from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from tickets.models import Event, Order, OrderDetails, Ticket, Participant


@pytest.mark.django_db
class TestPublicViews:
    def test_index_view(self, client):
        response = client.get(reverse("home"))
        assert response.status_code == 200

    def test_events_view_search_and_time_filtering(self, client, db):
        now = timezone.now()

        e_rock = Event.objects.create(
            name="Rock Concert", start_datetime=now + timedelta(days=5)
        )
        e_jazz = Event.objects.create(
            name="Jazz Night", start_datetime=now + timedelta(days=5)
        )
        e_past = Event.objects.create(
            name="Old Rock", start_datetime=now - timedelta(days=2)
        )

        url = reverse("events")

        response = client.get(url, {"search": "Rock"})

        assert response.status_code == 200

        events_in_context = response.context["events"]

        assert len(events_in_context) == 1
        assert e_rock in events_in_context

        assert e_jazz not in events_in_context
        assert e_past not in events_in_context

        assert response.context["search_query"] == "Rock"


@pytest.mark.django_db
class TestPurchaseViews:
    def test_payment_success_view_requires_login(self, client, pending_order):
        url = reverse("payment_success", kwargs={"order_id": pending_order.id})
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_payment_success_view_for_logged_user(
        self, client, test_user, pending_order
    ):
        client.force_login(test_user)
        url = reverse("payment_success", kwargs={"order_id": pending_order.id})

        response = client.get(url)

        assert response.status_code == 200
        assert "tickets/payment_success.html" in [t.name for t in response.templates]

    def test_payment_canceled_view_requires_login(self, client):
        url = reverse("payment_canceled")
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_payment_canceled_view_for_logged_user(self, client, test_user):
        client.force_login(test_user)
        url = reverse("payment_canceled")

        response = client.get(url)

        assert response.status_code == 200
        assert "tickets/payment_canceled.html" in [t.name for t in response.templates]

    def test_cart_view_get_with_items(
        self, client, test_user, reserved_ticket, pending_order
    ):
        client.force_login(test_user)
        reserved_ticket.reserved_until = timezone.now() + timedelta(minutes=10)
        reserved_ticket.save()

        OrderDetails.objects.create(
            order=pending_order, participant=None, ticket=reserved_ticket
        )
        url = reverse("cart")
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["total"] == Decimal("99.99")
        assert "expiry_time" in response.context
        assert (
            response.context["expiry_time"]
            == reserved_ticket.reserved_until.isoformat()
        )

    @patch("tickets.views.reserve_tickets")
    def test_tickets_view_general_admission_success(
        self, mock_reserve, client, test_user, future_event, create_tickets
    ):
        client.force_login(test_user)
        future_event.has_numbered_seats = False
        future_event.save()

        create_tickets(5)

        url = reverse("tickets", kwargs={"event_id": future_event.id})

        response = client.post(url, {"quantity": "2"})

        assert response.status_code == 302
        assert response.url == reverse("cart")

        mock_reserve.assert_called_once()

        args, kwargs = mock_reserve.call_args
        assert len(kwargs["ticket_ids"]) == 2

    def test_tickets_view_no_tickets_selected_shows_error(
        self, client, test_user, future_event
    ):
        client.force_login(test_user)
        future_event.has_numbered_seats = True
        future_event.save()

        url = reverse("tickets", kwargs={"event_id": future_event.id})
        response = client.post(url, {"ticket_ids": []})

        assert response.status_code == 302
        assert response.url == url

        messages = list(get_messages(response.wsgi_request))
        assert "No tickets selected." in str(messages[0])

    @patch("tickets.views.reserve_tickets")
    def test_tickets_view_catches_validation_error(
        self, mock_reserve, client, test_user, future_event
    ):
        client.force_login(test_user)
        future_event.has_numbered_seats = True
        future_event.save()

        mock_reserve.side_effect = ValidationError("Too many tickets")

        url = reverse("tickets", kwargs={"event_id": future_event.id})
        response = client.post(url, {"ticket_ids": [1, 2]})

        messages = list(get_messages(response.wsgi_request))
        assert "Too many tickets" in str(messages[0])

    def test_cart_view_clears_expired_cart_on_get(
        self, client, test_user, reserved_ticket, pending_order
    ):
        client.force_login(test_user)

        from django.utils import timezone
        from datetime import timedelta

        reserved_ticket.reserved_until = timezone.now() - timedelta(minutes=5)
        reserved_ticket.save()
        OrderDetails.objects.create(order=pending_order, ticket=reserved_ticket)

        url = reverse("cart")
        response = client.get(url)

        assert response.status_code == 302
        assert response.url == url

        assert Order.objects.filter(id=pending_order.id).count() == 0

    def test_remove_from_cart_view_success(
        self, client, test_user, reserved_ticket, pending_order
    ):
        client.force_login(test_user)

        OrderDetails.objects.create(order=pending_order, ticket=reserved_ticket)
        assert OrderDetails.objects.count() == 1

        url = reverse("remove_from_cart", kwargs={"ticket_id": reserved_ticket.id})
        response = client.get(url)

        assert response.status_code == 302
        assert response.url == reverse("cart")

        reserved_ticket.refresh_from_db()
        assert reserved_ticket.status == Ticket.Status.AVAILABLE
        assert reserved_ticket.reserved_until is None

        assert OrderDetails.objects.count() == 0
        assert Order.objects.filter(id=pending_order.id).count() == 0

    def test_remove_from_cart_view_invalid_ticket(
        self, client, test_user, future_event
    ):
        client.force_login(test_user)

        other_ticket = Ticket.objects.create(
            event=future_event,
            sector="A",
            row="1",
            seat="99",
            price="50.00",
            status=Ticket.Status.AVAILABLE,
        )

        url = reverse("remove_from_cart", kwargs={"ticket_id": other_ticket.id})
        response = client.get(url)

        assert response.status_code == 302
        assert response.url == reverse("cart")

        from django.contrib.messages import get_messages

        messages = list(get_messages(response.wsgi_request))
        assert len(messages) > 0
        assert "This ticket is not in your cart" in str(messages[0])

    def test_cart_clear_view_success(
        self, client, test_user, create_tickets, pending_order
    ):
        client.force_login(test_user)

        tickets = create_tickets(3)
        for t in tickets:
            t.status = Ticket.Status.RESERVED
            t.save()
            OrderDetails.objects.create(order=pending_order, ticket=t)

        assert OrderDetails.objects.count() == 3

        url = reverse("cart_clear")
        response = client.get(url)

        assert response.status_code == 302

        assert Ticket.objects.filter(status=Ticket.Status.AVAILABLE).count() >= 3

        assert Order.objects.count() == 0
        assert OrderDetails.objects.count() == 0

    @patch("tickets.views.finalize_order")
    @patch("tickets.views.stripe.checkout.Session.retrieve")
    def test_finalize_cart_payment_success(
        self,
        mock_stripe_retrieve,
        mock_finalize_order,
        client,
        test_user,
        pending_order,
    ):
        client.force_login(test_user)

        mock_session = MagicMock()
        mock_session.metadata = {"order_id": pending_order.id}
        mock_session.payment_status = "paid"
        mock_stripe_retrieve.return_value = mock_session

        url = reverse("finalize_cart") + "?session_id=cs_test_abc123"

        response = client.get(url)
        mock_finalize_order.assert_called_once_with(pending_order.id)

        assert response.status_code == 302
        assert response.url == reverse(
            "payment_success", kwargs={"order_id": pending_order.id}
        )

    def test_finalize_cart_no_session_id(self, client, test_user):
        client.force_login(test_user)
        url = reverse("finalize_cart")
        response = client.get(url)

        assert response.status_code == 302
        assert response.url == reverse("cart")

    @patch("tickets.views.stripe.checkout.Session.retrieve")
    def test_finalize_cart_unpaid_status(self, mock_retrieve, client, test_user):
        client.force_login(test_user)

        mock_session = MagicMock()
        mock_session.metadata = {"order_id": 99}
        mock_session.payment_status = "unpaid"
        mock_retrieve.return_value = mock_session

        url = reverse("finalize_cart") + "?session_id=cs_test_123"
        response = client.get(url)

        assert response.status_code == 302
        assert response.url == reverse("cart")
        messages = list(get_messages(response.wsgi_request))
        assert "Payment was not confirmed" in str(messages[0])


