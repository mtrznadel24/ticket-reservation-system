from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views import generic
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from .models import Ticket, Event, Order, OrderDetails
from django.contrib.auth import login
from .forms import CustomUserCreationForm
from .services import (
    reserve_tickets,
    update_participants_details,
    finalize_order,
    cancel_order_service,
)


class IndexView(TemplateView):
    template_name = "tickets/index.html"


class EventsView(generic.ListView):
    template_name = "tickets/events.html"
    context_object_name = "latest_events"

    def get_queryset(self):
        now = timezone.now()

        return (
            Event.objects.filter(event_date__gt=now)
            .annotate(
                available_count=Count("ticket", filter=Q(ticket__status="available"))
            )
            .order_by("event_date")
        )


@login_required
def tickets_view(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    tickets = (
        Ticket.objects.select_for_update()
        .filter(event=event, status=Ticket.Status.AVAILABLE)
        .order_by("seat")
    )

    if request.method == "POST":
        selected_ticket_ids = request.POST.getlist("ticket_ids")

        if not selected_ticket_ids:
            messages.error(request, "Nie wybrano żadnych biletów.")
            return redirect("tickets", event_id=event_id)

        try:
            reserve_tickets(user=request.user, ticket_ids=selected_ticket_ids)
            messages.success(request, "Bilety zostały dodane do koszyka.")
            return redirect("cart")

        except ValidationError as e:
            messages.error(request, str(e.message))

        except Exception as e:
            messages.error(request, str(e))
            return redirect("tickets", event_id=event_id)

    return render(request, "tickets/tickets.html", {"event": event, "tickets": tickets})


@login_required
def cart_view(request):
    try:
        order = Order.objects.get(user=request.user, status=Order.Status.PENDING)
        order_details = OrderDetails.objects.filter(order=order).select_related(
            "participant", "ticket"
        )
        total = order.total_price()

    except Order.DoesNotExist:
        order = None
        order_details = []
        total = 0

    if request.method == "POST":
        try:
            update_participants_details(request.user, request.POST, order_details)
            return redirect("finalize_cart")
        except ValidationError as e:
            messages.error(request, str(e.message))
        except Exception as e:
            messages.error(request, str(e))

    return render(
        request,
        "tickets/cart.html",
        {"order": order, "order_details": order_details, "total": total},
    )


@login_required
@transaction.atomic
def finalize_cart(request):
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(
                user=request.user, status=Order.Status.PENDING
            )
            finalize_order(order)

        messages.success(request, "Zakup zakończony sukcesem!")
        return redirect("order_details", order_id=order.id)

    except Order.DoesNotExist:
        messages.error(request, "Brak zamówienia do finalizacji.")
        return redirect("home")
    except Exception as e:
        messages.error(request, f"Wystąpił błąd podczas finalizacji zamówienia: {e}")
        return redirect("cart")


def register(request):
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


@login_required
def my_orders(request):
    orders = (
        Order.objects.filter(user=request.user)
        .annotate(total_calculated_price=Sum("orderdetails__ticket__price"))
        .order_by("-updated_at")
    )

    return render(request, "tickets/my_orders.html", {"orders": orders})


@login_required
def order_details(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    details = OrderDetails.objects.filter(order=order).select_related(
        "ticket", "participant"
    )

    return render(
        request, "tickets/order_details.html", {"order": order, "details": details}
    )


@require_POST
@login_required
def cancel_order(request, order_id):
    try:
        cancel_order_service(request.user, order_id)
        messages.success(request, "Zamówienie zostało anulowane.")

    except ValidationError as e:
        messages.error(request, e.message)
    except Exception as e:
        messages.error(request, f"Wystąpił błąd: {e}")

    return redirect("order_details", order_id=order_id)
