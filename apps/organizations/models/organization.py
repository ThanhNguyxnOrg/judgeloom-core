from __future__ import annotations

from django.db import models

from core.models import SluggedModel


class Organization(SluggedModel):
    """User organization for teams, schools, or communities."""

    name = models.CharField(max_length=255, unique=True)
    short_name = models.CharField(max_length=64, blank=True, default="")
    about = models.TextField(blank=True, default="")
    logo = models.ImageField(upload_to="organizations/logos/", null=True, blank=True)
    admins = models.ManyToManyField(
        "accounts.User",
        related_name="admin_of",
        blank=True,
    )
    is_open = models.BooleanField(default=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    access_code = models.CharField(max_length=64, null=True, blank=True)

    class Meta(SluggedModel.Meta):
        """Model metadata and index definitions for organization search."""

        db_table = "organizations_organization"
        ordering = ["name"]
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"
        indexes = [
            models.Index(fields=["slug"], name="organizations_slug_idx"),
            models.Index(fields=["name"], name="organizations_name_idx"),
        ]

    def get_slug_source(self) -> str:
        return self.name

    @property
    def member_count(self) -> int:
        """Return current number of members.

        Returns:
            Number of users attached to this organization.
        """

        return self.members.count()

    def __str__(self) -> str:
        """Return concise organization representation."""

        return self.name
