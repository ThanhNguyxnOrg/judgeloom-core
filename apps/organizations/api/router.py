from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.contrib.auth import get_user_model
from ninja import Router, Schema

from apps.organizations.api.schemas import (
    OrgCreateIn,
    OrgMemberOut,
    OrgOut,
    OrgRequestIn,
    OrgRequestOut,
    OrgUpdateIn,
)
from apps.organizations.models import Organization, OrganizationRequest
from apps.organizations.services.org_service import OrganizationService
from core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from core.permissions import JudgeLoomAuth

if TYPE_CHECKING:
    from django.http import HttpRequest

    from apps.accounts.models import User

router = Router(tags=["organizations"])


class OrgRequestRejectIn(Schema):
    """Payload for rejecting an organization request."""

    response: str


def _request_user(request: HttpRequest) -> User:
    """Resolve authenticated user from request context.

    Args:
        request: Incoming request object.

    Returns:
        Authenticated user instance.

    Raises:
        ValidationError: If request has no authenticated user.
    """

    user_model = cast("type[User]", get_user_model())
    auth_user = getattr(request, "auth", None)
    if isinstance(auth_user, user_model):
        return cast("User", auth_user)

    request_user = getattr(request, "user", None)
    if request_user is not None and isinstance(request_user, user_model) and request_user.is_authenticated:
        return cast("User", request_user)

    raise ValidationError("Authentication required.")


def _get_org_or_404(slug: str) -> Organization:
    """Get organization by slug or raise domain not found error."""

    organization = Organization.objects.filter(slug=slug).first()
    if organization is None:
        raise NotFoundError("Organization not found.")
    return organization


def _require_org_admin(org: Organization, user: User) -> None:
    """Require org admin or global staff privileges.

    Args:
        org: Organization object.
        user: Current user.

    Raises:
        PermissionDeniedError: If user lacks required permissions.
    """

    if user.is_staff or org.admins.filter(pk=user.pk).exists():
        return
    raise PermissionDeniedError("Organization admin permission required.")


def _org_out(org: Organization) -> OrgOut:
    """Convert organization model into API output payload."""

    return OrgOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        short_name=org.short_name,
        about=org.about,
        is_open=org.is_open,
        member_count=org.member_count,
        creation_date=org.creation_date,
    )


def _request_out(request_obj: OrganizationRequest) -> OrgRequestOut:
    """Convert request model into API output payload."""

    return OrgRequestOut(
        id=request_obj.id,
        user_id=request_obj.user_id,
        organization_id=request_obj.organization_id,
        status=request_obj.status,
        reason=request_obj.reason,
        response=request_obj.response,
        created_at=request_obj.created_at,
        reviewed_by_id=request_obj.reviewed_by_id,
        reviewed_at=request_obj.reviewed_at,
    )


@router.get("/", response=list[OrgOut])
def list_organizations(request: HttpRequest) -> list[OrgOut]:
    """List available organizations."""

    _ = request
    organizations = Organization.objects.all().order_by("name")
    return [_org_out(org) for org in organizations]


@router.post("/", response=OrgOut, auth=JudgeLoomAuth())
def create_organization(request: HttpRequest, payload: OrgCreateIn) -> OrgOut:
    """Create an organization; restricted to staff users."""

    user = _request_user(request)
    if not user.is_staff:
        raise PermissionDeniedError("Only staff can create organizations.")

    organization = OrganizationService.create_organization(
        name=payload.name,
        creator=user,
        slug=payload.slug,
        short_name=payload.short_name or "",
        about=payload.about or "",
        is_open=payload.is_open,
        access_code=payload.access_code,
    )
    return _org_out(organization)


@router.get("/{slug}", response=OrgOut)
def organization_detail(request: HttpRequest, slug: str) -> OrgOut:
    """Return organization detail by slug."""

    _ = request
    org = _get_org_or_404(slug)
    return _org_out(org)


@router.patch("/{slug}", response=OrgOut, auth=JudgeLoomAuth())
def update_organization(request: HttpRequest, slug: str, payload: OrgUpdateIn) -> OrgOut:
    """Update organization metadata; requires admin access."""

    user = _request_user(request)
    org = _get_org_or_404(slug)
    _require_org_admin(org, user)

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(org, field, value)
    if update_data:
        org.save(update_fields=[*update_data.keys(), "updated_at"])

    return _org_out(org)


@router.get("/{slug}/members", response=list[OrgMemberOut])
def organization_members(request: HttpRequest, slug: str) -> list[OrgMemberOut]:
    """List organization members."""

    _ = request
    org = _get_org_or_404(slug)
    members = OrganizationService.list_members(org)
    return [
        OrgMemberOut(
            id=member.id,
            username=member.username,
            display_name=member.display_name,
            rating=member.rating,
        )
        for member in members
    ]


@router.post("/{slug}/join", response=OrgRequestOut, auth=JudgeLoomAuth())
def join_organization(request: HttpRequest, slug: str, payload: OrgRequestIn) -> OrgRequestOut:
    """Create a membership request for an organization."""

    user = _request_user(request)
    org = _get_org_or_404(slug)

    if not org.is_open and not payload.reason and not org.access_code:
        raise ValidationError("Private organization requires a reason or access code process.")

    request_obj = OrganizationService.request_membership(
        org=org,
        user=user,
        reason=payload.reason or "",
    )
    return _request_out(request_obj)


@router.post("/{slug}/requests/{request_id}/approve", response=OrgRequestOut, auth=JudgeLoomAuth())
def approve_request(request: HttpRequest, slug: str, request_id: int) -> OrgRequestOut:
    """Approve an organization membership request."""

    user = _request_user(request)
    org = _get_org_or_404(slug)
    _require_org_admin(org, user)

    request_obj = OrganizationService.get_request_or_404(org, request_id)
    OrganizationService.approve_request(request_obj, reviewer=user)
    request_obj.refresh_from_db()

    return _request_out(request_obj)


@router.post("/{slug}/requests/{request_id}/reject", response=OrgRequestOut, auth=JudgeLoomAuth())
def reject_request(
    request: HttpRequest,
    slug: str,
    request_id: int,
    payload: OrgRequestRejectIn,
) -> OrgRequestOut:
    """Reject an organization membership request."""

    user = _request_user(request)
    org = _get_org_or_404(slug)
    _require_org_admin(org, user)

    request_obj = OrganizationService.get_request_or_404(org, request_id)
    OrganizationService.reject_request(request_obj, reviewer=user, response=payload.response)
    request_obj.refresh_from_db()

    return _request_out(request_obj)
