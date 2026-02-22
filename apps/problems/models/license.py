from __future__ import annotations

from django.db import models

from core.models import SluggedModel

class License(SluggedModel):
    """Represents a reusable problem content license."""

    name = models.CharField(max_length=128, unique=True)
    key = models.CharField(max_length=64, unique=True)
    text = models.TextField()
    url = models.URLField(blank=True)

    class Meta:
        db_table = "problems_license"
        ordering = ("name",)
        verbose_name = "Problem license"
        verbose_name_plural = "Problem licenses"
        indexes = [
            models.Index(fields=["name"], name="prob_lic_name_idx"),
            models.Index(fields=["key"], name="prob_lic_key_idx"),
        ]

    def __str__(self) -> str:
        """Return the human readable license name."""

        return self.name

    def get_slug_source(self) -> str:
        """Return the canonical source used for slug generation."""

        return self.key
