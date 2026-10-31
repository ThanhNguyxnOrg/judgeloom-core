from __future__ import annotations

from django.db import models


class SubmissionMode(models.TextChoices):
    """Whether a judge request is a scored submission or an ephemeral run."""

    SUBMIT = "submit", "Submit"
    RUN = "run", "Run"


class SubmissionStatus(models.TextChoices):
    """Lifecycle states for a submission in the judging pipeline."""

    QUEUED = "Q", "Queued (Q)"
    COMPILING = "CP", "Compiling (CP)"
    JUDGING = "JG", "Judging (JG)"
    COMPLETED = "CM", "Completed (CM)"
    ERROR = "ER", "Error (ER)"


class SubmissionResult(models.TextChoices):
    """Verdict codes returned by the judge."""

    AC = "AC", "Accepted (AC)"
    WA = "WA", "Wrong Answer (WA)"
    TLE = "TLE", "Time Limit Exceeded (TLE)"
    MLE = "MLE", "Memory Limit Exceeded (MLE)"
    RTE = "RTE", "Runtime Error (RTE)"
    CE = "CE", "Compilation Error (CE)"
    IR = "IR", "Invalid Return (IR)"
    OLE = "OLE", "Output Limit Exceeded (OLE)"
    IE = "IE", "Internal Error (IE)"
    PARTIAL = "PT", "Partial Score (PT)"


RESULT_CSS_CLASS: dict[str, str] = {
    "AC": "success",
    "PT": "info",
    "WA": "danger",
    "TLE": "warning",
    "MLE": "warning",
    "RTE": "danger",
    "CE": "secondary",
    "IR": "danger",
    "OLE": "warning",
    "IE": "dark",
}
