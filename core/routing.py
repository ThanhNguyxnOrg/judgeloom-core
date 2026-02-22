"""
JudgeLoom — WebSocket Routing
================================

Maps WebSocket URL paths to their Channels consumer classes.
Imported by ``config.asgi`` to register with the ProtocolTypeRouter.
"""

from __future__ import annotations

from django.urls import path

from apps.contests.consumers import ContestConsumer
from apps.judge.consumers import JudgeStatusConsumer
from apps.submissions.consumers import SubmissionConsumer

websocket_urlpatterns: list = [
    path("ws/submissions/<int:submission_id>/", SubmissionConsumer.as_asgi()),
    path("ws/contests/<str:contest_key>/", ContestConsumer.as_asgi()),
    path("ws/judges/", JudgeStatusConsumer.as_asgi()),
]
