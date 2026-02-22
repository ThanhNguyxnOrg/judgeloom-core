"""
JudgeLoom — createjudgeloomuser management command
=====================================================

Creates a new platform user with a specified role.  Supports
interactive and non-interactive modes for scripting.

Usage::

    python manage.py createjudgeloomuser admin_user --role admin --email admin@example.com
    python manage.py createjudgeloomuser setter1 --role problem_setter --password s3cret
"""

from __future__ import annotations

import getpass

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts.constants import UserRole
from apps.accounts.models import User


class Command(BaseCommand):
    """Create a JudgeLoom user with the specified role."""

    help = "Create a new JudgeLoom user with a specified role."

    def add_arguments(self, parser: CommandParser) -> None:
        """Define CLI arguments.

        Args:
            parser: Argument parser instance.
        """
        parser.add_argument("username", type=str, help="Username for the new user.")
        parser.add_argument(
            "--email",
            type=str,
            default="",
            help="Email address for the new user.",
        )
        parser.add_argument(
            "--role",
            type=str,
            choices=[c.value for c in UserRole],
            default=UserRole.PARTICIPANT,
            help="Role to assign (default: participant).",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=None,
            help="Password (prompted interactively if omitted).",
        )
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Grant superuser and staff privileges.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Execute the command.

        Args:
            *args: Positional arguments (unused).
            **options: Parsed CLI options.
        """
        username: str = options["username"]  # type: ignore[assignment]
        email: str = options["email"]  # type: ignore[assignment]
        role: str = options["role"]  # type: ignore[assignment]
        password: str | None = options["password"]  # type: ignore[assignment]
        is_superuser: bool = options["superuser"]  # type: ignore[assignment]

        if User.objects.filter(username=username).exists():
            raise CommandError(f"User '{username}' already exists.")

        if password is None:
            password = getpass.getpass("Password: ")
            password_confirm = getpass.getpass("Password (again): ")
            if password != password_confirm:
                raise CommandError("Passwords do not match.")

        if not password:
            raise CommandError("Password must not be empty.")

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            is_staff=is_superuser,
            is_superuser=is_superuser,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created user '{user.username}' with role '{role}'"
                f"{' (superuser)' if is_superuser else ''}."
            )
        )
