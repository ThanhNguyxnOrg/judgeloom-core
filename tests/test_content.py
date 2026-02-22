"""
JudgeLoom — Content Tests
============================

Unit tests for BlogPost model and visibility logic.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from apps.content.constants import PostVisibility
from tests.factories import BlogPostFactory


@pytest.mark.django_db
class TestBlogPostModel:
    """Tests for the BlogPost model."""

    def test_create_blog_post(self, blog_post):
        """Factory creates a valid published blog post."""
        assert blog_post.pk is not None
        assert blog_post.visibility == PostVisibility.PUBLISHED

    def test_blog_post_str(self, blog_post):
        """__str__ returns the post title."""
        assert str(blog_post) == blog_post.title

    def test_is_published(self, blog_post):
        """Published post with past date is published."""
        assert blog_post.is_published is True

    def test_is_draft(self):
        """Draft post reports is_draft correctly."""
        post = BlogPostFactory(visibility=PostVisibility.DRAFT, publish_date=None)
        assert post.is_draft is True
        assert post.is_published is False

    def test_is_not_published_future_date(self):
        """Published visibility with future date is not actually published."""
        from datetime import timedelta

        post = BlogPostFactory(
            visibility=PostVisibility.PUBLISHED,
            publish_date=timezone.now() + timedelta(days=1),
        )
        assert post.is_published is False
