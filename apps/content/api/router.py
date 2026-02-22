from __future__ import annotations

from typing import Any

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from ninja import Router

from apps.content.api.schemas import (
    CommentIn,
    CommentOut,
    CommentVoteIn,
    NavigationOut,
    PostCreateIn,
    PostDetailOut,
    PostListOut,
    PostUpdateIn,
)
from apps.content.constants import PostVisibility
from apps.content.models import BlogPost, Comment, NavigationItem
from apps.content.services import CommentService, PostService
from core.exceptions import PermissionDeniedError

router = Router(tags=["content"])

def _require_authenticated(user: Any) -> None:
    """Ensure current user is authenticated.

    Args:
        user: Request user.

    Raises:
        PermissionDeniedError: If user is anonymous.
    """

    if not getattr(user, "is_authenticated", False):
        raise PermissionDeniedError("Authentication required.")

def _require_staff(user: Any) -> None:
    """Ensure current user is a staff member.

    Args:
        user: Request user.

    Raises:
        PermissionDeniedError: If user is not staff.
    """

    _require_authenticated(user)
    if not getattr(user, "is_staff", False):
        raise PermissionDeniedError("Staff access required.")

def _post_to_list_schema(post: BlogPost) -> PostListOut:
    """Convert a BlogPost model into PostListOut schema."""

    return PostListOut(
        slug=post.slug,
        title=post.title,
        summary=post.summary,
        visibility=post.visibility,
        is_pinned=post.is_pinned,
        publish_date=post.publish_date,
        author_id=post.author_id,
    )

def _post_to_detail_schema(post: BlogPost) -> PostDetailOut:
    """Convert a BlogPost model into PostDetailOut schema."""

    return PostDetailOut(
        slug=post.slug,
        title=post.title,
        summary=post.summary,
        visibility=post.visibility,
        is_pinned=post.is_pinned,
        publish_date=post.publish_date,
        author_id=post.author_id,
        content=post.content,
        is_organization_private=post.is_organization_private,
        organizations=list(post.organizations.values_list("id", flat=True)),
        og_image=post.og_image or None,
    )

@router.get("/posts", response=list[PostListOut])
def list_posts(request: Any, page: int = 1, page_size: int = 20) -> list[PostListOut]:
    """List published posts with simple pagination."""

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    page_size = min(page_size, 100)

    queryset = PostService.get_visible_posts(request.user).filter(visibility=PostVisibility.PUBLISHED)
    offset = (page - 1) * page_size
    posts = queryset[offset : offset + page_size]
    return [_post_to_list_schema(post) for post in posts]

@router.post("/posts", response=PostDetailOut)
def create_post(request: Any, payload: PostCreateIn) -> PostDetailOut:
    """Create a new blog post. Staff only."""

    _require_staff(request.user)

    post = PostService.create_post(
        title=payload.title,
        author=request.user,
        content=payload.content,
        visibility=payload.visibility,
    )
    update_kwargs: dict[str, Any] = {}
    if payload.summary is not None:
        update_kwargs["summary"] = payload.summary
    update_kwargs["is_organization_private"] = payload.is_organization_private
    if payload.og_image is not None:
        update_kwargs["og_image"] = payload.og_image
    if update_kwargs:
        post = PostService.update_post(post, **update_kwargs)

    if payload.organization_ids:
        post.organizations.set(payload.organization_ids)
    return _post_to_detail_schema(post)

@router.get("/posts/{slug}", response=PostDetailOut)
def get_post_detail(request: Any, slug: str) -> PostDetailOut:
    """Return post detail by slug."""

    post = PostService.get_post_by_slug(slug)
    visible_ids = PostService.get_visible_posts(request.user).values_list("id", flat=True)
    if post.id not in set(visible_ids):
        raise PermissionDeniedError("Post is not visible to this user.")
    return _post_to_detail_schema(post)

@router.patch("/posts/{slug}", response=PostDetailOut)
def update_post(request: Any, slug: str, payload: PostUpdateIn) -> PostDetailOut:
    """Update an existing post."""

    _require_authenticated(request.user)
    post = PostService.get_post_by_slug(slug)

    if post.author_id != request.user.id and not getattr(request.user, "is_staff", False):
        raise PermissionDeniedError("You do not have permission to update this post.")

    data = payload.dict(exclude_none=True)
    organization_ids = data.pop("organization_ids", None)
    post = PostService.update_post(post, **data)

    if organization_ids is not None:
        post.organizations.set(organization_ids)

    return _post_to_detail_schema(post)

