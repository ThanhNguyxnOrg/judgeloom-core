from __future__ import annotations

import hashlib
import json
import math
import zipfile
from collections import defaultdict
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max

from apps.problems.models import Problem, ProblemPackage, ProblemTestCase
from core.exceptions import ValidationError

MAX_TEST_CASES = 200
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_VALIDATOR_SOURCE_BYTES = 256 * 1024
MAX_MANIFEST_POINTS = 1_000_000.0


class PackageImportService:
    """Validate and persist immutable problem test-data packages."""

    @staticmethod
    @transaction.atomic
    def import_zip(problem: Problem, archive_file: Any, *, activate: bool = True) -> ProblemPackage:
        """Import a ZIP archive and create a new package version.

        Args:
            problem: Problem receiving the package.
            archive_file: Uploaded ZIP file-like object.
            activate: Whether this package becomes the active version.

        Returns:
            Persisted package.

        Raises:
            ValidationError: If the archive or manifest is invalid.
        """

        archive_name = str(getattr(archive_file, "name", ""))
        if not archive_name.lower().endswith(".zip"):
            raise ValidationError("Test data must be a ZIP archive.")

        payload = archive_file.read()
        archive_file.seek(0)
        if len(payload) > MAX_ARCHIVE_BYTES:
            raise ValidationError(f"Archive exceeds maximum allowed size ({MAX_ARCHIVE_BYTES} bytes).")
        digest = hashlib.sha256(payload).hexdigest()

        existing = ProblemPackage.objects.filter(problem=problem, sha256=digest).first()
        if existing is not None:
            if activate:
                PackageImportService.activate(existing)
            return existing

        try:
            with zipfile.ZipFile(BytesIO(payload), "r") as zf:
                file_names = PackageImportService._safe_file_names(zf.namelist())
                if sum(info.file_size for info in zf.infolist()) > MAX_UNCOMPRESSED_BYTES:
                    raise ValidationError(f"Archive exceeds maximum uncompressed size ({MAX_UNCOMPRESSED_BYTES} bytes).")
                manifest = PackageImportService._read_manifest(zf, file_names)
                PackageImportService._validate_validator(manifest)
                cases = PackageImportService._manifest_cases(zf, file_names, manifest, problem)
                if cases is None:
                    cases = PackageImportService._file_cases(zf, file_names, problem)
        except zipfile.BadZipFile as exc:
            raise ValidationError("Invalid ZIP archive.") from exc

        if not cases:
            raise ValidationError("Archive must contain matching .in and .out/.ans files.")
        if len(cases) > MAX_TEST_CASES:
            raise ValidationError(f"Archive exceeds maximum allowed test cases ({MAX_TEST_CASES}).")

        PackageImportService._validate_groups(manifest, cases)
        manifest = PackageImportService._build_manifest(problem, manifest, cases)
        version = (problem.packages.aggregate(max_version=Max("version"))["max_version"] or 0) + 1

        if activate:
            problem.packages.filter(is_active=True).update(is_active=False)

        package = ProblemPackage(
            problem=problem,
            version=version,
            sha256=digest,
            manifest=manifest,
            size_bytes=len(payload),
            is_active=activate,
        )
        package.archive.save(f"{problem.code}-{digest[:12]}.zip", ContentFile(payload), save=False)
        package.save()

        ProblemTestCase.objects.bulk_create(
            [
                ProblemTestCase(
                    package=package,
                    order=index,
                    input_file=case["input"],
                    output_file=case["answer"],
                    input_sha256=case["input_sha256"],
                    output_sha256=case["answer_sha256"],
                    points=case["points"],
                    group=case["group"],
                )
                for index, case in enumerate(cases, start=1)
            ]
        )
        return package

    @staticmethod
    @transaction.atomic
    def activate(package: ProblemPackage) -> None:
        """Make one package active for its problem.

        Args:
            package: Package to activate.
        """

        ProblemPackage.objects.filter(problem=package.problem).exclude(pk=package.pk).update(is_active=False)
        package.is_active = True
        package.save(update_fields=["is_active", "updated_at"])

    @staticmethod
    def _safe_file_names(names: list[str]) -> list[str]:
        safe_names: list[str] = []
        for name in names:
            normalized = name.replace("\\", "/")
            path = PurePosixPath(normalized)
            if path.is_absolute() or ".." in path.parts or (path.parts and path.parts[0].endswith(":")):
                raise ValidationError(f"Invalid file path in archive: {name}")
            if name.endswith("/") or name.startswith("__MACOSX"):
                continue
            safe_names.append(normalized)
        return safe_names

    @staticmethod
    def _read_manifest(zf: zipfile.ZipFile, file_names: list[str]) -> dict[str, Any]:
        if "manifest.json" not in file_names:
            return {}
        try:
            payload = zf.read("manifest.json")
            manifest = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValidationError("Invalid manifest.json.") from exc
        if not isinstance(manifest, dict):
            raise ValidationError("manifest.json must be an object.")
        return manifest

    @staticmethod
    def _validate_validator(manifest: dict[str, Any]) -> None:
        """Validate optional inline Testlib validator metadata."""

        validator = manifest.get("validator")
        if validator is None:
            return
        if not isinstance(validator, dict):
            raise ValidationError("manifest validator must be an object.")

        validator_type = str(validator.get("type", "none")).lower()
        if validator_type not in {"none", "testlib"}:
            raise ValidationError(f"Unsupported manifest validator type: {validator_type}")

        if validator_type == "testlib":
            source = validator.get("source")
            if not isinstance(source, str) or not source.strip():
                raise ValidationError("A Testlib validator requires inline source.")
            if len(source.encode("utf-8")) > MAX_VALIDATOR_SOURCE_BYTES:
                raise ValidationError("Validator source exceeds the maximum allowed size.")

    @staticmethod
    def _manifest_cases(
        zf: zipfile.ZipFile,
        file_names: list[str],
        manifest: dict[str, Any],
        problem: Problem,
    ) -> list[dict[str, Any]] | None:
        raw_cases = manifest.get("cases")
        if not isinstance(raw_cases, list) or not raw_cases:
            return None

        cases: list[dict[str, Any]] = []
        for item in raw_cases:
            if not isinstance(item, dict):
                raise ValidationError("Each manifest case must be an object.")
            input_file = str(item.get("input", ""))
            answer_file = str(item.get("answer", item.get("output", "")))
            if not input_file or not answer_file:
                raise ValidationError("Manifest cases require input and answer paths.")
            if input_file not in file_names or answer_file not in file_names:
                raise ValidationError(f"Manifest case references a missing file: {input_file}, {answer_file}")
            points = item.get("points")
            try:
                parsed_points = None if points is None else float(points)
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"Manifest case points must be numeric: {points!r}") from exc
            if parsed_points is not None and (
                not math.isfinite(parsed_points)
                or parsed_points < 0
                or parsed_points > MAX_MANIFEST_POINTS
            ):
                raise ValidationError("Manifest case points must be finite and within the allowed range.")
            cases.append(
                {
                    "input": input_file,
                    "answer": answer_file,
                    "group": str(item.get("group") or "default"),
                    "points": parsed_points,
                    "input_sha256": hashlib.sha256(zf.read(input_file)).hexdigest(),
                    "answer_sha256": hashlib.sha256(zf.read(answer_file)).hexdigest(),
                }
            )
        return PackageImportService._apply_default_points(problem, cases)

    @staticmethod
    def _file_cases(
        zf: zipfile.ZipFile,
        file_names: list[str],
        problem: Problem,
    ) -> list[dict[str, Any]]:
        pairs: dict[str, dict[str, str]] = defaultdict(dict)
        for filename in file_names:
            path = PurePosixPath(filename)
            stem = path.stem
            extension = path.suffix.lower()
            if extension == ".in":
                if "in" in pairs[stem]:
                    raise ValidationError(f"Duplicate testcase stem detected: {stem}")
                pairs[stem]["in"] = filename
            elif extension in (".out", ".ans"):
                if "out" in pairs[stem]:
                    raise ValidationError(f"Duplicate testcase stem detected: {stem}")
                pairs[stem]["out"] = filename

        valid_cases: list[tuple[int, str, dict[str, str]]] = []
        for stem, parts in pairs.items():
            if "in" in parts and "out" in parts:
                digits = "".join(character for character in stem if character.isdigit())
                valid_cases.append((int(digits) if digits else 0, stem, parts))

        if not valid_cases:
            raise ValidationError("Archive must contain matching .in and .out/.ans files.")
        if len(valid_cases) > MAX_TEST_CASES:
            raise ValidationError(f"Archive exceeds maximum allowed test cases ({MAX_TEST_CASES}).")

        valid_cases.sort(key=lambda item: (item[0], item[1]))
        cases: list[dict[str, Any]] = []
        for _, _, parts in valid_cases:
            input_file = parts["in"]
            answer_file = parts["out"]
            cases.append(
                {
                    "input": input_file,
                    "answer": answer_file,
                    "group": "default",
                    "points": None,
                    "input_sha256": hashlib.sha256(zf.read(input_file)).hexdigest(),
                    "answer_sha256": hashlib.sha256(zf.read(answer_file)).hexdigest(),
                }
            )
        return PackageImportService._apply_default_points(problem, cases)

    @staticmethod
    def _apply_default_points(problem: Problem, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        missing = [case for case in cases if case["points"] is None]
        default_points = round(problem.points / len(cases), 2) if problem.points > 0 else 0.0
        for case in missing:
            case["points"] = default_points
        return cases

    @staticmethod
    def _validate_groups(manifest: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        raw_groups = manifest.get("groups")
        if raw_groups is None:
            raw_groups = []
        if not isinstance(raw_groups, list):
            raise ValidationError("manifest groups must be a list.")

        group_defs: dict[str, dict[str, Any]] = {}
        for item in raw_groups:
            if not isinstance(item, dict):
                raise ValidationError("Each manifest group must be an object.")
            group_id = str(item.get("id", "")).strip()
            if not group_id:
                raise ValidationError("Manifest group id is required.")
            if group_id in group_defs:
                raise ValidationError(f"Duplicate manifest group id: {group_id}")
            mode = str(item.get("mode", "sum"))
            if mode not in {"sum", "min"}:
                raise ValidationError(f"Unsupported manifest group mode: {mode}")
            try:
                points = float(item.get("points", 0) or 0)
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"Manifest group points must be numeric: {group_id}") from exc
            if not math.isfinite(points) or points < 0 or points > MAX_MANIFEST_POINTS:
                raise ValidationError(f"Manifest group points must be finite and within range: {group_id}")
            group_defs[group_id] = {"id": group_id, "mode": mode, "points": points}

        case_groups = {str(case["group"]) for case in cases}
        if group_defs:
            unknown = case_groups - set(group_defs)
            if unknown:
                raise ValidationError(f"Manifest cases reference unknown groups: {', '.join(sorted(unknown))}")
        elif case_groups != {"default"}:
            raise ValidationError("Manifest cases use custom groups but no group definitions were provided.")
        return group_defs

    @staticmethod
    def _build_manifest(problem: Problem, manifest: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
        result = dict(manifest)
        result.setdefault("schema", 1)
        result.setdefault("problem_code", problem.code)
        result.setdefault("time_limit", problem.time_limit)
        result.setdefault("memory_limit", problem.memory_limit)
        result.setdefault("checker", {"type": "exact"})
        result.setdefault("partial_score", bool(problem.partial_score))
        result.setdefault("short_circuit", bool(problem.short_circuit))
        result["cases"] = [
            {
                "id": str(index),
                "input": case["input"],
                "answer": case["answer"],
                "input_sha256": case["input_sha256"],
                "answer_sha256": case["answer_sha256"],
                "points": case["points"],
                "group": case["group"],
            }
            for index, case in enumerate(cases, start=1)
        ]
        if not result.get("groups"):
            result["groups"] = [
                {
                    "id": "default",
                    "points": round(sum(float(case["points"]) for case in cases), 2),
                    "mode": "sum",
                }
            ]
        return result
