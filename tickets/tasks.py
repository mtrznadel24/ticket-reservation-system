from celery import shared_task
from .services import unlock_expired_tickets

@shared_task(name="cleanup_reservations_task")
def cleanup_reservations_task():
    unlock_expired_tickets()