@router.post("/posts/{slug}/publish", response=PostDetailOut)
def publish_post(request: Any, slug: str) -> PostDetailOut:
    """Publish a draft post."""

    _require_authenticated(request.user)
    post = PostService.get_post_by_slug(slug)

    if post.author_id != request.user.id and not getattr(request.user, "is_staff", False):
        raise PermissionDeniedError("You do not have permission to publish this post.")

    post = PostService.publish_post(post)
    return _post_to_detail_schema(post)

@router.get("/posts/{slug}/comments", response=list[CommentOut])
def get_post_comments(request: Any, slug: str) -> list[CommentOut]:
    """Return threaded comments for a post."""

    _ = request
    post = PostService.get_post_by_slug(slug)
    tree = CommentService.get_comment_tree(post)
    return [CommentOut(**node) for node in tree]

@router.post("/posts/{slug}/comments", response=CommentOut)
def add_comment(request: Any, slug: str, payload: CommentIn) -> CommentOut:
    """Add a new comment to a post."""

    _require_authenticated(request.user)
    post = PostService.get_post_by_slug(slug)
    parent = None
    if payload.parent_id is not None:
        parent = get_object_or_404(Comment, id=payload.parent_id)

    comment = CommentService.create_comment(
        post=post,
        author=request.user,
        body=payload.body,
        parent=parent,
    )
    return CommentOut(
        id=comment.id,
        post_id=comment.post_id,
        author_id=comment.author_id,
        parent_id=comment.parent_id,
        path=comment.path,
        body=comment.body,
        visibility=comment.visibility,
        score=comment.score,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        children=[],
    )

@router.patch("/comments/{comment_id}", response=CommentOut)
def edit_comment(request: Any, comment_id: int, payload: CommentIn) -> CommentOut:
    """Edit an existing comment. Owner only."""

    _require_authenticated(request.user)
    comment = get_object_or_404(Comment, id=comment_id)

    if comment.author_id != request.user.id and not getattr(request.user, "is_staff", False):
        raise PermissionDeniedError("You do not have permission to edit this comment.")

    updated = CommentService.edit_comment(comment, payload.body)
    return CommentOut(
        id=updated.id,
        post_id=updated.post_id,
        author_id=updated.author_id,
        parent_id=updated.parent_id,
        path=updated.path,
        body=updated.body,
        visibility=updated.visibility,
        score=updated.score,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
        children=[],
    )

@router.delete("/comments/{comment_id}", response=CommentOut)
def delete_comment(request: Any, comment_id: int) -> CommentOut:
    """Soft-delete an existing comment."""

    _require_authenticated(request.user)
    comment = get_object_or_404(Comment, id=comment_id)

    if comment.author_id != request.user.id and not getattr(request.user, "is_staff", False):
        raise PermissionDeniedError("You do not have permission to delete this comment.")

    deleted = CommentService.delete_comment(comment)
    return CommentOut(
        id=deleted.id,
        post_id=deleted.post_id,
        author_id=deleted.author_id,
        parent_id=deleted.parent_id,
        path=deleted.path,
        body=deleted.body,
        visibility=deleted.visibility,
        score=deleted.score,
        created_at=deleted.created_at,
        updated_at=deleted.updated_at,
        children=[],
    )

@router.post("/comments/{comment_id}/vote")
def vote_comment(request: Any, comment_id: int, payload: CommentVoteIn) -> dict[str, str]:
    """Vote on a comment with +1 or -1."""

    _require_authenticated(request.user)
    comment = get_object_or_404(Comment, id=comment_id)
    CommentService.vote_comment(comment, request.user, payload.value)
    return {"detail": "Vote recorded."}

@router.get("/navigation", response=list[NavigationOut])
def get_navigation(request: Any) -> list[NavigationOut]:
    """Return navigation tree for menu rendering."""

    _ = request
    items: QuerySet[NavigationItem] = NavigationItem.objects.select_related("parent").all().order_by(
        "order"
    )

    nodes: dict[int, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []

    for item in items:
        node = {
            "id": item.id,
            "key": item.key,
            "label": item.label,
            "url": item.url,
            "icon": item.icon,
            "order": item.order,
            "is_external": item.is_external,
            "children": [],
        }
        nodes[item.id] = node

        if item.parent_id is None:
            roots.append(node)
        else:
            parent_node = nodes.get(item.parent_id)
            if parent_node is None:
                roots.append(node)
            else:
                parent_node["children"].append(node)

    return [NavigationOut(**node) for node in roots]
