from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone

from apps.judge.models import Judge, Language
from core.exceptions import NotFoundError

if TYPE_CHECKING:
    from django.db.models import QuerySet


class JudgeService:
    """Service layer for judge and language retrieval and state changes."""

    @classmethod
    def get_judge(cls, name: str) -> Judge:
        """Fetch a judge by unique name.

        Args:
            name: Judge identifier.

        Returns:
            Judge instance.

        Raises:
            NotFoundError: If the judge does not exist.
        """
        judge = Judge.objects.filter(name=name).first()
        if judge is None:
            raise NotFoundError(f"Judge '{name}' was not found.")
        return judge

    @classmethod
    def list_judges(cls) -> QuerySet[Judge]:
        """List judges with prefetches for admin/API usage.

        Returns:
            Queryset of all judges.
        """
        return Judge.objects.prefetch_related("runtimes", "problems").all()

    @classmethod
    def get_available_judges(cls) -> QuerySet[Judge]:
        """List judges that are online and not blocked.

        Returns:
            Queryset of available judges.
        """
        return Judge.objects.filter(online=True, is_blocked=False).order_by("name")

    @classmethod
    def update_judge_ping(cls, judge: Judge, ping_ms: float) -> None:
        """Update judge ping and online heartbeat state.

        Args:
            judge: Judge instance to update.
            ping_ms: New ping latency in milliseconds.
        """
        judge.ping = ping_ms
        judge.online = True
        if judge.start_time is None:
            judge.start_time = timezone.now()
        judge.save(update_fields=["ping", "online", "start_time", "updated_at"])

    @classmethod
    def block_judge(cls, judge: Judge) -> None:
        """Block a judge from receiving new work.

        Args:
            judge: Judge instance to block.
        """
        judge.is_blocked = True
        judge.save(update_fields=["is_blocked", "updated_at"])

    @classmethod
    def unblock_judge(cls, judge: Judge) -> None:
        """Unblock a judge and allow new dispatching.

        Args:
            judge: Judge instance to unblock.
        """
        judge.is_blocked = False
        judge.save(update_fields=["is_blocked", "updated_at"])

    @classmethod
    def get_supported_languages(cls) -> QuerySet[Language]:
        """Return all enabled languages.

        Returns:
            Queryset of enabled language records.
        """
        return Language.objects.filter(is_enabled=True).order_by("key")

    @classmethod
    def get_language_by_key(cls, key: str) -> Language:
        """Fetch language by key.

        Args:
            key: Language key value.

        Returns:
            Matching language instance.

        Raises:
            NotFoundError: If language key is unknown.
        """
        language = Language.objects.filter(key=key).first()
        if language is None:
            raise NotFoundError(f"Language '{key}' was not found.")
        return language
