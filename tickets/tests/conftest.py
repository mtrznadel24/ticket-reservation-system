from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User, Permission
from django.utils import timezone

from tickets.models import Event, Ticket, Order


@pytest.fixture
def test_user(db):
    """Create and return test user."""
    return User.objects.create_user(username='test_user', password='password123')

@pytest.fixture
def future_event(db):
    """Create and return a future event."""

    return Event.objects.create(name='Event', start_datetime=timezone.now() + timedelta(days=5))

@pytest.fixture
def available_ticket(future_event):
    """Create and return an available ticket."""
    return Ticket.objects.create(
        event=future_event,
        sector="A",
        row="1",
        seat="10",
        price=Decimal("99.99"),
        status=Ticket.Status.AVAILABLE
    )

@pytest.fixture
def reserved_ticket(future_event):
    """Create and return an available ticket."""
    return Ticket.objects.create(
        event=future_event,
        sector="A",
        row="1",
        seat="11",
        price=Decimal("99.99"),
        status=Ticket.Status.RESERVED
    )

@pytest.fixture
def create_tickets(future_event):
    """Factory fixture to create multiple available tickets."""
    def _create_tickets(quantity):
        tickets = [
            Ticket(
                event=future_event,
                sector="A",
                row="1",
                seat=f"{i}",
                price=Decimal("99.99"),
                status=Ticket.Status.AVAILABLE
            )
            for i in range(quantity)
        ]
        return Ticket.objects.bulk_create(tickets)
    return _create_tickets

@pytest.fixture
def pending_order(test_user, db):
    """Create and return a pending order for the test user."""
    return Order.objects.create(user=test_user, status=Order.Status.PENDING)


@pytest.fixture
def staff_user(test_user):
    """Fixture that grants the scan_ticket permission to the user."""
    permission = Permission.objects.get(codename='can_scan_ticket')
    test_user.user_permissions.add(permission)
    return test_user