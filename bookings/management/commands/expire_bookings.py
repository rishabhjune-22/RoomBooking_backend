from django.core.management.base import BaseCommand, CommandError

from bookings.services.expiry_service import expire_due_bookings


class Command(BaseCommand):
    help = "Mark past active bookings as expired."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1")

        expired_count = expire_due_bookings(batch_size=batch_size)
        self.stdout.write(self.style.SUCCESS(f"Expired {expired_count} booking(s)."))
