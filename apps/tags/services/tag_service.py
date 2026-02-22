from __future__ import annotations

from django.db.models import Count, QuerySet
from django.utils.text import slugify

from apps.problems.models import Problem
from apps.problems.services import ProblemService
from apps.tags.models import Tag
from core.exceptions import NotFoundError

class TagService:
    """Service layer for tag creation and tagging workflows."""

    @staticmethod
    def get_or_create_tag(name: str) -> Tag:
        """Find an existing tag or create one from a name.

        Args:
            name: Human-readable tag name.

        Returns:
            Tag: Existing or newly created tag.
        """

        normalized_name = name.strip()
        tag_code = slugify(normalized_name)
        if not tag_code:
            raise ValueError("Tag name cannot produce an empty slug.")

        tag, _ = Tag.objects.get_or_create(
            code=tag_code,
            defaults={"name": normalized_name},
        )
        return tag

    @staticmethod
    def tag_problem(problem: Problem, tag_names: list[str]) -> None:
        """Associate a set of tags to a problem.

        Args:
            problem: Target problem instance.
            tag_names: Collection of tag names to assign.
        """

        tags: list[Tag] = []
        for tag_name in tag_names:
            if not tag_name.strip():
                continue
            tags.append(TagService.get_or_create_tag(tag_name))

        if tags:
            problem.tags.add(*tags)

    @staticmethod
    def untag_problem(problem: Problem, tag_names: list[str]) -> None:
        """Detach selected tags from a problem."""

        cleaned_names = [name.strip() for name in tag_names if name.strip()]
        if not cleaned_names:
            return

        tags = Tag.objects.filter(name__in=cleaned_names)
        if tags.exists():
            problem.tags.remove(*tags)

    @staticmethod
    def get_popular_tags(limit: int = 20) -> QuerySet[Tag]:
        """Return tags ordered by number of linked problems."""

        return Tag.objects.annotate(problem_total=Count("problems")).order_by("-problem_total", "name")[:limit]

    @staticmethod
    def get_problems_by_tag(tag_code: str, user: object) -> QuerySet[Problem]:
        """Return visible problems that include a specific tag.

        Args:
            tag_code: Slug-like tag code.
            user: Current user for visibility filtering.

        Raises:
            NotFoundError: If tag does not exist.

        Returns:
            QuerySet[Problem]: Visibility-filtered problems for the tag.
        """

        tag = Tag.objects.filter(code=tag_code).first()
        if tag is None:
            raise NotFoundError(f"Tag '{tag_code}' does not exist.")

        visible_problems: QuerySet[Problem] = ProblemService.get_visible_problems(user)
        return visible_problems.filter(tags=tag).distinct()
