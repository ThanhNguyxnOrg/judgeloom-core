from __future__ import annotations

from typing import TYPE_CHECKING

from django.template.defaultfilters import slugify
from django.utils import timezone

from apps.organizations.constants import OrganizationRequestStatus
from apps.organizations.models import Organization, OrganizationRequest
from core.exceptions import NotFoundError, ValidationError
from core.validators import validate_slug

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.accounts.models import User


class OrganizationService:
    """Business operations for organization lifecycle and membership."""

    @staticmethod
    def create_organization(name: str, creator: User, **kwargs: str | bool | None) -> Organization:
        """Create a new organization and assign creator as admin/member.

        Args:
            name: Organization display name.
            creator: User creating the organization.
            **kwargs: Optional additional model fields.

        Returns:
            Newly created organization.

        Raises:
            ValidationError: If name/slug is invalid or already exists.
        """

        clean_name = name.strip()
        if not clean_name:
            raise ValidationError("Organization name is required.")

        raw_slug = kwargs.pop("slug", None)
        slug = str(raw_slug) if raw_slug else slugify(clean_name)
        validate_slug(slug)

        if Organization.objects.filter(name__iexact=clean_name).exists():
            raise ValidationError("Organization name already exists.")
        if Organization.objects.filter(slug=slug).exists():
            raise ValidationError("Organization slug already exists.")

        organization = Organization.objects.create(name=clean_name, slug=slug, **kwargs)
        creator.organizations.add(organization)
        organization.admins.add(creator)
        return organization

    @staticmethod
    def add_member(org: Organization, user: User) -> None:
        """Add a user to an organization if not already present."""

        if not OrganizationService.is_member(org, user):
            user.organizations.add(org)

    @staticmethod
    def remove_member(org: Organization, user: User) -> None:
        """Remove a user from an organization."""

        user.organizations.remove(org)
        org.admins.remove(user)

    @staticmethod
    def promote_admin(org: Organization, user: User) -> None:
        """Promote an existing member to organization admin.

        Raises:
            ValidationError: If user is not a member.
        """

        if not OrganizationService.is_member(org, user):
            raise ValidationError("User must be a member before promotion.")
        org.admins.add(user)

    @staticmethod
    def demote_admin(org: Organization, user: User) -> None:
        """Demote an organization admin to regular member."""

        org.admins.remove(user)

    @staticmethod
    def request_membership(org: Organization, user: User, reason: str) -> OrganizationRequest:
        """Create a pending membership request.

        Args:
            org: Target organization.
            user: Requesting user.
            reason: User-provided request rationale.

        Returns:
            Newly created pending request.

        Raises:
            ValidationError: If user is already a member or has pending request.
        """

        if OrganizationService.is_member(org, user):
            raise ValidationError("User is already a member.")

        pending_exists = OrganizationRequest.objects.filter(
            organization=org,
            user=user,
            status=OrganizationRequestStatus.PENDING,
        ).exists()
        if pending_exists:
            raise ValidationError("A pending request already exists.")

        return OrganizationRequest.objects.create(
            organization=org,
            user=user,
            status=OrganizationRequestStatus.PENDING,
            reason=reason.strip(),
        )

    @staticmethod
    def approve_request(request: OrganizationRequest, reviewer: User) -> None:
        """Approve a pending request and add user to organization.

        Raises:
            ValidationError: If request is not pending.
        """

        if request.status != OrganizationRequestStatus.PENDING:
            raise ValidationError("Only pending requests can be approved.")

        OrganizationService.add_member(request.organization, request.user)
        request.status = OrganizationRequestStatus.APPROVED
        request.reviewed_by = reviewer
        request.reviewed_at = timezone.now()
        request.response = ""
        request.save(update_fields=["status", "reviewed_by", "reviewed_at", "response", "updated_at"])

    @staticmethod
    def reject_request(request: OrganizationRequest, reviewer: User, response: str) -> None:
        """Reject a pending request with reviewer feedback.

        Raises:
            ValidationError: If request is not pending.
        """

        if request.status != OrganizationRequestStatus.PENDING:
            raise ValidationError("Only pending requests can be rejected.")

        request.status = OrganizationRequestStatus.REJECTED
        request.reviewed_by = reviewer
        request.reviewed_at = timezone.now()
        request.response = response.strip()
        request.save(update_fields=["status", "reviewed_by", "reviewed_at", "response", "updated_at"])

    @staticmethod
    def list_members(org: Organization) -> QuerySet[User]:
        """Return queryset of members for an organization."""

        return org.members.order_by("username")

    @staticmethod
    def is_member(org: Organization, user: User) -> bool:
        """Check whether a user is currently a member.

        Args:
            org: Organization entity.
            user: Candidate member.

        Returns:
            ``True`` if user belongs to organization.
        """

        return org.members.filter(pk=user.pk).exists()

    @staticmethod
    def get_request_or_404(org: Organization, request_id: int) -> OrganizationRequest:
        """Resolve request by id inside organization scope.

        Args:
            org: Organization instance.
            request_id: Request primary key.

        Returns:
            Matching ``OrganizationRequest``.

        Raises:
            NotFoundError: If request does not exist.
        """

        request_obj = OrganizationRequest.objects.filter(organization=org, pk=request_id).first()
        if request_obj is None:
            raise NotFoundError("Organization request not found.")
        return request_obj