@pytest.mark.django_db
class TestDashboardViews:
    def test_my_tickets_and_orders_require_login(self, client):
        assert client.get(reverse("my_tickets")).status_code == 302
        assert client.get(reverse("my_orders")).status_code == 302

    def test_my_orders_view_calculates_total_price(
        self, client, test_user, future_event
    ):
        client.force_login(test_user)

        order = Order.objects.create(user=test_user, status=Order.Status.COMPLETED)
        t1 = Ticket.objects.create(
            event=future_event,
            sector="A",
            row="1",
            seat="1",
            price=Decimal("100.00"),
            status=Ticket.Status.SOLD,
        )
        t2 = Ticket.objects.create(
            event=future_event,
            sector="A",
            row="1",
            seat="2",
            price=Decimal("50.00"),
            status=Ticket.Status.SOLD,
        )

        OrderDetails.objects.create(order=order, ticket=t1)
        OrderDetails.objects.create(order=order, ticket=t2)

        response = client.get(reverse("my_orders"))
        assert response.status_code == 200

        orders_in_context = response.context["orders"]
        assert len(orders_in_context) == 1
        assert orders_in_context[0].total_calculated_price == Decimal("150.00")

    def test_order_details_view_can_cancel_logic(self, client, test_user, future_event):
        client.force_login(test_user)
        order = Order.objects.create(user=test_user, status=Order.Status.COMPLETED)
        t = Ticket.objects.create(
            event=future_event,
            sector="A",
            row="1",
            seat="1",
            price=Decimal("10.00"),
            status=Ticket.Status.SOLD,
        )
        OrderDetails.objects.create(order=order, ticket=t)

        url = reverse("order_details", kwargs={"order_id": order.id})
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["can_cancel"] is True

    @patch("tickets.views.cancel_order_service")
    def test_cancel_order_post_only_and_calls_service(
        self, mock_cancel_service, client, test_user, pending_order
    ):
        client.force_login(test_user)
        url = reverse("cancel_order", kwargs={"order_id": pending_order.id})

        response_get = client.get(url)
        assert response_get.status_code == 405

        response_post = client.post(url)
        assert response_post.status_code == 302

        mock_cancel_service.assert_called_once_with(test_user, pending_order.id)


