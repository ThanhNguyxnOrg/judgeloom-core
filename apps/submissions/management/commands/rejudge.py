"""
JudgeLoom — rejudge management command
==========================================

Enqueues rejudge tasks for submissions matching the given filters.
Supports filtering by problem code, user, or submission ID range.

Usage::

    python manage.py rejudge --problem aplusb
    python manage.py rejudge --user alice --user bob
    python manage.py rejudge --id-from 100 --id-to 200
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db.models import QuerySet

from apps.submissions.models import Submission


class Command(BaseCommand):
    """Rejudge submissions matching the specified criteria."""

    help = "Rejudge submissions filtered by problem, user, or ID range."

    def add_arguments(self, parser: CommandParser) -> None:
        """Define CLI arguments.

        Args:
            parser: Argument parser instance.
        """
        parser.add_argument(
            "--problem",
            type=str,
            default=None,
            help="Problem code to rejudge submissions for.",
        )
        parser.add_argument(
            "--user",
            type=str,
            action="append",
            default=None,
            help="Username(s) whose submissions to rejudge (repeatable).",
        )
        parser.add_argument(
            "--id-from",
            type=int,
            default=None,
            help="Minimum submission ID (inclusive).",
        )
        parser.add_argument(
            "--id-to",
            type=int,
            default=None,
            help="Maximum submission ID (inclusive).",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Execute the command.

        Args:
            *args: Positional arguments (unused).
            **options: Parsed CLI options.
        """
        problem_code: str | None = options["problem"]  # type: ignore[assignment]
        usernames: list[str] | None = options["user"]  # type: ignore[assignment]
        id_from: int | None = options["id_from"]  # type: ignore[assignment]
        id_to: int | None = options["id_to"]  # type: ignore[assignment]

        if not any([problem_code, usernames, id_from, id_to]):
            raise CommandError(
                "At least one filter is required: --problem, --user, --id-from, or --id-to."
            )

        queryset: QuerySet[Submission] = Submission.objects.all()

        if problem_code:
            queryset = queryset.filter(problem__code=problem_code)
        if usernames:
            queryset = queryset.filter(user__username__in=usernames)
        if id_from is not None:
            queryset = queryset.filter(pk__gte=id_from)
        if id_to is not None:
            queryset = queryset.filter(pk__lte=id_to)

        count = queryset.count()
        if count == 0:
            self.stdout.write(self.style.WARNING("No submissions match the given filters."))
            return

        self.stdout.write(f"Enqueuing {count} submission(s) for rejudge...")

        from apps.submissions.tasks import rejudge_submissions

        submission_ids = list(queryset.values_list("pk", flat=True))
        rejudge_submissions.delay(submission_ids)

        self.stdout.write(
            self.style.SUCCESS(f"Enqueued {count} submission(s) for rejudge.")
        )
