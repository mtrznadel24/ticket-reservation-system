from datetime import timedelta

import stripe
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum, IntegerField
from django.db.models.functions import Cast
from django.forms import formset_factory
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, ListView, DetailView

from .models import Ticket, Event, Order, OrderDetails
from .forms import ParticipantForm, CustomUserCreationForm
from tickets.services.order_logic import (
    reserve_tickets,
    update_participants_details,
    finalize_order,
    cancel_order_service,
    remove_from_cart,
    release_order_tickets,
)
from .services.stripe_service import create_stripe_checkout_session

# Public views


class IndexView(TemplateView):
    """Display the homepage with the latest 5 upcoming events."""

    template_name = "tickets/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["latest_events"] = (
            Event.objects.filter(start_datetime__gte=timezone.now())
            .annotate(
                available_count=Count(
                    "ticket",
                    filter=Q(ticket__status=Ticket.Status.AVAILABLE),
                )
            )
            .order_by("start_datetime")[:5]
        )

        return context


class EventsView(ListView):
    """Display the events with searchbar."""

    template_name = "tickets/events.html"
    context_object_name = "events"

    def get_queryset(self):
        now = timezone.now()

        query = self.request.GET.get("search")

        qs = (
            Event.objects.filter(start_datetime__gt=now).annotate(
                available_count=Count(
                    "ticket", filter=Q(ticket__status=Ticket.Status.AVAILABLE)
                )
            )
        ).order_by("start_datetime")

        if query:
            qs = qs.filter(name__icontains=query)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["search_query"] = self.request.GET.get("search", "")

        return context


# Buying process


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
    """Display the payment success page."""

    template_name = "tickets/payment_success.html"


class PaymentCanceledView(LoginRequiredMixin, TemplateView):
    """Display the payment canceled page."""

    template_name = "tickets/payment_canceled.html"


@login_required
def tickets_view(request, event_id):
    """
    Handle seat selection. Supports:
    1. Interactive grid for numbered seats.
    2. Quantity selection for general admission.
    """
    event = get_object_or_404(Event, pk=event_id)
    tickets = Ticket.objects.filter(event=event).annotate(
        row_int=Cast('row', output_field=IntegerField()),
        seat_int=Cast('seat', output_field=IntegerField())
    ).order_by("sector", "row_int", "seat_int")

    if request.method == "POST":
        selected_ticket_ids = []

        if event.has_numbered_seats:
            selected_ticket_ids = request.POST.getlist("ticket_ids")
        else:
            quantity = int(request.POST.get("quantity", 0))
            if quantity > 0:
                selected_ticket_ids = list(
                    Ticket.objects.filter(
                        event=event, status=Ticket.Status.AVAILABLE
                    ).order_by("price").values_list("id", flat=True)[:quantity]
                )

        if not selected_ticket_ids:
            messages.error(request, "No tickets selected.")
            return redirect("tickets", event_id=event_id)

        try:
            reserve_tickets(user=request.user, ticket_ids=selected_ticket_ids)
            messages.success(request, "Tickets were added to cart successfully.")
            return redirect("cart")

        except ValidationError as e:
            messages.error(request, str(e.message))

        except Exception as e:
            messages.error(request, str(e))
            return redirect("tickets", event_id=event_id)

    return render(request, "tickets/tickets.html", {"event": event, "tickets": tickets})


@login_required
def cart_view(request):
    """Display the cart page with filling forms"""
    try:
        now = timezone.now()
        order = Order.objects.get(user=request.user, status=Order.Status.PENDING)
        order_details = OrderDetails.objects.filter(order=order).select_related(
            "participant", "ticket", "ticket__event"
        )
        total = order.total_price()

        if order_details and order_details[0].ticket.reserved_until < now:
            tickets = [d.ticket for d in order_details]
            release_order_tickets(order, tickets)
            return redirect("cart")

    except Order.DoesNotExist:
        order = None
        order_details = []
        total = 0

    ParticipantFormSet = formset_factory(ParticipantForm, extra=len(order_details))

    if request.method == "POST":
        for detail in order_details:
            if detail.ticket.reserved_until < timezone.now():
                messages.error(
                    request, "Reservation time out. Your cart has been cleared."
                )
                return redirect("cart")
        formset = ParticipantFormSet(request.POST)
        if formset.is_valid():
            try:
                session = create_stripe_checkout_session(request, order)
                update_participants_details(
                    request.user, formset.cleaned_data, order_details
                )
                expire_time = timezone.now() + timedelta(minutes=15)
                for detail in order_details:
                    detail.ticket.reserved_until = expire_time
                return redirect(session.url, code=303)

            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
        else:
            messages.error(request, "Errors in the form")
    else:
        initial_data = [
            {
                "first_name": d.participant.first_name if d.participant else "",
                "last_name": d.participant.last_name if d.participant else "",
                "pesel": d.participant.pesel if d.participant else "",
            }
            for d in order_details
        ]
        formset = ParticipantFormSet(initial=initial_data)

    forms_with_details = list(zip(order_details, formset))

    expiry_time = None
    if order_details:
        expiry_time = order_details[0].ticket.reserved_until.isoformat()

    return render(
        request,
        "tickets/cart.html",
        {
            "order": order,
            "total": total,
            "formset": formset,
            "forms_with_details": forms_with_details,
            "expiry_time": expiry_time,
        },
    )


