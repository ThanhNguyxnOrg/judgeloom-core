from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.content.constants import PostVisibility
from core.models import SluggedModel

class BlogPost(SluggedModel):
    """Markdown blog post published on the platform."""

    title = models.CharField(max_length=200)
    author = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="blog_posts",
    )
    content = models.TextField(help_text="Post content in Markdown format.")
    summary = models.TextField(blank=True)
    visibility = models.CharField(
        max_length=16,
        choices=PostVisibility.choices,
        default=PostVisibility.DRAFT,
    )
    publish_date = models.DateTimeField(null=True, blank=True)
    is_pinned = models.BooleanField(default=False)
    organizations = models.ManyToManyField(
        "organizations.Organization",
        blank=True,
        related_name="blog_posts",
    )
    is_organization_private = models.BooleanField(default=False)
    og_image = models.URLField(blank=True)

    @property
    def is_published(self) -> bool:
        """Return True when the post is publicly published."""

        return (
            self.visibility == PostVisibility.PUBLISHED
            and self.publish_date is not None
            and self.publish_date <= timezone.now()
        )

    @property
    def is_draft(self) -> bool:
        """Return True when the post is still a draft."""

        return self.visibility == PostVisibility.DRAFT

    @property
    def comment_count(self) -> int:
        """Return the number of visible comments for this post."""

        return self.comments.filter(visibility="visible").count()

    def get_slug_source(self) -> str:
        """Return the source value used to generate the slug."""

        return self.title

    class Meta:
        db_table = "content_blog_post"
        verbose_name = "Blog post"
        verbose_name_plural = "Blog posts"
        ordering = ("-is_pinned", "-publish_date")
        indexes = [
            models.Index(fields=["visibility"], name="content_post_vis_idx"),
            models.Index(fields=["publish_date"], name="content_post_pub_idx"),
            models.Index(fields=["is_pinned"], name="content_post_pin_idx"),
        ]

    def __str__(self) -> str:
        """Return the post title as the string representation."""

        return self.title
