"""
JudgeLoom — seed_problems management command
================================================

Creates sample problems for local development and testing.
Each problem includes a description and basic configuration.

Usage::

    python manage.py seed_problems
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.problems.constants import ProblemVisibility
from apps.problems.models import Problem

SAMPLE_PROBLEMS: list[dict[str, object]] = [
    {
        "code": "aplusb",
        "name": "A + B",
        "description": (
            "## A + B\n\n"
            "Given two integers **a** and **b**, compute their sum.\n\n"
            "### Input\n"
            "A single line containing two space-separated integers "
            "a and b (−10⁹ ≤ a, b ≤ 10⁹).\n\n"
            "### Output\n"
            "Print a single integer — the sum of a and b.\n\n"
            "### Example\n"
            "```\nInput:  3 5\nOutput: 8\n```"
        ),
        "time_limit": 1.0,
        "memory_limit": 262144,
        "points": 100.0,
        "visibility": ProblemVisibility.PUBLIC,
    },
    {
        "code": "helloworld",
        "name": "Hello, World!",
        "description": (
            "## Hello, World!\n\n"
            "Print the string `Hello, World!` (without quotes) to "
            "standard output.\n\n"
            "### Input\n"
            "No input.\n\n"
            "### Output\n"
            "A single line containing `Hello, World!`.\n\n"
            "### Example\n"
            "```\nInput:  (none)\nOutput: Hello, World!\n```"
        ),
        "time_limit": 1.0,
        "memory_limit": 262144,
        "points": 50.0,
        "visibility": ProblemVisibility.PUBLIC,
    },
    {
        "code": "fizzbuzz",
        "name": "FizzBuzz",
        "description": (
            "## FizzBuzz\n\n"
            "Given an integer **n**, for each integer from 1 to n:\n"
            "- Print `FizzBuzz` if divisible by both 3 and 5.\n"
            "- Print `Fizz` if divisible by 3 only.\n"
            "- Print `Buzz` if divisible by 5 only.\n"
            "- Otherwise, print the number itself.\n\n"
            "### Input\n"
            "A single integer n (1 ≤ n ≤ 100).\n\n"
            "### Output\n"
            "n lines, each containing the appropriate value.\n\n"
            "### Example\n"
            "```\nInput:  5\nOutput:\n1\n2\nFizz\n4\nBuzz\n```"
        ),
        "time_limit": 1.0,
        "memory_limit": 262144,
        "points": 150.0,
        "partial_score": False,
        "visibility": ProblemVisibility.PUBLIC,
    },
]


class Command(BaseCommand):
    """Seed the database with sample problems."""

    help = "Create sample problems for local development."

    def handle(self, *args: object, **options: object) -> None:
        """Execute the command.

        Args:
            *args: Positional arguments (unused).
            **options: Parsed CLI options.
        """
        created_count = 0

        for problem_data in SAMPLE_PROBLEMS:
            code = problem_data["code"]
            if Problem.objects.filter(code=code).exists():
                self.stdout.write(f"  Skipping '{code}' (already exists)")
                continue

            Problem.objects.create(**problem_data)
            created_count += 1
            self.stdout.write(f"  Created problem: {code}")

        self.stdout.write(
            self.style.SUCCESS(f"Seeded {created_count} problem(s).")
        )
