from __future__ import annotations

from django.db import models

from core.models import OrderedModel

class TagGroup(OrderedModel):
    """Logical grouping for sets of tags."""

    name = models.CharField(max_length=128, unique=True)
    tags = models.ManyToManyField("tags.Tag", related_name="groups", blank=True)

    class Meta:
        db_table = "tags_tag_group"
        ordering = ("order", "name")
        verbose_name = "Tag group"
        verbose_name_plural = "Tag groups"
        indexes = [
            models.Index(fields=["name"], name="tag_group_name_idx"),
            models.Index(fields=["order"], name="tag_group_order_idx"),
        ]

    def __str__(self) -> str:
        """Return display label for admin and debugging."""

        return self.name
