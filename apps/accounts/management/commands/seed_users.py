"""
JudgeLoom — seed_users management command
=============================================

Populates the database with sample users for local development.
Creates one user per role plus an admin superuser.

Usage::

    python manage.py seed_users
    python manage.py seed_users --password devpass123
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandParser

from apps.accounts.constants import UserRole
from apps.accounts.models import User

DEFAULT_PASSWORD = "judgeloom2025"

SEED_USERS: list[dict[str, str | bool]] = [
    {
        "username": "admin",
        "email": "admin@judgeloom.dev",
        "role": UserRole.ADMIN,
        "is_staff": True,
        "is_superuser": True,
    },
    {
        "username": "setter",
        "email": "setter@judgeloom.dev",
        "role": UserRole.PROBLEM_SETTER,
        "is_staff": True,
        "is_superuser": False,
    },
    {
        "username": "judge_user",
        "email": "judge@judgeloom.dev",
        "role": UserRole.JUDGE,
        "is_staff": True,
        "is_superuser": False,
    },
    {
        "username": "alice",
        "email": "alice@judgeloom.dev",
        "role": UserRole.PARTICIPANT,
        "is_staff": False,
        "is_superuser": False,
    },
    {
        "username": "bob",
        "email": "bob@judgeloom.dev",
        "role": UserRole.PARTICIPANT,
        "is_staff": False,
        "is_superuser": False,
    },
]


class Command(BaseCommand):
    """Seed the database with development users."""

    help = "Create sample users for local development."

    def add_arguments(self, parser: CommandParser) -> None:
        """Define CLI arguments.

        Args:
            parser: Argument parser instance.
        """
        parser.add_argument(
            "--password",
            type=str,
            default=DEFAULT_PASSWORD,
            help=f"Password for all seeded users (default: {DEFAULT_PASSWORD}).",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Execute the command.

        Args:
            *args: Positional arguments (unused).
            **options: Parsed CLI options.
        """
        password: str = options["password"]  # type: ignore[assignment]
        created_count = 0

        for user_data in SEED_USERS:
            username = user_data["username"]
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"  Skipping '{username}' (already exists)")
                continue

            User.objects.create_user(
                username=username,
                email=user_data["email"],
                password=password,
                role=user_data["role"],
                is_staff=user_data["is_staff"],
                is_superuser=user_data["is_superuser"],
            )
            created_count += 1
            self.stdout.write(f"  Created '{username}' ({user_data['role']})")

        self.stdout.write(
            self.style.SUCCESS(f"Seeded {created_count} user(s).")
        )
