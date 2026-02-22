"""
JudgeLoom — Test conftest
============================

Shared pytest fixtures for unit and integration tests.
Provides pre-built model instances through factory_boy.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from tests.factories import (
    AdminUserFactory,
    BlogPostFactory,
    ContestFactory,
    ContestParticipationFactory,
    JudgeFactory,
    LanguageFactory,
    OrganizationFactory,
    ProblemFactory,
    PythonLanguageFactory,
    SubmissionFactory,
    TagFactory,
    TicketFactory,
    UserFactory,
)


@pytest.fixture
def user(db):
    """Create and return a standard participant user."""
    return UserFactory()


@pytest.fixture
def admin_user(db):
    """Create and return an admin superuser."""
    return AdminUserFactory()


@pytest.fixture
def language(db):
    """Create and return a Python 3 language."""
    return PythonLanguageFactory()


@pytest.fixture
def organization(db):
    """Create and return a test organization."""
    return OrganizationFactory()


@pytest.fixture
def problem(db):
    """Create and return a public test problem."""
    return ProblemFactory()


@pytest.fixture
def contest(db):
    """Create and return an active contest."""
    return ContestFactory(
        start_time=timezone.now() - timedelta(hours=1),
        end_time=timezone.now() + timedelta(hours=2),
    )


@pytest.fixture
def finished_contest(db):
    """Create and return a finished contest."""
    return ContestFactory(
        key="finished",
        start_time=timezone.now() - timedelta(hours=5),
        end_time=timezone.now() - timedelta(hours=1),
    )


@pytest.fixture
def participation(db, user, contest):
    """Create and return a contest participation for the default user."""
    return ContestParticipationFactory(user=user, contest=contest)


@pytest.fixture
def submission(db, user, problem, language):
    """Create and return a queued submission."""
    return SubmissionFactory(user=user, problem=problem, language=language)


@pytest.fixture
def judge(db):
    """Create and return an online judge worker."""
    return JudgeFactory()


@pytest.fixture
def tag(db):
    """Create and return a problem tag."""
    return TagFactory()


@pytest.fixture
def blog_post(db, user):
    """Create and return a published blog post."""
    return BlogPostFactory(author=user)


@pytest.fixture
def ticket(db, user):
    """Create and return an open ticket."""
    return TicketFactory(author=user)
