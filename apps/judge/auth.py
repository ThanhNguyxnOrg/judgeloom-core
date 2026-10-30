from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from ninja.errors import HttpError
from ninja.security import HttpBearer

from apps.judge.models import Judge

if TYPE_CHECKING:
    from django.http import HttpRequest


class JudgeTokenAuth(HttpBearer):
    """Bearer-token authentication for judge workers."""

    def authenticate(self, request: HttpRequest, token: str) -> Judge | None:
        """Resolve a judge by the SHA-256 hash of its bearer token.

        Args:
            request: Incoming request.
            token: Raw bearer token.

        Returns:
            The matching judge, or None for an unknown token.

        Raises:
            HttpError: If the judge is blocked.
        """

        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        judge = Judge.objects.filter(token_hash=digest).first()
        if judge is None:
            return None
        if judge.is_blocked:
            raise HttpError(403, "Judge is blocked.")
        return judge
