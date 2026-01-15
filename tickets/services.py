from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from tickets.models import Order, Ticket, Participant, OrderDetails


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
            order.status = Order.Status.CANCELED
            order.save()


@transaction.atomic
def reserve_tickets(user, ticket_ids):
    if not ticket_ids:
        raise ValidationError("Nie wybrano żadnych biletów")

    order, _ = Order.objects.get_or_create(user=user, status=Order.Status.PENDING)

    for ticket_id in ticket_ids:
        ticket = Ticket.objects.select_for_update().get(id=ticket_id)
        if ticket.status != Ticket.Status.AVAILABLE:
            raise ValidationError(f"Bilet {ticket.seat} jest już niedostępny.")

        participant = Participant.objects.create(user=user)
        ticket.status = Ticket.Status.RESERVED
        ticket.reserved_until = timezone.now() + timedelta(minutes=15)
        ticket.save()

        OrderDetails.objects.create(order=order, participant=participant, ticket=ticket)


@transaction.atomic
def update_participants_details(user, post_data, order_details):
    participants_to_update = []
    for detail in order_details:
        participant = detail.participant

        first_name = post_data.get(f"first_name_{participant.id}", "").strip()
        last_name = post_data.get(f"last_name_{participant.id}", "").strip()
        pesel = post_data.get(f"pesel_{participant.id}", "").strip()

        if not first_name or not last_name or not pesel:
            raise ValidationError("Należy wypełnić wszystkie pola")

        if len(pesel) != 11:
            raise ValidationError("Pesel powinien mieć długość 11")

        participant.first_name = first_name
        participant.last_name = last_name
        participant.pesel = pesel

        participants_to_update.append(participant)

    Participant.objects.bulk_update(
        participants_to_update, ["first_name", "last_name", "pesel"]
    )


@transaction.atomic
def finalize_order(order):
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


@transaction.atomic
def cancel_order_service(user, order_id):
    try:
        order = Order.objects.get(id=order_id, user=user)
    except Order.DoesNotExist:
        raise ValidationError("Zamówienie nie istnieje")

    if order.status == "canceled":
        raise ValidationError("Zamówienie zostało już anulowane")

    order_details = OrderDetails.objects.filter(order=order).select_related("ticket")

    tickets_to_update = []

    for detail in order_details:
        ticket = detail.ticket
        ticket.status = Ticket.Status.AVAILABLE
        ticket.reserved_until = None
        tickets_to_update.append(ticket)

    Ticket.objects.bulk_update(tickets_to_update, ["status", "reserved_until"])

    order.status = Order.Status.CANCELED
    order.save()
