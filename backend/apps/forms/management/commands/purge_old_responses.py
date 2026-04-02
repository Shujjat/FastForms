"""Delete Response rows (and answers via CASCADE) older than RESPONSE_RETENTION_DAYS."""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.forms.models import Response as FormResponse


class Command(BaseCommand):
    help = "Delete form responses with submitted_at older than RESPONSE_RETENTION_DAYS (0 = disabled)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print how many rows would be deleted without deleting.",
        )

    def handle(self, *args, **options):
        days = int(getattr(settings, "RESPONSE_RETENTION_DAYS", 0) or 0)
        if days <= 0:
            self.stdout.write(self.style.WARNING("RESPONSE_RETENTION_DAYS is 0 or unset; nothing to do."))
            return

        cutoff = timezone.now() - timedelta(days=days)
        qs = FormResponse.objects.filter(submitted_at__lt=cutoff)
        n = qs.count()
        if options["dry_run"]:
            self.stdout.write(self.style.NOTICE(f"Would delete {n} response(s) (submitted before {cutoff.isoformat()})."))
            return

        deleted, breakdown = qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} object(s). Breakdown: {breakdown}"))
