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
    # 基础支撑层
    # 三个接口公共父类，避免通用动作重复写
    agent = PhoenixAgent()

    @staticmethod  # 静态方法，用于封装与类相关但不依赖实例状态的工具逻辑，主要是为了代码组织和复用。
    def _get_user(request) -> User:  # _约定：不希望外部直接调用，-> User 表明函数返回User
        """用户登录信息提取"""
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
        """把数据库里的ChatMessage模型对象转换成前端或者LLM更容易理解的标准字典格式。"""
        return {
            "role": message.role,
            "content": message.content,
            "metadata": message.metadata or {},
        }

    @staticmethod
    def _cache_recent_session_messages(session: ChatSession) -> None:
        """把最近10调信息缓存到Redis【轻量用户隔离、活跃会话缓存】 TODO 检查后续从哪儿读取以及给函数的调用"""
        key = f"session:{session.id}:recent"  # session+id+最近十条信息
        recent = list(
            session.messages.order_by("-created_at").values("role", "content", "metadata")[:10]
        )
        cache.set(key, list(reversed(recent)), timeout=settings.SESSION_CACHE_SECONDS)  # 10min


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class JDAnalyzeView(BaseAgentView):
    """岗位分析视图函数"""
    def post(self, request):
        serializer = JDAnalyzeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # 参数校验
        user = self._get_user(request)  # 获取当前用户
        jd_text = serializer.validated_data["jd_text"]

        with transaction.atomic():  # 开启事务
            session = ChatSession.objects.create(user=user, topic="岗位分析")  # 创建会话主题表
            ChatMessage.objects.create(session=session, role="user", content=jd_text)  # 创建信息明细表

            result = self.agent.analyze_jd(jd_text)  # 调用agent

            assistant_message = ChatMessage.objects.create(  # 生成的结果一份进chatmessage
                session=session,
                role="assistant",
                content=result["content"],
                metadata=result.get("metadata", {}),
            )
            AnalysisResult.objects.create(  # 另一份结构化分析结果存进analysisresult
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
    """简历优化视图函数"""
    def post(self, request):
        serializer = ResumeOptimizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # 参数校验
        user = self._get_user(request)

        session_id = serializer.validated_data["session_id"]
        resume_text = serializer.validated_data["resume_text"]

        try:
            session = ChatSession.objects.get(id=session_id, user=user)  # 检查会话用户，同interview
        except ChatSession.DoesNotExist as exc:
            raise Http404("会话不存在或不属于当前用户") from exc

        latest_jd = AnalysisResult.objects.filter(user=user, source_type="jd").first()  # 基于最近一次JD分析结果
        if not latest_jd:
            return Response(
                {"detail": "请先完成一次岗位分析后再进行简历优化。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            ChatMessage.objects.create(session=session, role="user", content=resume_text)  # 用户消息写入

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
        serializer = InterviewChatRequestSerializer(data=request.data)  # 参数校验
        serializer.is_valid(raise_exception=True)
        user = self._get_user(request)  # 暂时没有JWT，会给会话绑定一个用户，按用户隔离

        session_id = serializer.validated_data.get("session_id")  # 会话ID，决定是否新对话
        topic = serializer.validated_data.get("topic")  # 面试话题/主题
        user_answer = serializer.validated_data.get("user_answer")  # 用户的回答

        if session_id:  # 已有的对话
            try:
                session = ChatSession.objects.get(id=session_id, user=user)  # 按照用户+sessionid双重验证
            except ChatSession.DoesNotExist as exc:
                raise Http404("会话不存在或不属于当前用户") from exc

            with transaction.atomic():  # with，将用户消息入库和AI回复入库当作一个原子操作处理，会话成功完整存储，失败回滚
                ChatMessage.objects.create(session=session, role="user", content=user_answer)  # 先存用户对话
                history = list(  # 查询会话历史
                    session.messages.values("role", "content", "metadata", "created_at").order_by("created_at")
                )
                result = self.agent.continue_interview(  # 调用Agent回答
                    topic=session.topic.replace("模拟面试-", "", 1),
                    user_answer=user_answer,
                    history=history,
                )
                assistant_message = ChatMessage.objects.create(  # 然后存入助手AI的回复
                    session=session,
                    role="assistant",
                    content=result["content"],
                    metadata=result.get("metadata", {}),
                )

            self._cache_recent_session_messages(session)  # 事务结束后，刷新缓存消息
            return Response(  # 返回响应
                {
                    "session_id": session.id,
                    "message": self._message_payload(assistant_message),
                },
                status=status.HTTP_200_OK,
            )

        topic = topic or "Python后端"  # 如果没有已有对话，先给主题
        with transaction.atomic():
            session = ChatSession.objects.create(user=user, topic=f"模拟面试-{topic}")  # 创建数据库会话主题表
            result = self.agent.start_interview(topic=topic, history=[])
            assistant_message = ChatMessage.objects.create(  # 创建数据库消息明细表
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