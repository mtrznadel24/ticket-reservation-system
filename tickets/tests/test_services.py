from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from tickets.models import Ticket, OrderDetails, Order, Participant, Event
from tickets.services.order_logic import unlock_expired_tickets, reserve_tickets, cancel_order_service, finalize_order, \
    update_participants_details, release_order_tickets


@pytest.mark.django_db
class TestOrderLogic:

    # --- UNLOCK EXPIRED TICKETS ---

    def test_unlock_expired_tickets_happy_path(self, reserved_ticket, pending_order):
        reserved_ticket.reserved_until = timezone.now() - timedelta(minutes=5)
        reserved_ticket.save()

        OrderDetails.objects.create(order=pending_order, ticket=reserved_ticket)

        assert Order.objects.count() == 1
        assert OrderDetails.objects.count() == 1

        unlock_expired_tickets()

        reserved_ticket.refresh_from_db()

        assert reserved_ticket.status == Ticket.Status.AVAILABLE
        assert reserved_ticket.reserved_until is None

        assert Order.objects.count() == 0
        assert OrderDetails.objects.count() == 0

    def test_unlock_expired_tickets_unhappy_path(self, reserved_ticket, pending_order):
        reserved_ticket.reserved_until = timezone.now() + timedelta(minutes=5)
        reserved_ticket.save()

        OrderDetails.objects.create(order=pending_order, ticket=reserved_ticket)

        assert Order.objects.count() == 1
        assert OrderDetails.objects.count() == 1

        unlock_expired_tickets()

        reserved_ticket.refresh_from_db()

        assert reserved_ticket.status == Ticket.Status.RESERVED
        assert reserved_ticket.reserved_until is not None

        assert Order.objects.count() == 1
        assert OrderDetails.objects.count() == 1

    # --- RESERVE TICKETS ---

    @pytest.mark.django_db
    def test_reserve_tickets_blocks_more_than_8(self, test_user, create_tickets):
        tickets = create_tickets(9)
        tickets_ids = [t.id for t in tickets]

        with pytest.raises(ValidationError) as exc_info:
            reserve_tickets(user=test_user, ticket_ids=tickets_ids)

        assert "Too many tickets in cart" in str(exc_info.value)

    @pytest.mark.django_db
    def test_reserve_tickets_refreshes_existing_timer(self, test_user, create_tickets, pending_order):
        tickets = create_tickets(2)
        ticket_old = tickets[0]
        ticket_new = tickets[1]

        ticket_old.status = Ticket.Status.RESERVED
        ticket_old.reserved_until = timezone.now() + timedelta(minutes=10)
        ticket_old.save()
        OrderDetails.objects.create(order=pending_order, ticket=ticket_old)

        reserve_tickets(user=test_user, ticket_ids=[ticket_new.id])

        ticket_old.refresh_from_db()
        ticket_new.refresh_from_db()

        assert ticket_old.reserved_until == ticket_new.reserved_until

        assert ticket_old.reserved_until < timezone.now() + timedelta(minutes=10)

    @pytest.mark.django_db
    def test_reserve_tickets_lazy_cleanup_on_expired_cart(self, test_user, create_tickets, pending_order):
        tickets = create_tickets(2)
        ticket_expired = tickets[0]
        ticket_new = tickets[1]

        ticket_expired.status = Ticket.Status.RESERVED
        ticket_expired.reserved_until = timezone.now() - timedelta(minutes=5)
        ticket_expired.save()
        OrderDetails.objects.create(order=pending_order, ticket=ticket_expired)

        reserve_tickets(user=test_user, ticket_ids=[ticket_new.id])

        ticket_expired.refresh_from_db()
        assert ticket_expired.status == Ticket.Status.AVAILABLE
        assert ticket_expired.reserved_until is None

        ticket_new.refresh_from_db()
        assert ticket_new.status == Ticket.Status.RESERVED

        active_order = Order.objects.get(user=test_user, status=Order.Status.PENDING)
        assert OrderDetails.objects.filter(order=active_order).count() == 1
        assert OrderDetails.objects.first().ticket == ticket_new

    # --- RELEASE ORDER TICKETS ---

    def test_release_order_tickets_releases_and_deletes(self, test_user, create_tickets, pending_order):
        tickets = list(create_tickets(2))
        for t in tickets:
            t.status = Ticket.Status.RESERVED
            t.reserved_until = timezone.now() + timedelta(minutes=10)
            t.save()
            OrderDetails.objects.create(order=pending_order, ticket=t)

        release_order_tickets(pending_order, tickets)

        for t in tickets:
            t.refresh_from_db()
            assert t.status == Ticket.Status.AVAILABLE
            assert t.reserved_until is None

        assert Order.objects.filter(id=pending_order.id).count() == 0
        assert OrderDetails.objects.count() == 0

    # --- UPDATE PARTICIPANTS ---

    def test_update_participants_mixed_existing_and_new(self, test_user, reserved_ticket, pending_order, future_event):
        other_ticket = Ticket.objects.create(event=future_event, sector="A", row="1", seat="12",
                                     price=Decimal("50.00"), status=Ticket.Status.RESERVED)

        p1 = Participant.objects.create(user=test_user, first_name="Michael", last_name="Brown")
        detail_1 = OrderDetails.objects.create(order=pending_order, ticket=reserved_ticket, participant=p1)
        detail_2 = OrderDetails.objects.create(order=pending_order, ticket=other_ticket)

        data_list = [
            {"first_name": "John", "last_name": "Deep"},
            {"first_name": "James", "last_name": "Johnson"}
        ]

        update_participants_details(test_user, data_list, [detail_1, detail_2])

        p1.refresh_from_db()
        detail_2.refresh_from_db()

        assert p1.first_name == "John"
        assert p1.last_name == "Deep"
        assert p1.pesel is None

        assert detail_2.participant.first_name == "James"
        assert detail_2.participant.last_name == "Johnson"
        assert detail_2.participant.pesel is None

    def test_update_participants_missing_pesel_raises_error(self, test_user, reserved_ticket, pending_order):
        reserved_ticket.event.need_pesel = True
        reserved_ticket.event.save()

        detail = OrderDetails.objects.create(order=pending_order, ticket=reserved_ticket)
        data_list = [{"first_name": "John", "last_name": "Deep", "pesel": ""}]

        with pytest.raises(ValidationError) as exc_info:
            update_participants_details(test_user, data_list, [detail])

        assert "PESEL is strictly required" in str(exc_info.value)

    # --- FINALIZE ORDER ---

    @patch('tickets.services.order_logic.generate_tickets_pdf_task.delay_on_commit')
    @pytest.mark.django_db
    def test_finalize_order_happy_path(self, mock_pdf_task, reserved_ticket, pending_order):
        detail = OrderDetails.objects.create(order=pending_order, ticket=reserved_ticket)

        finalize_order(pending_order.id)
        mock_pdf_task.assert_called_once_with(pending_order.id)

        pending_order.refresh_from_db()
        detail.ticket.refresh_from_db()

        assert pending_order.status == Order.Status.COMPLETED
        assert detail.ticket.status == Ticket.Status.SOLD

    def test_finalize_order_ignores_non_pending_orders(self, pending_order):
        pending_order.status = Order.Status.COMPLETED
        pending_order.save()

        # We patch the task to ensure it is NOT called
        with patch('tickets.services.order_logic.generate_tickets_pdf_task.delay_on_commit') as mock_task:
            finalize_order(pending_order.id)

            mock_task.assert_not_called()

    # --- CANCEL ORDER ---

    def test_cancel_order_happy_path(self, test_user, reserved_ticket, pending_order):
        OrderDetails.objects.create(order=pending_order, ticket=reserved_ticket)

        cancel_order_service(test_user, pending_order.id)

        pending_order.refresh_from_db()
        reserved_ticket.refresh_from_db()

        assert pending_order.status == Order.Status.CANCELED
        assert reserved_ticket.status == Ticket.Status.AVAILABLE
        assert reserved_ticket.reserved_until is None

    def test_cancel_order_wrong_user_or_not_exists(self, db):
        from django.contrib.auth.models import User
        other_user = User.objects.create_user(username="other", password="123")

        with pytest.raises(ValidationError, match="Order does not exist"):
            cancel_order_service(other_user, 9999)

    @pytest.mark.django_db
    def test_cancel_order_fails_if_event_started(self, test_user, pending_order):

        past_event = Event.objects.create(
            name="Old Event",
            start_datetime=timezone.now() - timedelta(hours=1),
            location="History Museum"
        )
        t = Ticket.objects.create(event=past_event, sector="A", row="1", seat="99",
                                  status=Ticket.Status.RESERVED, price=Decimal("10.00"))
        OrderDetails.objects.create(order=pending_order, ticket=t)

        with pytest.raises(ValidationError, match=f"Cannot cancel: The event 'Old Event' has already started or passed."):
            cancel_order_service(test_user, pending_order.id)