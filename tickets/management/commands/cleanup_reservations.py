from django.core.management.base import BaseCommand
from tickets.services import unlock_expired_tickets


class Command(BaseCommand):
    help = "Zwalnia rezerwacje biletów po terminie i anuluje puste zamówienia"

    def handle(self, *args, **options):
        self.stdout.write("Czyszczenia rezerwacji...")

        unlock_expired_tickets()

        self.stdout.write(self.style.SUCCESS("Pomyślnie zakończono czyszczenie"))