@login_required
def cart_clear_view(request):
    """Clear the user cart"""
    try:
        order = Order.objects.prefetch_related("details__ticket").get(
            user=request.user, status=Order.Status.PENDING
        )

        details = order.details.all()
        tickets = [d.ticket for d in details]

        release_order_tickets(order, tickets)

    except Order.DoesNotExist:
        messages.error(request, "Order does not exist")

    return redirect("cart")


@login_required
def remove_from_cart_view(request, ticket_id):
    """Remove ticket from cart"""
    try:
        remove_from_cart(request.user, ticket_id)
        messages.success(request, "Successfully removed from cart.")
    except ValidationError as e:
        messages.error(request, str(e))

    return redirect("cart")


@login_required
def finalize_cart(request):
    """Finalize the purchase."""
    session_id = request.GET.get("session_id")

    if not session_id:
        messages.error(request, "No payment session id provided.")
        return redirect("cart")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        order_id = session.metadata.get("order_id")

        if session.payment_status == "paid":
            finalize_order(order_id)
            messages.success(request, "Purchase was successful!")
            return redirect("payment_success", order_id=order_id)
        else:
            messages.error(request, "Payment was not confirmed")
            return redirect("cart")

    except Order.DoesNotExist:
        messages.error(request, "No order to finalize.")
        return redirect("home")
    except Exception as e:
        messages.error(request, f"Error occurred during finalizing  {e}")
        return redirect("cart")


# User Dashboard


class MyTicketsView(LoginRequiredMixin, ListView):
    """Display logged user active tickets"""

    template_name = "tickets/my_tickets.html"
    context_object_name = "details"

    def get_queryset(self):
        details = (
            OrderDetails.active.for_user(self.request.user)
            .completed()
            .usable()
            .select_related("ticket", "participant", "order", "ticket__event")
            .order_by("ticket__event__start_datetime")
        )
        return details


class MyOrdersView(LoginRequiredMixin, ListView):
    """Display logged user orders."""

    template_name = "tickets/my_orders.html"
    context_object_name = "orders"

    def get_queryset(self):
        orders = (
            Order.objects.filter(user=self.request.user)
            .annotate(total_calculated_price=Sum("details__ticket__price"))
            .order_by("-updated_at")
        )
        return orders


class OrderDetailsView(LoginRequiredMixin, DetailView):
    """Display details of an order."""

    model = Order
    template_name = "tickets/order_details.html"
    context_object_name = "order"
    pk_url_kwarg = "order_id"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        details = OrderDetails.objects.filter(order=self.object).select_related(
            "ticket", "participant", "ticket__event"
        )

        now = timezone.now()
        can_be_canceled = False

        if self.object.status == Order.Status.COMPLETED:
            can_be_canceled = all(d.ticket.event.start_datetime > now for d in details)

        context["details"] = details
        context["can_cancel"] = can_be_canceled
        return context


@require_POST
@login_required
def cancel_order(request, order_id):
    """Cancel an order."""
    try:
        cancel_order_service(request.user, order_id)
        messages.success(request, "Order was cancelled.")

    except ValidationError as e:
        messages.error(request, e.message)
    except Exception as e:
        messages.error(request, f"There was an error {e}")

    return redirect("order_details", order_id=order_id)


# Scanner/Staff


@login_required
@permission_required("tickets.can_scan_ticket", raise_exception=True)
def scan_preview(request):
    """Display a page to scan a ticket."""
    return render(request, "tickets/scan_preview.html")


@login_required
@permission_required("tickets.can_scan_ticket", raise_exception=True)
def scan_ticket_view(request, ticket_uuid):
    """Display a page after scanning a ticket enabling to update ticket.is_scanned data."""
    detail = get_object_or_404(
        OrderDetails.objects.select_related("ticket", "participant", "ticket__event"),
        ticket_uuid=ticket_uuid,
    )

    if request.method == "POST":
        if detail.scanned_at:
            messages.error(request, "Ticket already scanned.")
            return redirect("scan_ticket", ticket_uuid=ticket_uuid)

        detail.scanned_at = timezone.now()
        detail.save()
        detail.ticket.status = Ticket.Status.SCANNED
        detail.ticket.save()

        messages.success(request, "Ticket scanned.")

        return redirect("scan_ticket", ticket_uuid=ticket_uuid)

    pesel = detail.participant.pesel
    masked_pesel = ""

    if pesel and len(pesel) == 11:
        masked_pesel = f"{pesel[:6]}***{pesel[-2:]}"

    context = {"detail": detail, "masked_pesel": masked_pesel}

    return render(request, "tickets/scan_ticket.html", context)


# Webhooks/Auth


def register(request):
    """Display a page to register new user"""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.first_name = form.cleaned_data["first_name"]
            user.last_name = form.cleaned_data["last_name"]
            user.email = form.cleaned_data["email"]
            user.save()

            login(request, user)
            return redirect("home")
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/register.html", {"form": form})


@csrf_exempt
def stripe_webhook(request):
    """Handle a webhook request."""
    payload = request.body
    sig_header = request.headers.get("stripe-signature")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")

        if order_id:
            finalize_order(order_id)

    return HttpResponse(status=200)
