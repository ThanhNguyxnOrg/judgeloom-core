from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import timedelta
from io import BytesIO, StringIO

import jwt
import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, RequestFactory, override_settings
from django.utils import timezone

from apps.accounts.services.auth_service import AuthService
from apps.content.constants import CommentVisibility, PostVisibility
from apps.content.models import Comment
from apps.content.services.comment_service import CommentService
from apps.content.services.post_service import PostService
from apps.contests.constants import ContestVisibility
from apps.contests.services.contest_service import ContestService
from apps.contests.services.ranking_service import RankingService
from apps.judge.admin import JudgeAdmin
from apps.judge.models import Judge, JudgeJobStatus
from apps.judge.services.judge_result_service import JudgeResultService
from apps.problems.constants import ProblemVisibility
from apps.problems.services.package_service import PackageImportService
from apps.submissions.constants import SubmissionMode, SubmissionResult, SubmissionStatus
from apps.submissions.models import Submission, SubmissionSource
from apps.submissions.services import SubmissionService
from core.exceptions import ContestAccessDeniedError, ContestError, SubmissionError, ValidationError
from core.middleware import RateLimitMiddleware
from core.permissions import JudgeLoomAuth
from tests.factories import (
    BlogPostFactory,
    ContestFactory,
    ContestParticipationFactory,
    JudgeFactory,
    ProblemFactory,
    SubmissionFactory,
    UserFactory,
)


def make_zip(entries: dict[str, bytes], name: str = "package.zip") -> SimpleUploadedFile:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for path, data in entries.items():
            zf.writestr(path, data)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/zip")


def import_package(problem):
    return PackageImportService.import_zip(
        problem,
        make_zip({"data/01.in": b"1 2\n", "data/01.ans": b"3\n"}),
    )


@pytest.mark.django_db
class TestContentVisibilityRegressions:
    def test_private_post_comments_are_not_visible(self, user):
        draft = BlogPostFactory(author=user, visibility=PostVisibility.DRAFT, publish_date=None)
        entry = Comment.objects.create(post=draft, author=user, body="secret discussion", path="001")

        assert PostService.can_view_post(AnonymousUser(), draft) is False
        client = Client()
        response = client.get(f"/api/content/posts/{draft.slug}/comments")

        assert response.status_code == 403
        assert entry.body.encode() not in response.content

    def test_hidden_comments_are_filtered_from_visible_post(self, user):
        post = BlogPostFactory(author=user)
        Comment.objects.create(post=post, author=user, body="visible", path="001")
        Comment.objects.create(
            post=post,
            author=user,
            body="hidden",
            path="002",
            visibility=CommentVisibility.HIDDEN,
        )

        tree = CommentService.get_comment_tree(post)
        bodies = [node["body"] for node in tree]
        assert bodies == ["visible"]


