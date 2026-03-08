import stripe

from django.conf import settings
from django.urls import reverse

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_stripe_checkout_session(request, order):

    success_url = request.build_absolute_uri(reverse('finalize_cart'))
    cancel_url = request.build_absolute_uri(reverse('payment_canceled'))

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'pln',
                'product_data': {
                    'name': f'Bilety na zamówienie #{order.id}',
                },
                'unit_amount': int(order.total_price() * 100),
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        metadata={
            'order_id': order.id,
        }
    )

    return session

