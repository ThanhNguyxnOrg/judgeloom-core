from __future__ import annotations

import hmac
from typing import TYPE_CHECKING, Any

from django.utils import timezone

from apps.judge.models import Judge
from apps.submissions.constants import SubmissionResult, SubmissionStatus
from apps.submissions.services import SubmissionService

if TYPE_CHECKING:
    from collections.abc import Callable


class JudgeHandler:
    """Protocol handler for a single connected judge worker."""

    def __init__(self, transport: Callable[[dict[str, Any]], None] | None = None) -> None:
        """Initialize handler state.

        Args:
            transport: Optional outbound transport callback for judge messages.
        """
        self.transport = transport
        self.judge: Judge | None = None

    def on_connect(self, judge_name: str, auth_key: str) -> bool:
        """Authenticate and register a connecting judge worker.

        Args:
            judge_name: Judge identifier.
            auth_key: Shared secret from the bridge client.

        Returns:
            True when connection is accepted.
        """
        judge = Judge.objects.filter(name=judge_name).first()
        if judge is None:
            return False
        if not hmac.compare_digest(judge.auth_key, auth_key):
            return False

        judge.online = True
        if judge.start_time is None:
            judge.start_time = timezone.now()
        judge.save(update_fields=["online", "start_time", "updated_at"])

        self.judge = judge

        from apps.judge.bridge.bridge_manager import BridgeManager

        BridgeManager.get_instance().register_judge(self)
        return True

    def on_submission_result(self, submission_id: int, result_data: dict[str, Any]) -> None:
        """Handle final submission result callback from judge.

        Args:
            submission_id: Submission id.
            result_data: Final aggregate result payload.
        """
        SubmissionService.update_submission_result(submission_id=submission_id, result_data=result_data)

    def on_test_case_result(self, submission_id: int, case_data: dict[str, Any]) -> None:
        """Handle per-test-case progress callback from judge.

        Args:
            submission_id: Submission id.
            case_data: Single test-case payload.
        """
        SubmissionService.update_test_case_result(submission_id=submission_id, case_data=case_data)

    def on_compile_error(self, submission_id: int, error_msg: str) -> None:
        """Handle compile error callback and mark submission as failed.

        Args:
            submission_id: Submission id.
            error_msg: Compiler output message.
        """
        SubmissionService.update_submission_result(
            submission_id=submission_id,
            result_data={
                "status": SubmissionStatus.ERROR,
                "result": SubmissionResult.CE,
                "error_message": error_msg,
                "points": 0.0,
                "time_used": 0.0,
                "memory_used": 0,
            },
        )

    def on_disconnect(self) -> None:
        """Unregister judge and mark it offline."""
        if self.judge is not None:
            self.judge.online = False
            self.judge.save(update_fields=["online", "updated_at"])

        from apps.judge.bridge.bridge_manager import BridgeManager

        BridgeManager.get_instance().unregister_judge(self)

    def send_submission(self, submission_data: dict[str, Any]) -> bool:
        """Send serialized submission payload to this judge.

        Args:
            submission_data: Submission envelope for remote execution.

        Returns:
            True when payload was sent successfully.
        """
        if self.transport is None or self.judge is None:
            return False
        try:
            self.transport(submission_data)
            return True
        except Exception:
            return False
