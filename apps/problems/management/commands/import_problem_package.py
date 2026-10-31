from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.problems.models import Problem
from apps.problems.services.package_service import PackageImportService


class Command(BaseCommand):
    """Import a versioned test-data package from a ZIP file."""

    help = "Import a ZIP test-data package for a problem."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("problem_code", type=str)
        parser.add_argument("zip_path", type=str)
        parser.add_argument(
            "--no-activate",
            action="store_true",
            help="Import the package without making it active.",
        )

    def handle(self, *args: object, **options: object) -> None:
        problem = Problem.objects.filter(code=str(options["problem_code"])).first()
        if problem is None:
            raise CommandError(f"Problem '{options['problem_code']}' was not found.")

        zip_path = Path(str(options["zip_path"]))
        if not zip_path.is_file():
            raise CommandError(f"ZIP file '{zip_path}' was not found.")

        with zip_path.open("rb") as archive:
            package = PackageImportService.import_zip(
                problem,
                archive,
                activate=not bool(options["no_activate"]),
            )

        state = "active" if package.is_active else "inactive"
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {problem.code} package v{package.version} "
                f"({package.sha256[:12]}, {state}) with {package.test_cases.count()} cases."
            )
        )
