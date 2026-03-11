from django.core.management import BaseCommand, CommandError

from tickets.models import Event, Ticket


class Command(BaseCommand):
    help = "Creating tickets for an event (numbered or not)"

    def add_arguments(self, parser):
        parser.add_argument("event_id", type=int)
        parser.add_argument("price", type=float)

        parser.add_argument(
            "--amount",
            type=int,
            help="Amount of tickets to create without numbered seats",
        )

        parser.add_argument("--sectors", type=str, help="Sectors as string np. 'A,B,C'")
        parser.add_argument("--rows", type=int, help="Number of rows")
        parser.add_argument("--seats", type=int, help="Number of seats in a row")

    def handle(self, *args, **options):
        event_id = options["event_id"]
        price = options["price"]
        event = Event.objects.get(id=event_id)
        tickets = []

        if event.has_numbered_seats:
            sectors = options["sectors"]
            rows = options["rows"]
            seats = options["seats"]

            if not all([sectors, rows, seats]):
                raise CommandError(
                    "For events with numbered seats, you must provide --sectors, --rows, and --seats"
                )

            sectors = [s.strip() for s in sectors.split(",")]

            for sector in sectors:
                for row in range(1, rows + 1):
                    for seat in range(1, seats + 1):
                        tickets.append(
                            Ticket(
                                event=event,
                                price=price,
                                sector=sector,
                                row=str(row),
                                seat=str(seat),
                            )
                        )

        else:
            amount = options["amount"]

            if amount is None:
                raise CommandError(
                    "For events with no numbered seat,you must specify an amount of tickets to create with --amount"
                )

            for _ in range(amount):
                tickets.append(Ticket(event=event, price=price))

        Ticket.objects.bulk_create(tickets)
        self.stdout.write(self.style.SUCCESS("Successfully created tickets"))
