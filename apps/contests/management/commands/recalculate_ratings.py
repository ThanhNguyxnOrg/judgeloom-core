"""
JudgeLoom — recalculate_ratings management command
=====================================================

Recalculates ratings for all rated contests or a specific contest.
Deletes existing Rating records and re-runs the rating algorithm.

Usage::

    python manage.py recalculate_ratings
    python manage.py recalculate_ratings --contest abc123
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from apps.contests.constants import ParticipationStatus
from apps.contests.models import Contest, ContestParticipation
from apps.ratings.models import Rating


class Command(BaseCommand):
    """Recalculate ratings for rated contests."""

    help = "Recalculate user ratings from contest participation data."

    def add_arguments(self, parser: CommandParser) -> None:
        """Define CLI arguments.

        Args:
            parser: Argument parser instance.
        """
        parser.add_argument(
            "--contest",
            type=str,
            default=None,
            help="Recalculate ratings for a specific contest key only.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be recalculated without writing to the database.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Execute the command.

        Args:
            *args: Positional arguments (unused).
            **options: Parsed CLI options.
        """
        contest_key: str | None = options["contest"]  # type: ignore[assignment]
        dry_run: bool = options["dry_run"]  # type: ignore[assignment]

        contests = Contest.objects.filter(is_rated=True).order_by("end_time")
        if contest_key:
            contests = contests.filter(key=contest_key)

        if not contests.exists():
            self.stdout.write(self.style.WARNING("No rated contests found."))
            return

        self.stdout.write(f"Processing {contests.count()} rated contest(s)...")

        for contest in contests:
            participations = (
                ContestParticipation.objects.filter(
                    contest=contest,
                    status=ParticipationStatus.LIVE,
                    is_disqualified=False,
                )
                .select_related("user")
                .order_by("-score", "cumulative_time")
            )

            participant_count = participations.count()
            if participant_count == 0:
                self.stdout.write(f"  {contest.key}: no eligible participants, skipping")
                continue

            if dry_run:
                self.stdout.write(
                    f"  {contest.key}: would recalculate {participant_count} rating(s)"
                )
                continue

            with transaction.atomic():
                Rating.objects.filter(contest=contest).delete()

                ratings_to_create: list[Rating] = []
                for rank, participation in enumerate(participations, start=1):
                    user = participation.user
                    previous_rating = user.rating
                    performance = int(participation.score * 10)
                    weight = 1.0 / rank
                    delta = int((performance - previous_rating) * weight * 0.4)
                    new_rating = max(previous_rating + delta, 0)

                    ratings_to_create.append(
                        Rating(
                            user=user,
                            contest=contest,
                            participation=participation,
                            rank=rank,
                            rating_before=previous_rating,
                            rating_after=new_rating,
                            performance=performance,
                        )
                    )

                Rating.objects.bulk_create(ratings_to_create)

                for rating in ratings_to_create:
                    type(rating.user).objects.filter(pk=rating.user_id).update(
                        rating=rating.rating_after,
                        max_rating=max(rating.rating_after, rating.user.max_rating),
                    )

            self.stdout.write(
                f"  {contest.key}: recalculated {participant_count} rating(s)"
            )

        self.stdout.write(self.style.SUCCESS("Rating recalculation complete."))