@pytest.mark.django_db
class TestContestAccessRegressions:
    def test_private_contest_join_requires_access_code(self, user):
        contest = ContestFactory(
            visibility=ContestVisibility.PRIVATE,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
        )

        with pytest.raises(ContestAccessDeniedError):
            ContestService.join_contest(contest, user)

        contest.access_code = "invite-only"
        contest.save(update_fields=["access_code"])
        participation = ContestService.join_contest(contest, user, access_code="invite-only")
        assert participation.user_id == user.id

    def test_virtual_participation_is_visibility_checked_and_deduplicated(self, user):
        contest = ContestFactory(
            visibility=ContestVisibility.PRIVATE,
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now() - timedelta(hours=1),
            time_limit=timedelta(hours=1),
            access_code="virtual-code",
        )

        with pytest.raises(ContestAccessDeniedError):
            ContestService.start_virtual(contest, user)

        first = ContestService.start_virtual(contest, user, access_code="virtual-code")
        second = ContestService.start_virtual(contest, user, access_code="virtual-code")
        assert first.pk == second.pk

    def test_frozen_ranking_ignores_client_frozen_false(self, user):
        contest = ContestFactory(
            visibility=ContestVisibility.PUBLIC,
            scoreboard_frozen_after=timedelta(minutes=1),
            start_time=timezone.now() - timedelta(minutes=10),
            end_time=timezone.now() + timedelta(hours=1),
        )
        ContestParticipationFactory(contest=contest, user=user)

        assert contest.is_frozen is True
        entries = RankingService.get_frozen_ranking(contest)
        assert entries[0]["format_data"] == {"frozen": True}

        client = Client()
        response = client.get(f"/api/contests/{contest.key}/ranking?frozen=false")
        assert response.status_code == 200
        assert response.json()[0]["format_data"] == {"frozen": True}

    def test_frozen_ranking_excludes_post_freeze_submissions(self, user, language):
        contest = ContestFactory(
            visibility=ContestVisibility.PUBLIC,
            scoreboard_frozen_after=timedelta(minutes=1),
            start_time=timezone.now() - timedelta(minutes=10),
            end_time=timezone.now() + timedelta(hours=1),
        )
        problem = ProblemFactory()
        ContestService.add_problem(contest, problem, label="A", points=100)
        import_package(problem)

        before = ContestParticipationFactory(contest=contest, user=user)
        after_user = UserFactory()
        after = ContestParticipationFactory(contest=contest, user=after_user)

        before_submission = ContestService.submit_to_contest(
            user=user,
            contest=contest,
            problem_code=problem.code,
            language=language,
            source_code="print(1)",
        )
        after_submission = ContestService.submit_to_contest(
            user=after_user,
            contest=contest,
            problem_code=problem.code,
            language=language,
            source_code="print(2)",
        )

        freeze_time = contest.start_time + contest.scoreboard_frozen_after
        Submission.objects.filter(pk=before_submission.pk).update(
            created_at=freeze_time - timedelta(minutes=1),
            status="CM",
            result="AC",
            points=100.0,
        )
        Submission.objects.filter(pk=after_submission.pk).update(
            created_at=freeze_time + timedelta(minutes=1),
            status="CM",
            result="AC",
            points=100.0,
        )

        entries = RankingService.get_frozen_ranking(contest)
        by_user = {entry["user_id"]: entry for entry in entries}
        assert by_user[before.user_id]["score"] == 100.0
        assert by_user[after.user_id]["score"] == 0.0
        assert by_user[before.user_id]["rank"] == 1

    def test_contest_submission_is_bound_and_honors_max_submissions(self, user, language):
        contest = ContestFactory(
            visibility=ContestVisibility.PUBLIC,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
        )
        problem = ProblemFactory()
        ContestService.add_problem(contest, problem, label="A", points=100, max_submissions=1)
        participation = ContestParticipationFactory(contest=contest, user=user)
        import_package(problem)

        submission = ContestService.submit_to_contest(
            user=user,
            contest=contest,
            problem_code=problem.code,
            language=language,
            source_code="print(1)",
        )
        assert submission.contest_participation_id == participation.id

        with pytest.raises(ContestError, match="limit"):
            ContestService.submit_to_contest(
                user=user,
                contest=contest,
                problem_code=problem.code,
                language=language,
                source_code="print(2)",
            )

    def test_non_participant_cannot_submit_to_contest(self, user, language):
        contest = ContestFactory(
            visibility=ContestVisibility.PUBLIC,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
        )
        problem = ProblemFactory()
        ContestService.add_problem(contest, problem, label="A", points=100)
        import_package(problem)

        with pytest.raises(ContestAccessDeniedError, match="Join"):
            ContestService.submit_to_contest(
                user=user,
                contest=contest,
                problem_code=problem.code,
                language=language,
                source_code="print(1)",
            )


@pytest.mark.django_db
class TestSubmissionVisibilityRegressions:
    def test_private_problem_submission_requires_author_or_contest_access(self, user, language):
        problem = ProblemFactory(visibility=ProblemVisibility.PRIVATE)
        import_package(problem)

        with pytest.raises(SubmissionError, match="access"):
            SubmissionService.create_submission(
                user=user,
                problem=problem,
                language=language,
                source_code="print(1)",
            )

        problem.authors.add(user)
        submission = SubmissionService.create_submission(
            user=user,
            problem=problem,
            language=language,
            source_code="print(1)",
        )
        assert submission.user_id == user.id

    def test_active_contest_participant_can_submit_contest_only_problem(self, user, language):
        contest = ContestFactory(
            visibility=ContestVisibility.PUBLIC,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
        )
        problem = ProblemFactory(visibility=ProblemVisibility.CONTEST_ONLY)
        ContestService.add_problem(contest, problem, label="A", points=100)
        ContestParticipationFactory(contest=contest, user=user)
        import_package(problem)

        submission = SubmissionService.create_submission(
            user=user,
            problem=problem,
            language=language,
            source_code="print(1)",
        )
        assert submission.user_id == user.id