@pytest.mark.django_db
class TestScannerViews:
    def test_scan_preview_denies_without_permission(self, client, test_user):
        client.force_login(test_user)
        response = client.get(reverse("scan_preview"))
        assert response.status_code == 403

    def test_scan_preview_allows_with_permission(self, client, staff_user):
        client.force_login(staff_user)
        response = client.get(reverse("scan_preview"))
        assert response.status_code == 200

    def test_scan_ticket_view_masks_pesel_on_get(
        self, client, staff_user, future_event
    ):
        client.force_login(staff_user)
        order = Order.objects.create(user=staff_user, status=Order.Status.COMPLETED)
        t = Ticket.objects.create(
            event=future_event,
            sector="A",
            row="1",
            seat="1",
            price=Decimal("10.00"),
            status=Ticket.Status.SOLD,
        )
        participant = Participant.objects.create(
            user=staff_user, first_name="Jan", last_name="Kowalski", pesel="12345678901"
        )

        detail = OrderDetails.objects.create(
            order=order, ticket=t, participant=participant
        )

        url = reverse("scan_ticket", kwargs={"ticket_uuid": detail.ticket_uuid})
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["masked_pesel"] == "123456***01"

    def test_scan_ticket_view_post_updates_status(
        self, client, staff_user, future_event
    ):
        client.force_login(staff_user)
        order = Order.objects.create(user=staff_user, status=Order.Status.COMPLETED)
        t = Ticket.objects.create(
            event=future_event,
            sector="A",
            row="1",
            seat="1",
            price=Decimal("10.00"),
            status=Ticket.Status.SOLD,
        )
        participant = Participant.objects.create(
            user=staff_user, first_name="Jan", pesel="12345678901"
        )
        detail = OrderDetails.objects.create(
            order=order, ticket=t, participant=participant
        )

        url = reverse("scan_ticket", kwargs={"ticket_uuid": detail.ticket_uuid})

        response = client.post(url)
        assert response.status_code == 302

        detail.refresh_from_db()
        detail.ticket.refresh_from_db()

        assert detail.scanned_at is not None
        assert detail.ticket.status == Ticket.Status.SCANNED

    def test_scan_ticket_view_post_already_scanned(
        self, client, staff_user, future_event
    ):
        client.force_login(staff_user)
        order = Order.objects.create(user=staff_user, status=Order.Status.COMPLETED)
        t = Ticket.objects.create(
            event=future_event,
            sector="A",
            row="1",
            seat="1",
            price=Decimal("10.00"),
            status=Ticket.Status.SCANNED,
        )
        participant = Participant.objects.create(
            user=staff_user, first_name="Jan", pesel="12345678901"
        )

        detail = OrderDetails.objects.create(
            order=order, ticket=t, participant=participant, scanned_at=timezone.now()
        )

        url = reverse("scan_ticket", kwargs={"ticket_uuid": detail.ticket_uuid})
        response = client.post(url)

        from django.contrib.messages import get_messages

        messages = list(get_messages(response.wsgi_request))
        assert "Ticket already scanned." in str(messages[0])
