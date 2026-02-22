"""
JudgeLoom — Test Factories
=============================

Factory Boy factories for all major domain models.  Factories
produce minimal valid instances suitable for unit and integration
tests.  Each factory sets only required fields so tests can
override specific attributes cleanly.
"""

from __future__ import annotations

from datetime import timedelta

import factory
from django.utils import timezone

from apps.accounts.constants import UserRole
from apps.accounts.models import User
from apps.content.constants import PostVisibility
from apps.content.models import BlogPost
from apps.contests.constants import ContestFormat, ContestVisibility, ParticipationStatus
from apps.contests.models import Contest, ContestParticipation
from apps.judge.models import Judge, Language
from apps.organizations.models import Organization
from apps.problems.constants import ProblemVisibility
from apps.problems.models import Problem
from apps.ratings.models import Rating
from apps.submissions.constants import SubmissionResult, SubmissionStatus
from apps.submissions.models import Submission
from apps.tags.models import Tag
from apps.tickets.constants import TicketPriority, TicketStatus
from apps.tickets.models import Ticket


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating User instances."""

    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@judgeloom.test")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    role = UserRole.PARTICIPANT
    is_active = True


class AdminUserFactory(UserFactory):
    """Factory for creating admin superusers."""

    username = factory.Sequence(lambda n: f"admin{n}")
    role = UserRole.ADMIN
    is_staff = True
    is_superuser = True


class OrganizationFactory(factory.django.DjangoModelFactory):
    """Factory for creating Organization instances."""

    class Meta:
        model = Organization
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Organization {n}")
    short_name = factory.LazyAttribute(lambda obj: f"Org{obj.name.split()[-1]}")
    about = "A test organization."
    is_open = True


class LanguageFactory(factory.django.DjangoModelFactory):
    """Factory for creating Language instances."""

    class Meta:
        model = Language
        django_get_or_create = ("key",)

    key = factory.Sequence(lambda n: f"LANG{n}")
    name = factory.LazyAttribute(lambda obj: f"Language {obj.key}")
    short_name = factory.LazyAttribute(lambda obj: obj.key)
    ace_mode = "text"
    pygments_name = "text"
    extension = "txt"
    is_enabled = True


class PythonLanguageFactory(LanguageFactory):
    """Factory for creating a Python 3 language."""

    key = "PY3"
    name = "Python 3"
    short_name = "Python 3"
    ace_mode = "python"
    pygments_name = "python3"
    extension = "py"


class ProblemFactory(factory.django.DjangoModelFactory):
    """Factory for creating Problem instances."""

    class Meta:
        model = Problem
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"PROB{n}")
    name = factory.LazyAttribute(lambda obj: f"Problem {obj.code}")
    description = "A sample problem for testing."
    time_limit = 2.0
    memory_limit = 262144
    points = 100.0
    visibility = ProblemVisibility.PUBLIC


class ContestFactory(factory.django.DjangoModelFactory):
    """Factory for creating Contest instances."""

    class Meta:
        model = Contest
        django_get_or_create = ("key",)

    key = factory.Sequence(lambda n: f"contest{n}")
    name = factory.LazyAttribute(lambda obj: f"Contest {obj.key}")
    start_time = factory.LazyFunction(timezone.now)
    end_time = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=3))
    visibility = ContestVisibility.PUBLIC
    format_name = ContestFormat.DEFAULT
    is_rated = False


class ContestParticipationFactory(factory.django.DjangoModelFactory):
    """Factory for creating ContestParticipation instances."""

    class Meta:
        model = ContestParticipation

    contest = factory.SubFactory(ContestFactory)
    user = factory.SubFactory(UserFactory)
    status = ParticipationStatus.LIVE
    score = 0.0


class SubmissionFactory(factory.django.DjangoModelFactory):
    """Factory for creating Submission instances."""

    class Meta:
        model = Submission

    user = factory.SubFactory(UserFactory)
    problem = factory.SubFactory(ProblemFactory)
    language = factory.SubFactory(LanguageFactory)
    status = SubmissionStatus.QUEUED
    result = None
    points = 0.0


class JudgeFactory(factory.django.DjangoModelFactory):
    """Factory for creating Judge instances."""

    class Meta:
        model = Judge
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"judge-{n}")
    auth_key = factory.Sequence(lambda n: f"authkey-{n:032d}")
    online = True
    is_blocked = False


class RatingFactory(factory.django.DjangoModelFactory):
    """Factory for creating Rating instances."""

    class Meta:
        model = Rating

    user = factory.SubFactory(UserFactory)
    contest = factory.SubFactory(ContestFactory)
    participation = factory.SubFactory(ContestParticipationFactory)
    rank = 1
    rating_before = 1500
    rating_after = 1550
    performance = 1600


class TagFactory(factory.django.DjangoModelFactory):
    """Factory for creating Tag instances."""

    class Meta:
        model = Tag
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Tag {n}")
    code = factory.LazyAttribute(lambda obj: obj.name.lower().replace(" ", "-"))


class BlogPostFactory(factory.django.DjangoModelFactory):
    """Factory for creating BlogPost instances."""

    class Meta:
        model = BlogPost

    title = factory.Sequence(lambda n: f"Blog Post {n}")
    author = factory.SubFactory(UserFactory)
    content = "Sample blog post content for testing."
    visibility = PostVisibility.PUBLISHED
    publish_date = factory.LazyFunction(timezone.now)


class TicketFactory(factory.django.DjangoModelFactory):
    """Factory for creating Ticket instances."""

    class Meta:
        model = Ticket

    title = factory.Sequence(lambda n: f"Ticket {n}")
    author = factory.SubFactory(UserFactory)
    body = "Sample ticket body for testing."
    status = TicketStatus.OPEN
    priority = TicketPriority.MEDIUM
