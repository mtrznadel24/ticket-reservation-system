import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField


class Event(models.Model):
    name = models.CharField(max_length=64)
    image = models.ImageField(upload_to="events/%Y/%m/%d/", null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=255, default='Main Arena')
    start_datetime = models.DateTimeField(db_index=True)
    need_pesel = models.BooleanField(default=False)
    has_numbered_seats = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "events"


class Ticket(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        SOLD = "sold", "Sold"
        SCANNED = "scanned", "Scanned"

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    sector = models.CharField(max_length=16, null=True, blank=True)
    row = models.CharField(max_length=16, null=True, blank=True)
    seat = models.CharField(max_length=16, null=True, blank=True)

    price = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status, default=Status.AVAILABLE)
    reserved_until = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()

        if self.event.has_numbered_seats:
            if not self.sector or not self.row or not self.seat:
                raise ValidationError({
                    'seat': "Numbered events require a sector, row, and seat to be specified.",
                    'row': "Required for numbered events.",
                    'sector': "Required for numbered events."
                })
        else:
            self.sector = None
            self.row = None
            self.seat = None

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ticket: {self.id} for {self.event.name}, seat: {self.seat}, price: {self.price}"

    class Meta:
        db_table = "tickets"
        unique_together = ("event", "sector", "row", "seat")
        indexes = [
            models.Index(fields=['status', 'reserved_until']),
        ]
        permissions = [
            ("can_scan_ticket", "Can verify and scan event tickets"),
        ]


class Participant(models.Model):
    first_name = models.CharField(max_length=64, null=True, blank=True)
    last_name = models.CharField(max_length=64, null=True, blank=True)
    pesel = EncryptedCharField(max_length=11, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        db_table = "participants"


class ActiveTicketsQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(order__user=user)

    def completed(self):
        return self.filter(order__status=Order.Status.COMPLETED)

    def usable(self):
        now = timezone.now()
        buffer_time = now - timedelta(hours=6)
        return self.filter(ticket__event__start_datetime__gte=buffer_time)

class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"

    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tickets_pdf = models.FileField(upload_to="tickets_pdfs/%Y/%m/%d/", null=True, blank=True)

    def __str__(self):
        return f"Order {self.id}"

    class Meta:
        db_table = "orders"

    def total_price(self):
        result = OrderDetails.objects.filter(order=self).aggregate(
            total=Sum("ticket__price")
        )
        return result["total"] or 0


class OrderDetails(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="details")
    participant = models.ForeignKey(Participant, null=True, blank=True, on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    ticket_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    scanned_at = models.DateTimeField(null=True, blank=True)


    objects = models.Manager()
    active = ActiveTicketsQuerySet.as_manager()

    def __str__(self):
        return f"Order by {self.participant} for ticket {self.ticket}"

    class Meta:
        db_table = "orders_details"
