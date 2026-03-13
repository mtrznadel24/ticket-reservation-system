import stripe
import time
from django.conf import settings
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_stripe_checkout_session(request, order):
    base_url = settings.SITE_URL.rstrip("/")

    success_url = f"{base_url}{reverse('finalize_cart')}"
    cancel_url = f"{base_url}{reverse('payment_canceled')}"

    logger.info(
        f"Initiating Stripe Checkout for Order #{order.id} | Return URL: {success_url}"
    )
    expires_at = int(time.time()) + (30 * 60)
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        expires_at=expires_at,
        line_items=[
            {
                "price_data": {
                    "currency": "pln",
                    "product_data": {
                        "name": f"Bilety na zamówienie #{order.id}",
                    },
                    "unit_amount": int(order.total_price() * 100),
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        metadata={
            "order_id": order.id,
        },
    )

    return session
