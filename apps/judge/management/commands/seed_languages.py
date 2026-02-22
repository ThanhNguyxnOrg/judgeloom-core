"""
JudgeLoom — seed_languages management command
=================================================

Populates the database with the default set of programming languages
supported by JudgeLoom judge workers.

Usage::

    python manage.py seed_languages
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.judge.models import Language

LANGUAGES: list[dict[str, str | bool]] = [
    {
        "key": "C",
        "name": "C (GCC)",
        "short_name": "C",
        "ace_mode": "c_cpp",
        "pygments_name": "c",
        "extension": "c",
    },
    {
        "key": "CPP17",
        "name": "C++17 (GCC)",
        "short_name": "C++17",
        "ace_mode": "c_cpp",
        "pygments_name": "cpp",
        "extension": "cpp",
    },
    {
        "key": "CPP20",
        "name": "C++20 (GCC)",
        "short_name": "C++20",
        "ace_mode": "c_cpp",
        "pygments_name": "cpp",
        "extension": "cpp",
    },
    {
        "key": "JAVA",
        "name": "Java (OpenJDK)",
        "short_name": "Java",
        "ace_mode": "java",
        "pygments_name": "java",
        "extension": "java",
    },
    {
        "key": "PY3",
        "name": "Python 3",
        "short_name": "Python 3",
        "ace_mode": "python",
        "pygments_name": "python3",
        "extension": "py",
    },
    {
        "key": "PYPY3",
        "name": "PyPy 3",
        "short_name": "PyPy 3",
        "ace_mode": "python",
        "pygments_name": "python3",
        "extension": "py",
    },
    {
        "key": "JS",
        "name": "JavaScript (Node.js)",
        "short_name": "JS",
        "ace_mode": "javascript",
        "pygments_name": "javascript",
        "extension": "js",
    },
    {
        "key": "GO",
        "name": "Go",
        "short_name": "Go",
        "ace_mode": "golang",
        "pygments_name": "go",
        "extension": "go",
    },
    {
        "key": "RUST",
        "name": "Rust",
        "short_name": "Rust",
        "ace_mode": "rust",
        "pygments_name": "rust",
        "extension": "rs",
    },
    {
        "key": "KOTLIN",
        "name": "Kotlin (JVM)",
        "short_name": "Kotlin",
        "ace_mode": "kotlin",
        "pygments_name": "kotlin",
        "extension": "kt",
    },
    {
        "key": "RUBY",
        "name": "Ruby",
        "short_name": "Ruby",
        "ace_mode": "ruby",
        "pygments_name": "ruby",
        "extension": "rb",
    },
    {
        "key": "CSHARP",
        "name": "C# (.NET)",
        "short_name": "C#",
        "ace_mode": "csharp",
        "pygments_name": "csharp",
        "extension": "cs",
    },
]


class Command(BaseCommand):
    """Seed the database with default programming languages."""

    help = "Create or update the standard set of programming languages."

    def handle(self, *args: object, **options: object) -> None:
        """Execute the command.

        Args:
            *args: Positional arguments (unused).
            **options: Parsed CLI options.
        """
        created_count = 0
        updated_count = 0

        for lang_data in LANGUAGES:
            key = lang_data["key"]
            defaults = {k: v for k, v in lang_data.items() if k != "key"}
            _, created = Language.objects.update_or_create(
                key=key,
                defaults=defaults,
            )
            if created:
                created_count += 1
                self.stdout.write(f"  Created language: {key}")
            else:
                updated_count += 1
                self.stdout.write(f"  Updated language: {key}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created_count} created, {updated_count} updated."
            )
        )
