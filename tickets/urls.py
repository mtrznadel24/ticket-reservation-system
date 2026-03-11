from django.urls import path

from . import views

urlpatterns = [
    path("events", views.EventsView.as_view(), name="events"),
    path("events/<int:event_id>/", views.tickets_view, name="tickets"),
    path("my-orders/", views.MyOrdersView.as_view(), name="my_orders"),
    path(
        "my-orders/<int:order_id>/",
        views.OrderDetailsView.as_view(),
        name="order_details",
    ),
    path("my-tickets/", views.MyTicketsView.as_view(), name="my_tickets"),
    path("cancel-order/<int:order_id>/", views.cancel_order, name="cancel_order"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/clear/", views.cart_clear_view, name="cart_clear"),
    path(
        "cart/remove_ticket/<int:ticket_id>/",
        views.remove_from_cart_view,
        name="remove_from_cart",
    ),
    path("finalize/", views.finalize_cart, name="finalize_cart"),
    path(
        "success/<int:order_id>/",
        views.PaymentSuccessView.as_view(),
        name="payment_success",
    ),
    path("cancel/", views.PaymentCanceledView.as_view(), name="payment_canceled"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("scan/", views.scan_preview, name="scan_preview"),
    path("scan/<uuid:ticket_uuid>/", views.scan_ticket_view, name="scan_ticket"),
]
