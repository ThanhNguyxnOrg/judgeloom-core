from __future__ import annotations

from django.db import models

class PostVisibility(models.TextChoices):
    """Visibility states for a blog post."""

    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"

class CommentVisibility(models.TextChoices):
    """Visibility states for a comment."""

    VISIBLE = "visible", "Visible"
    HIDDEN = "hidden", "Hidden"
    DELETED = "deleted", "Deleted"
