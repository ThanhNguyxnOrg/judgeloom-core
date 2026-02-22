"""
JudgeLoom — Organization Tests
==================================

Unit tests for Organization model and member counting.
"""

from __future__ import annotations

import pytest

from tests.factories import OrganizationFactory, UserFactory


@pytest.mark.django_db
class TestOrganizationModel:
    """Tests for the Organization model."""

    def test_create_organization(self, organization):
        """Factory creates a valid open organization."""
        assert organization.pk is not None
        assert organization.is_open is True

    def test_organization_str(self, organization):
        """__str__ returns the organization name."""
        assert str(organization) == organization.name

    def test_member_count_empty(self, organization):
        """New organization has zero members."""
        assert organization.member_count == 0

    def test_member_count_after_join(self, organization, user):
        """Member count reflects joined users."""
        user.organizations.add(organization)
        assert organization.member_count == 1

    def test_multiple_members(self, organization):
        """Member count with multiple users."""
        u1 = UserFactory(username="orgmember1")
        u2 = UserFactory(username="orgmember2")
        u1.organizations.add(organization)
        u2.organizations.add(organization)
        assert organization.member_count == 2
