from __future__ import annotations

from datetime import datetime

from ninja import Schema

class PostCreateIn(Schema):
    """Payload for creating a blog post."""

    title: str
    content: str
    visibility: str = "draft"
    summary: str | None = None
    is_organization_private: bool = False
    organization_ids: list[int] = []
    og_image: str | None = None

class PostUpdateIn(Schema):
    """Payload for updating a blog post."""

    title: str | None = None
    content: str | None = None
    summary: str | None = None
    visibility: str | None = None
    is_pinned: bool | None = None
    is_organization_private: bool | None = None
    organization_ids: list[int] | None = None
    og_image: str | None = None

class PostListOut(Schema):
    """Blog post list item response."""

    slug: str
    title: str
    summary: str
    visibility: str
    is_pinned: bool
    publish_date: datetime | None = None
    author_id: int

class PostDetailOut(PostListOut):
    """Detailed blog post response."""

    content: str
    is_organization_private: bool
    organizations: list[int]
    og_image: str | None = None

class CommentIn(Schema):
    """Payload for adding or editing a comment."""

    body: str
    parent_id: int | None = None

class CommentOut(Schema):
    """Serialized threaded comment node."""

    id: int
    post_id: int
    author_id: int
    parent_id: int | None = None
    path: str
    body: str
    visibility: str
    score: int
    created_at: datetime
    updated_at: datetime
    children: list["CommentOut"] = []

class CommentVoteIn(Schema):
    """Payload for a comment vote."""

    value: int

class NavigationOut(Schema):
    """Navigation menu node."""

    id: int
    key: str
    label: str
    url: str
    icon: str
    order: int
    is_external: bool
    children: list["NavigationOut"] = []