@pytest.mark.django_db
class TestSubmissionPrivacyRegressions:
    def _submission(self, user, problem, language):
        submission = SubmissionFactory(
            user=user,
            problem=problem,
            language=language,
            status=SubmissionStatus.COMPLETED,
            result=SubmissionResult.AC,
            error_message="compile detail that must stay private",
        )
        SubmissionSource.objects.create(submission=submission, source_code="print(1)")
        return submission

    def test_public_metadata_hides_source_and_test_cases(self, user, problem, language):
        submission = self._submission(user, problem, language)
        submission = SubmissionService.set_submission_public(submission, True)
        anonymous = Client()

        detail = anonymous.get(f"/api/submissions/{submission.id}")
        assert detail.status_code == 200
        assert detail.json()["is_public"] is True
        assert detail.json()["error_message"] == ""

        assert anonymous.get(f"/api/submissions/{submission.id}/source").status_code == 401
        assert anonymous.get(f"/api/submissions/{submission.id}/test-cases").status_code == 401

        other = UserFactory()
        authenticated = Client()
        authenticated.force_login(other)
        assert authenticated.get(f"/api/submissions/{submission.id}/source").status_code == 403
        assert authenticated.get(f"/api/submissions/{submission.id}/test-cases").status_code == 403

    def test_share_token_is_metadata_only_and_revocable(self, user, problem, language):
        submission = self._submission(user, problem, language)
        owner = Client()
        owner.force_login(user)

        created = owner.post(f"/api/submissions/{submission.id}/share")
        assert created.status_code == 200
        token = created.json()["share_token"]

        anonymous = Client()
        shared = anonymous.get(f"/api/submissions/shared/{token}")
        assert shared.status_code == 200
        assert shared.json()["id"] == submission.id
        assert shared.json()["error_message"] == ""

        revoked = owner.delete(f"/api/submissions/{submission.id}/share")
        assert revoked.status_code == 200
        assert anonymous.get(f"/api/submissions/shared/{token}").status_code == 404

    def test_only_owner_or_staff_can_change_visibility(self, user, problem, language):
        submission = self._submission(user, problem, language)
        other = UserFactory()
        client = Client()
        client.force_login(other)

        response = client.patch(
            f"/api/submissions/{submission.id}/visibility",
            data='{"is_public": true}',
            content_type="application/json",
        )
        assert response.status_code == 403
        submission.refresh_from_db()
        assert submission.is_public is False

    def test_problem_author_can_read_private_submission_and_source(self, user, problem, language):
        submission = self._submission(user, problem, language)
        author = UserFactory()
        problem.authors.add(author)
        client = Client()
        client.force_login(author)

        assert client.get(f"/api/submissions/{submission.id}").status_code == 200
        source = client.get(f"/api/submissions/{submission.id}/source")
        assert source.status_code == 200
        assert source.json()["source_code"]

    def test_public_filter_lists_public_submissions(self, user, problem, language):
        public = self._submission(user, problem, language)
        public = SubmissionService.set_submission_public(public, True)
        private = self._submission(UserFactory(), problem, language)
        viewer = Client()
        viewer.force_login(UserFactory())

        response = viewer.get("/api/submissions/?public=true")
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()["items"]}
        assert public.id in ids
        assert private.id not in ids


