from __future__ import annotations

from typing import TYPE_CHECKING

from ninja import Schema
from pydantic import Field

if TYPE_CHECKING:
    from datetime import datetime


class OrgCreateIn(Schema):
    """Payload for organization creation."""

    name: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=2, max_length=255)
    short_name: str | None = Field(default=None, max_length=64)
    about: str | None = None
    is_open: bool = True
    access_code: str | None = Field(default=None, max_length=64)


class OrgUpdateIn(Schema):
    """Payload for partial organization updates."""

    name: str | None = Field(default=None, min_length=2, max_length=255)
    short_name: str | None = Field(default=None, max_length=64)
    about: str | None = None
    is_open: bool | None = None
    access_code: str | None = Field(default=None, max_length=64)


class OrgOut(Schema):
    """Organization response payload."""

    id: int
    name: str
    slug: str
    short_name: str
    about: str
    is_open: bool
    member_count: int
    creation_date: datetime


class OrgMemberOut(Schema):
    """Organization member payload."""

    id: int
    username: str
    display_name: str
    rating: int


class OrgRequestIn(Schema):
    """Payload to request membership."""

    reason: str | None = None


class OrgRequestOut(Schema):
    """Organization membership request payload."""

    id: int
    user_id: int
    organization_id: int
    status: str
    reason: str
    response: str
    created_at: datetime
    reviewed_by_id: int | None
    reviewed_at: datetime | None
