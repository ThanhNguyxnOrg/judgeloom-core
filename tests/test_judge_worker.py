import pytest

from apps.judge.models import Judge
from apps.submissions.constants import SubmissionStatus
from apps.submissions.models import Submission
from tests.factories import JudgeFactory, SubmissionFactory

pytestmark = pytest.mark.django_db


class TestJudgeWorkerDataFlow:
    def test_judge_factory_creates_online_worker(self):
        judge = JudgeFactory(online=True)

        assert isinstance(judge, Judge)
        assert judge.online is True

    def test_submission_can_be_assigned_to_judge(self):
        judge = JudgeFactory(online=True)
        submission = SubmissionFactory(status=SubmissionStatus.JUDGING, judged_on=judge)

        submission.refresh_from_db()
        assert isinstance(submission, Submission)
        assert submission.judged_on_id == judge.id
        assert submission.status == SubmissionStatus.JUDGING

    def test_submission_without_worker_remains_unassigned(self):
        submission = SubmissionFactory(status=SubmissionStatus.QUEUED, judged_on=None)

        submission.refresh_from_db()
        assert submission.judged_on is None
        assert submission.status == SubmissionStatus.QUEUED
