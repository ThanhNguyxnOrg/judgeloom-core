from __future__ import annotations

import zipfile
from io import BytesIO

import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.judge.services.judge_gateway_service import JudgeGatewayService
from apps.judge.services.judge_result_service import JudgeResultService
from apps.problems.services.package_service import PackageImportService
from apps.submissions.constants import SubmissionResult
from apps.submissions.consumers import SubmissionConsumer
from apps.submissions.services import SubmissionService


def make_zip(entries: dict[str, bytes], name: str = "package.zip") -> SimpleUploadedFile:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for path, data in entries.items():
            zf.writestr(path, data)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/zip")


def make_submission(user, problem, language):
    PackageImportService.import_zip(
        problem,
        make_zip({"data/01.in": b"1 2\n", "data/01.ans": b"3\n"}),
    )
    return SubmissionService.create_submission(
        user=user,
        problem=problem,
        language=language,
        source_code="print(1)",
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_submission_consumer_receives_case_update(user, problem, language, judge):
    submission = await database_sync_to_async(make_submission)(user, problem, language)
    job = await database_sync_to_async(JudgeGatewayService.claim_job)(judge, ["PY3"])
    assert job is not None

    communicator = WebsocketCommunicator(
        SubmissionConsumer.as_asgi(),
        f"/ws/submissions/{submission.pk}/",
    )
    communicator.scope["user"] = user
    communicator.scope["url_route"] = {"kwargs": {"submission_id": submission.pk}}
    connected, _ = await communicator.connect()
    assert connected is True

    try:
        await database_sync_to_async(JudgeResultService.record_cases)(
            job,
            judge,
            [
                {
                    "case_number": 1,
                    "status": SubmissionResult.AC,
                    "time_used": 0.1,
                    "memory_used": 1024,
                    "points": 100,
                    "total_points": 100,
                }
            ],
        )
        payload = await communicator.receive_json_from(timeout=2)
    finally:
        await communicator.disconnect()

    assert payload["submission_id"] == submission.pk
    assert payload["cases"][0]["case_number"] == 1
    assert payload["case_total"] == 1
    assert payload["case_passed"] == 1


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_submission_consumer_closes_on_user_revocation(user, problem, language):
    submission = await database_sync_to_async(make_submission)(user, problem, language)
    communicator = WebsocketCommunicator(
        SubmissionConsumer.as_asgi(),
        f"/ws/submissions/{submission.pk}/",
    )
    communicator.scope["user"] = user
    communicator.scope["url_route"] = {"kwargs": {"submission_id": submission.pk}}
    connected, _ = await communicator.connect()
    assert connected is True

    layer = get_channel_layer()
    await layer.group_send(f"user_{user.pk}", {"type": "force.disconnect"})
    output = await communicator.receive_output(timeout=2)
    assert output["type"] == "websocket.close"
    assert output["code"] == 4401
