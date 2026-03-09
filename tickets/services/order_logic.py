from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from tickets.models import Order, Ticket, Participant, OrderDetails
from tickets.tasks import generate_tickets_pdf_task


@transaction.atomic
def unlock_expired_tickets():
    now = timezone.now()

    expired_tickets = Ticket.objects.filter(status=Ticket.Status.RESERVED, reserved_until__lt=now)

    if not expired_tickets.exists():
        return

    affected_ids = list(
        OrderDetails.objects.filter(ticket__in=expired_tickets)
        .values_list("order_id", flat=True)
        .distinct()
    )

    expired_tickets.update(status=Ticket.Status.AVAILABLE, reserved_until=None)

    orders_to_check = Order.objects.filter(
        id__in=affected_ids, status=Order.Status.PENDING
    )

    for order in orders_to_check:
        if (
            not OrderDetails.objects.filter(order=order)
            .exclude(ticket__status=Ticket.Status.AVAILABLE)
            .exists()
        ):
            order.delete()



@transaction.atomic
def reserve_tickets(user, ticket_ids):
    if not ticket_ids:
        raise ValidationError("Nie wybrano żadnych biletów")

    order, _ = Order.objects.get_or_create(user=user, status=Order.Status.PENDING)

    existing_details = list(OrderDetails.objects.select_related("ticket").filter(order=order))

    if existing_details and existing_details[0].ticket.reserved_until < timezone.now():
        tickets_to_release = [d.ticket for d in existing_details]
        for ticket in tickets_to_release:
            ticket.status = Ticket.Status.AVAILABLE
            ticket.reserved_until = None
        Ticket.objects.bulk_update(tickets_to_release, ["status", "reserved_until"])

        order.delete()
        order = Order.objects.create(user=user, status=Order.Status.PENDING)
        existing_details = []

    tickets_in_cart = [d.ticket for d in existing_details]
    tickets = list(Ticket.objects.select_for_update().filter(id__in=ticket_ids).order_by('id'))

    if len(tickets) + len(tickets_in_cart) > 8:
        raise ValidationError(f"Too many tickets in cart.")

    tickets_to_update = []
    order_details_to_create = []
    expiry_time = timezone.now() + timedelta(minutes=10)

    for ticket in tickets:
        if ticket.status != Ticket.Status.AVAILABLE:
            raise ValidationError(f"Bilet {ticket.seat} jest już niedostępny.")

        ticket.status = Ticket.Status.RESERVED
        ticket.reserved_until = expiry_time
        tickets_to_update.append(ticket)

        order_details_to_create.append(OrderDetails(order=order, participant=None, ticket=ticket))

    for ticket in tickets_in_cart:
        ticket.reserved_until = expiry_time
        tickets_to_update.append(ticket)

    OrderDetails.objects.bulk_create(order_details_to_create)
    Ticket.objects.bulk_update(tickets_to_update, ["status", "reserved_until"])

@transaction.atomic
def update_participants_details(user, data_list, order_details):
    for data, detail in zip(data_list, order_details):
        if detail.ticket.event.need_pesel and not data.get("pesel"):
            raise ValidationError(
                f"PESEL is strictly required for the event: {detail.ticket.event.name}"
            )

        if detail.participant:
            participant = detail.participant
            participant.first_name = data.get("first_name")
            participant.last_name = data.get("last_name")
            participant.pesel = data.get("pesel")
            participant.save()
        else:
            detail.participant = Participant.objects.create(
                user=user,
                **data
            )
            detail.save()


@transaction.atomic
def finalize_order(order_id):
    order = Order.objects.select_for_update().get(id=order_id)

    if order.status != Order.Status.PENDING:
        return

    order_details = OrderDetails.objects.filter(order=order).select_related(
        "ticket", "participant"
    )

    tickets_to_update = []
    for detail in order_details:
        ticket = detail.ticket
        ticket.status = Ticket.Status.SOLD
        tickets_to_update.append(ticket)

    Ticket.objects.bulk_update(tickets_to_update, ["status"])

    order.status = Order.Status.COMPLETED
    order.updated_at = timezone.now()
    order.save()

    generate_tickets_pdf_task.delay_on_commit(order_id)


@transaction.atomic
def cancel_order_service(user, order_id):
    try:
        order = Order.objects.get(id=order_id, user=user)
    except Order.DoesNotExist:
        raise ValidationError("Zamówienie nie istnieje")

    if order.status == "canceled":
        raise ValidationError("Zamówienie zostało już anulowane")

    order_details = OrderDetails.objects.filter(order=order).select_related("ticket", "ticket__event")

    now = timezone.now()
    for detail in order_details:
        if detail.ticket.event.start_datetime < now:
            raise ValidationError(
                f"Cannot cancel: The event '{detail.ticket.event.name}' has already started or passed.")

    tickets_to_update = []

    for detail in order_details:
        ticket = detail.ticket
        ticket.status = Ticket.Status.AVAILABLE
        ticket.reserved_until = None
        tickets_to_update.append(ticket)

    Ticket.objects.bulk_update(tickets_to_update, ["status", "reserved_until"])

    order.status = Order.Status.CANCELED
    order.save()
