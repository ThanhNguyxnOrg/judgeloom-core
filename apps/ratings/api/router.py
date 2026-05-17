from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from ninja import Router

from apps.contests.models import Contest
from apps.ratings.api.schemas import RatingChangeOut, RatingHistoryOut, RatingOut
from apps.ratings.services.rating_service import RatingService
from core.exceptions import ContestAccessDeniedError
from core.permissions import is_superuser

router = Router(tags=["ratings"])


@router.get("/history/{user_id}", response=list[RatingHistoryOut])
def rating_history(request, user_id: int) -> list[dict[str, Any]]:
    """Return rating history for one user."""

    user_model = get_user_model()
    user = get_object_or_404(user_model, pk=user_id)
    return RatingService.get_rating_history(user)


@router.get("/contest/{contest_key}", response=list[RatingChangeOut])
def contest_rating_changes(request, contest_key: str) -> list[dict[str, Any]]:
    """Return rating changes for one contest."""

    contest = get_object_or_404(Contest, key=contest_key)
    return RatingService.get_contest_rating_changes(contest)


@router.post("/calculate/{contest_key}", response=list[RatingOut])
def calculate_contest_ratings(request, contest_key: str) -> list[dict[str, Any]]:
    """Trigger rating calculation for a contest. Superuser-only."""

    if not is_superuser(request):
        raise ContestAccessDeniedError("Only superusers can calculate ratings.")

    contest = get_object_or_404(Contest, key=contest_key)
    rows = RatingService.calculate_ratings(contest)
    return [
        {
            "user_id": row.user_id,
            "contest_key": row.contest.key,
            "rank": row.rank,
            "rating_before": row.rating_before,
            "rating_after": row.rating_after,
            "delta": row.rating_after - row.rating_before,
            "performance": row.performance,
        }
        for row in rows
    ]
