from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.content.constants import PostVisibility
from apps.content.models import BlogPost
from core.exceptions import NotFoundError

class PostService:
    """Business operations for blog posts."""

    @staticmethod
    def create_post(
        title: str,
        author: Any,
        content: str,
        visibility: str = "draft",
    ) -> BlogPost:
        """Create and persist a new blog post.

        Args:
            title: Post title.
            author: User creating the post.
            content: Markdown body text.
            visibility: Initial post visibility.

        Returns:
            The created blog post instance.
        """

        summary: str = PostService._derive_summary(content)
        return BlogPost.objects.create(
            title=title,
            author=author,
            content=content,
            summary=summary,
            visibility=visibility,
        )

    @staticmethod
    def update_post(post: BlogPost, **kwargs: Any) -> BlogPost:
        """Update a post with supplied field values.

        Args:
            post: Existing post instance.
            **kwargs: Mutable field values.

        Returns:
            The updated post.
        """

        mutable_fields = {
            "title",
            "content",
            "summary",
            "visibility",
            "is_pinned",
            "is_organization_private",
            "og_image",
        }
        updated_fields: list[str] = []

        for key, value in kwargs.items():
            if key in mutable_fields:
                setattr(post, key, value)
                updated_fields.append(key)

        if "content" in updated_fields and "summary" not in updated_fields and not post.summary:
            post.summary = PostService._derive_summary(post.content)
            updated_fields.append("summary")

        if updated_fields:
            post.save(update_fields=updated_fields)
        return post

    @staticmethod
    def publish_post(post: BlogPost) -> BlogPost:
        """Publish a draft post immediately.

        Args:
            post: Post to publish.

        Returns:
            The published post.
        """

        post.visibility = PostVisibility.PUBLISHED
        post.publish_date = timezone.now()
        post.save(update_fields=["visibility", "publish_date"])
        return post

    @staticmethod
    def get_visible_posts(user: Any) -> QuerySet[BlogPost]:
        """Return posts visible to a specific user.

        Args:
            user: Current request user.

        Returns:
            QuerySet with visibility and organization filters applied.
        """

        queryset = BlogPost.objects.select_related("author").prefetch_related("organizations")

        if getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False):
            return queryset

        base_filter = Q(visibility=PostVisibility.PUBLISHED, publish_date__lte=timezone.now())
        queryset = queryset.filter(base_filter)

        if not getattr(user, "is_authenticated", False):
            return queryset.filter(is_organization_private=False)

        if not hasattr(user, "organizations"):
            return queryset.filter(is_organization_private=False)

        user_organizations = user.organizations.all()
        return queryset.filter(
            Q(is_organization_private=False)
            | Q(is_organization_private=True, organizations__in=user_organizations)
        ).distinct()

    @staticmethod
    def get_post_by_slug(slug: str) -> BlogPost:
        """Return a blog post by slug.

        Args:
            slug: Unique post slug.

        Returns:
            Matching blog post.

        Raises:
            NotFoundError: If the post does not exist.
        """

        try:
            return BlogPost.objects.select_related("author").prefetch_related("organizations").get(
                slug=slug
            )
        except BlogPost.DoesNotExist as exc:
            raise NotFoundError(f"Post with slug '{slug}' was not found.") from exc

    @staticmethod
    def pin_post(post: BlogPost) -> None:
        """Pin a post to the top of listings.

        Args:
            post: Post to pin.
        """

        if not post.is_pinned:
            post.is_pinned = True
            post.save(update_fields=["is_pinned"])

    @staticmethod
    def unpin_post(post: BlogPost) -> None:
        """Remove a post from pinned listings.

        Args:
            post: Post to unpin.
        """

        if post.is_pinned:
            post.is_pinned = False
            post.save(update_fields=["is_pinned"])

    @staticmethod
    def _derive_summary(content: str, max_chars: int = 280) -> str:
        """Derive a plain summary from Markdown text.

        Args:
            content: Full markdown content.
            max_chars: Maximum summary length.

        Returns:
            Truncated summary text.
        """

        collapsed = " ".join(content.split())
        if len(collapsed) <= max_chars:
            return collapsed
        return f"{collapsed[: max_chars - 3].rstrip()}..."
