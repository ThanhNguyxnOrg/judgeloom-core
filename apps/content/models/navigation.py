from __future__ import annotations

from django.db import models

from core.models import OrderedModel

class NavigationItem(OrderedModel):
    """Navigation item that supports hierarchical menus."""

    key = models.CharField(max_length=100, unique=True)
    label = models.CharField(max_length=120)
    url = models.CharField(max_length=500)
    icon = models.CharField(max_length=120, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    is_external = models.BooleanField(default=False)

    class Meta:
        db_table = "content_navigation_item"
        verbose_name = "Navigation item"
        verbose_name_plural = "Navigation items"
        ordering = ("order",)
        indexes = [
            models.Index(fields=["key"], name="content_nav_key_idx"),
            models.Index(fields=["parent", "order"], name="content_nav_parent_order_idx"),
        ]

    def __str__(self) -> str:
        """Return the navigation item label."""

        return self.label
