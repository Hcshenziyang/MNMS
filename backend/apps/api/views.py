from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agent_engine.agent import PhoenixAgent
from apps.core.models import AnalysisResult, ChatMessage, ChatSession

from .serializers import (
    InterviewChatRequestSerializer,
    JDAnalyzeRequestSerializer,
    ResumeOptimizeRequestSerializer,
)


class BaseAgentView(APIView):
    agent = PhoenixAgent()

    @staticmethod
    def _get_user(request) -> User:
        username = (
            request.headers.get("X-User", "").strip()
            or request.data.get("username", "").strip()
            or "demo_user"
        )
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@phoenix.local"},
        )
        return user

    @staticmethod
    def _message_payload(message: ChatMessage) -> dict[str, Any]:
        return {
            "role": message.role,
            "content": message.content,
            "metadata": message.metadata or {},
        }

    @staticmethod
    def _cache_recent_session_messages(session: ChatSession) -> None:
        key = f"session:{session.id}:recent"
        recent = list(
            session.messages.order_by("-created_at").values("role", "content", "metadata")[:10]
        )
        cache.set(key, list(reversed(recent)), timeout=settings.SESSION_CACHE_SECONDS)


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class JDAnalyzeView(BaseAgentView):
    def post(self, request):
        serializer = JDAnalyzeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self._get_user(request)
        jd_text = serializer.validated_data["jd_text"]

        with transaction.atomic():
            session = ChatSession.objects.create(user=user, topic="岗位分析")
            ChatMessage.objects.create(session=session, role="user", content=jd_text)

            result = self.agent.analyze_jd(jd_text)

            assistant_message = ChatMessage.objects.create(
                session=session,
                role="assistant",
                content=result["content"],
                metadata=result.get("metadata", {}),
            )
            AnalysisResult.objects.create(
                user=user,
                source_type="jd",
                source_text=jd_text,
                structured_data=result.get("metadata", {}),
            )

        self._cache_recent_session_messages(session)

        return Response(
            {
                "session_id": session.id,
                "message": self._message_payload(assistant_message),
            },
            status=status.HTTP_200_OK,
        )


class ResumeOptimizeView(BaseAgentView):
    def post(self, request):
        serializer = ResumeOptimizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self._get_user(request)

        session_id = serializer.validated_data["session_id"]
        resume_text = serializer.validated_data["resume_text"]

        try:
            session = ChatSession.objects.get(id=session_id, user=user)
        except ChatSession.DoesNotExist as exc:
            raise Http404("会话不存在或不属于当前用户") from exc

        latest_jd = AnalysisResult.objects.filter(user=user, source_type="jd").first()
        if not latest_jd:
            return Response(
                {"detail": "请先完成一次岗位分析后再进行简历优化。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            ChatMessage.objects.create(session=session, role="user", content=resume_text)

            result = self.agent.optimize_resume(
                jd_analysis=latest_jd.structured_data,
                resume_text=resume_text,
            )

            assistant_message = ChatMessage.objects.create(
                session=session,
                role="assistant",
                content=result["content"],
                metadata=result.get("metadata", {}),
            )
            AnalysisResult.objects.create(
                user=user,
                source_type="resume",
                source_text=resume_text,
                structured_data=result.get("metadata", {}),
            )

        self._cache_recent_session_messages(session)

        return Response(
            {
                "session_id": session.id,
                "message": self._message_payload(assistant_message),
            },
            status=status.HTTP_200_OK,
        )


class InterviewChatView(BaseAgentView):
    def post(self, request):
        serializer = InterviewChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self._get_user(request)

        session_id = serializer.validated_data.get("session_id")
        topic = serializer.validated_data.get("topic")
        user_answer = serializer.validated_data.get("user_answer")

        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=user)
            except ChatSession.DoesNotExist as exc:
                raise Http404("会话不存在或不属于当前用户") from exc

            with transaction.atomic():
                ChatMessage.objects.create(session=session, role="user", content=user_answer)
                history = list(
                    session.messages.values("role", "content", "metadata", "created_at").order_by("created_at")
                )
                result = self.agent.continue_interview(
                    topic=session.topic.replace("模拟面试-", "", 1),
                    user_answer=user_answer,
                    history=history,
                )
                assistant_message = ChatMessage.objects.create(
                    session=session,
                    role="assistant",
                    content=result["content"],
                    metadata=result.get("metadata", {}),
                )

            self._cache_recent_session_messages(session)
            return Response(
                {
                    "session_id": session.id,
                    "message": self._message_payload(assistant_message),
                },
                status=status.HTTP_200_OK,
            )

        topic = topic or "Python后端"
        with transaction.atomic():
            session = ChatSession.objects.create(user=user, topic=f"模拟面试-{topic}")
            result = self.agent.start_interview(topic=topic, history=[])
            assistant_message = ChatMessage.objects.create(
                session=session,
                role="assistant",
                content=result["content"],
                metadata=result.get("metadata", {}),
            )

        self._cache_recent_session_messages(session)

        return Response(
            {
                "session_id": session.id,
                "message": self._message_payload(assistant_message),
            },
            status=status.HTTP_200_OK,
        )