@pytest.mark.django_db
class TestRunModeRegressions:
    def test_run_endpoint_creates_custom_job_and_hides_it_from_submission_list(self, user, problem, language):
        import_package(problem)
        client = Client()
        client.force_login(user)

        response = client.post(
            "/api/submissions/run",
            data=json.dumps(
                {
                    "problem_code": problem.code,
                    "language_id": language.id,
                    "source_code": "print(1)",
                    "stdin": "custom\n",
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "run"

        submission = Submission.objects.get(pk=payload["id"])
        assert submission.mode == SubmissionMode.RUN
        assert submission.custom_input == "custom\n"
        assert submission.judge_job.config["mode"] == "run"
        assert submission.judge_job.config["custom_input"] == "custom\n"

        listing = client.get("/api/submissions/")
        assert listing.status_code == 200
        assert listing.json()["items"] == []

    def test_run_finishes_without_points_or_user_stats(self, user, problem, language):
        import_package(problem)
        submission = SubmissionService.create_submission(
            user=user,
            problem=problem,
            language=language,
            source_code="print(1)",
            mode=SubmissionMode.RUN,
            custom_input="custom\n",
        )
        job = submission.judge_job
        judge = JudgeFactory()
        job.status = JudgeJobStatus.CLAIMED
        job.claimed_by = judge
        job.lease_expires_at = timezone.now() + timedelta(minutes=1)
        job.save(update_fields=["status", "claimed_by", "lease_expires_at"])

        JudgeResultService.record_cases(
            job,
            judge,
            [
                {
                    "case_number": 1,
                    "status": "AC",
                    "time_used": 0.1,
                    "memory_used": 10,
                    "points": 100.0,
                    "total_points": 100.0,
                }
            ],
        )
        JudgeResultService.finish(job, judge, {"status": "completed"})

        submission.refresh_from_db()
        user.refresh_from_db()
        assert submission.status == SubmissionStatus.COMPLETED
        assert submission.result == SubmissionResult.AC
        assert submission.points == 0.0
        assert submission.case_total == 1
        assert submission.case_passed == 1
        assert user.problem_count == 0


@pytest.mark.django_db
class TestTokenLifecycleRegressions:
    def test_revoke_tokens_invalidates_access_and_refresh(self, user):
        token = AuthService.generate_jwt_token(user)
        auth = JudgeLoomAuth()
        request = type("MockRequest", (), {})()

        assert auth.authenticate(request, token) is not None
        AuthService.revoke_tokens(user)
        assert auth.authenticate(request, token) is None

        with pytest.raises(ValidationError, match="revoked"):
            AuthService.refresh_jwt_token(token)

    def test_password_change_invalidates_existing_token(self, user):
        token = AuthService.generate_jwt_token(user)
        AuthService.change_password(user, "testpass123", "newtestpass123")

        assert JudgeLoomAuth().authenticate(type("MockRequest", (), {})(), token) is None

    def test_logout_endpoint_revokes_token(self, user):
        token = AuthService.generate_jwt_token(user)
        client = Client()

        response = client.post("/api/accounts/logout", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200

        response = client.get("/api/accounts/me", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 401

    def test_legacy_token_without_version_still_uses_zero_version(self, user):
        now = timezone.now()
        token = jwt.encode(
            {
                "user_id": str(user.pk),
                "type": "access",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(hours=1)).timestamp()),
            },
            "testing-secret-key-not-for-production",
            algorithm="HS256",
        )

        authenticated = JudgeLoomAuth().authenticate(type("MockRequest", (), {})(), token)
        assert authenticated is not None
        assert authenticated.pk == user.pk


@pytest.mark.django_db
class TestJudgeTokenStorageRegressions:
    def test_create_judge_token_does_not_store_plaintext(self):
        output = StringIO()
        call_command("create_judge_token", "no-plaintext-judge", stdout=output)

        judge = Judge.objects.get(name="no-plaintext-judge")
        token = output.getvalue().split("Token (shown once): ", 1)[1].strip()
        assert judge.auth_key == ""
        assert judge.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
        assert judge.token_prefix == token[:8]

    def test_judge_admin_excludes_credential_columns(self):
        assert "auth_key" in JudgeAdmin.exclude
        assert "token_hash" in JudgeAdmin.exclude


@pytest.mark.django_db
class TestRateLimitIdentityRegressions:
    def test_forwarded_for_is_ignored_by_default(self):
        request = RequestFactory().get(
            "/api/test/",
            REMOTE_ADDR="10.0.0.5",
            HTTP_X_FORWARDED_FOR="203.0.113.9",
        )
        with override_settings(TRUST_X_FORWARDED_FOR=False, TRUSTED_PROXY_IPS=[]):
            assert RateLimitMiddleware._get_client_ip(request) == "10.0.0.5"

    def test_forwarded_for_is_used_only_from_trusted_proxy(self):
        request = RequestFactory().get(
            "/api/test/",
            REMOTE_ADDR="10.0.0.5",
            HTTP_X_FORWARDED_FOR="203.0.113.9",
        )
        with override_settings(TRUST_X_FORWARDED_FOR=True, TRUSTED_PROXY_IPS=["10.0.0.5"]):
            assert RateLimitMiddleware._get_client_ip(request) == "203.0.113.9"

    def test_invalid_forwarded_for_falls_back_to_peer(self):
        request = RequestFactory().get(
            "/api/test/",
            REMOTE_ADDR="10.0.0.5",
            HTTP_X_FORWARDED_FOR="not-an-ip",
        )
        with override_settings(TRUST_X_FORWARDED_FOR=True, TRUSTED_PROXY_IPS=["10.0.0.5"]):
            assert RateLimitMiddleware._get_client_ip(request) == "10.0.0.5"
