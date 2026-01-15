import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum


class Event(models.Model):
    name = models.CharField(max_length=64)
    event_date = models.DateField()

    def __str__(self):
        return self.name

    class Meta:
        db_table = "events"


class Ticket(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        SOLD = "sold", "Sold"

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    seat = models.IntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status, default=Status.AVAILABLE)
    reserved_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Ticket: {self.id} for {self.event.name}, seat: {self.seat}, price: {self.price}"

    class Meta:
        db_table = "tickets"
        unique_together = ("event", "seat")


class Participant(models.Model):
    first_name = models.CharField(max_length=64, null=True, blank=True)
    last_name = models.CharField(max_length=64, null=True, blank=True)
    pesel = models.CharField(max_length=11, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        db_table = "participants"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"

    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

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
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    ticket_UUID = models.UUIDField(default=uuid.uuid4, editable=False)

    def __str__(self):
        return f"Order by {self.participant} for ticket {self.ticket}"

    class Meta:
        db_table = "orders_details"
