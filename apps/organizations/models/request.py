from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.organizations.constants import OrganizationRequestStatus
from core.models import TimestampedModel


class OrganizationRequest(TimestampedModel):
    """Membership request raised by a user for an organization."""

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="organization_requests",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="membership_requests",
    )
    status = models.CharField(
        max_length=16,
        choices=OrganizationRequestStatus.choices,
        default=OrganizationRequestStatus.PENDING,
    )
    reason = models.TextField(blank=True, default="")
    response = models.TextField(blank=True, default="")
    reviewed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_organization_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimestampedModel.Meta):
        """Model metadata and request consistency constraints."""

        db_table = "organizations_request"
        ordering = ["-created_at"]
        verbose_name = "Organization Request"
        verbose_name_plural = "Organization Requests"
        indexes = [
            models.Index(fields=["status"], name="organizations_req_status_idx"),
            models.Index(fields=["organization", "status"], name="org_req_org_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                condition=Q(status=OrganizationRequestStatus.PENDING),
                name="organizations_unique_pending_request",
            )
        ]

    def __str__(self) -> str:
        """Return concise request representation."""

        return f"{self.user.username}:{self.organization.slug}:{self.status}"
