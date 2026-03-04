import json

import stripe
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.forms import formset_factory
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views import generic
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from .models import Ticket, Event, Order, OrderDetails
from django.contrib.auth import login
from .forms import CustomUserCreationForm, ParticipantForm
from tickets.services.order_logic import (
    reserve_tickets,
    update_participants_details,
    finalize_order,
    cancel_order_service,
)
from .services.stripe_service import create_stripe_checkout_session


class IndexView(TemplateView):
    template_name = "tickets/index.html"


class EventsView(generic.ListView):
    template_name = "tickets/events.html"
    context_object_name = "latest_events"

    def get_queryset(self):
        now = timezone.now()

        return (
            Event.objects.filter(start_datetime__gt=now)
            .annotate(
                available_count=Count("ticket", filter=Q(ticket__status=Ticket.Status.AVAILABLE))
            )
            .order_by("start_datetime")
        )


@login_required
def tickets_view(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    tickets = (
        Ticket.objects
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

    ParticipantFormSet = formset_factory(ParticipantForm, extra=len(order_details))

    if request.method == "POST":
        formset = ParticipantFormSet(request.POST)
        if formset.is_valid():
            print("--- DEBUG: Formset jest VALID ---")
            try:
                print(f"--- DEBUG: Próba utworzenia sesji Stripe dla zamówienia {order.id} ---")
                session = create_stripe_checkout_session(request, order)
                print(f"--- DEBUG: Sesja utworzona: {session.url}")

                update_participants_details(request.user, formset.cleaned_data, order_details)
                return redirect(session.url, code=303)

            except Exception as e:
                print(f"--- DEBUG: BŁĄD STRIPE/LOGIKI: {str(e)}")
                messages.error(request, f"Błąd: {str(e)}")
        else:
            print("BŁĘDY FORMSETU:", formset.errors)
            print("BŁĘDY NON_FORM:", formset.non_form_errors())
            messages.error(request, "Błędy w formularzu")
    else:
        initial_data = [
            {
                'first_name': d.participant.first_name if d.participant else '',
                'last_name': d.participant.last_name if d.participant else '',
                'pesel': d.participant.pesel if d.participant else '',
            }
            for d in order_details
        ]
        formset = ParticipantFormSet(initial=initial_data)

    forms_with_details = list(zip(order_details, formset))

    return render(
        request,
        "tickets/cart.html",
        {"order": order, "total": total, 'formset': formset, "forms_with_details": forms_with_details},
    )


@login_required
def finalize_cart(request):
    session_id = request.GET.get("session_id")

    if not session_id:
        messages.error(request, "Brak identyfikatora sesji płatności.")
        return redirect("cart")

    try:

        session = stripe.checkout.Session.retrieve(session_id)
        order_id = session.metadata.get("order_id")

        if session.payment_status == "paid":
            finalize_order(order_id)
            messages.success(request, "Zakup zakończony sukcesem!")
            return redirect("payment_success", order_id=order_id)
        else:
            messages.error(request, "Płatność nie została potwierdzona")
            return redirect("cart")

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

@login_required
def my_tickets(request):
    details = (OrderDetails.active
               .for_user(request.user)
               .completed()
               .usable()
               .select_related("ticket", "participant", "order")
               .order_by("ticket__event__start_datetime"))

    return render(request, "tickets/my_tickets.html", {"details": details})



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

@login_required
def payment_success(request, order_id):

    return render(request, "tickets/payment_success.html", {"order_id": order_id})

@login_required
def payment_cancelled(request):

    return render(request, "tickets/payment_cancelled.html")


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.headers.get('stripe-signature')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_id = session.get('metadata', {}).get('order_id')

        if order_id:
            finalize_order(order_id)

    return HttpResponse(status=200)
