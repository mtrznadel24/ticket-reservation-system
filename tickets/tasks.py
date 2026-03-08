import uuid

from celery import shared_task
from django.core.files.base import ContentFile

from .models import OrderDetails
from .utils.pdf_generator import draw_tickets_to_buffer


@shared_task(name="cleanup_reservations_task")
def cleanup_reservations_task():
    from tickets.services.order_logic import unlock_expired_tickets
    unlock_expired_tickets()

@shared_task
def generate_tickets_pdf_task(order_id):
    try:
        order_details = (OrderDetails.objects.filter(order_id=order_id)
                         .select_related('ticket', 'participant', 'ticket__event', 'order'))

        if not order_details.exists():
            return f"No details found for order {order_id}"

        order = order_details[0].order

        tickets_data = [{
            'has_numbered_seats': d.ticket.event.has_numbered_seats,
            'event_name': f"{d.ticket.event.name}",
            'name': f"{d.participant.first_name} {d.participant.last_name}",
            'sector': f"{d.ticket.sector}",
            'row': f"{d.ticket.row}",
            'seat': f"{d.ticket.seat}",
            'uuid': f"{d.ticket_uuid}"
        } for d in order_details]

        buffer = draw_tickets_to_buffer(tickets_data)

        unique_uuid = uuid.uuid4().hex
        pdf_name = f"order_{order_id}_tickets_{unique_uuid}.pdf"
        order.tickets_pdf.save(pdf_name, ContentFile(buffer.getvalue()), save=True)

        buffer.close()

        return f"Order {order_id} tickets generated"

    except Exception as e:
        return f"Error generating tickets pdf: {e}"

