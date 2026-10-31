from __future__ import annotations

import hashlib
import secrets

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.judge.models import Judge


class Command(BaseCommand):
    """Create or rotate a judge worker token."""

    help = "Create a judge record and print its bearer token once."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("name", type=str)
        parser.add_argument(
            "--rotate",
            action="store_true",
            help="Replace the token for an existing judge.",
        )

    def handle(self, *args: object, **options: object) -> None:
        name = str(options["name"]).strip()
        if not name:
            raise CommandError("Judge name is required.")

        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        judge = Judge.objects.filter(name=name).first()
        if judge is not None and not options["rotate"]:
            raise CommandError(f"Judge '{name}' already exists; use --rotate.")
        if judge is None:
            judge = Judge(name=name)
        judge.auth_key = ""
        judge.token_hash = digest
        judge.token_prefix = token[:8]
        judge.capabilities = judge.capabilities or {}
        judge.save()
        self.stdout.write(self.style.SUCCESS(f"Judge: {name}"))
        self.stdout.write(f"Token (shown once): {token}")
