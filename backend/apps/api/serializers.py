from rest_framework import serializers


class JDAnalyzeRequestSerializer(serializers.Serializer):
    jd_text = serializers.CharField(allow_blank=False, trim_whitespace=True)
    username = serializers.CharField(required=False, allow_blank=True)


class ResumeOptimizeRequestSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(min_value=1)
    resume_text = serializers.CharField(allow_blank=False, trim_whitespace=True)
    username = serializers.CharField(required=False, allow_blank=True)


class InterviewChatRequestSerializer(serializers.Serializer):
    topic = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    session_id = serializers.IntegerField(required=False, min_value=1)
    user_answer = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    username = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        topic = attrs.get("topic")
        session_id = attrs.get("session_id")
        user_answer = attrs.get("user_answer")

        if session_id and topic:
            raise serializers.ValidationError("session_id 和 topic 不能同时提供。")

        if not session_id and not topic:
            raise serializers.ValidationError("开始面试时必须提供 topic，或继续对话时提供 session_id。")

        if session_id and not user_answer:
            raise serializers.ValidationError("继续对话时必须提供 user_answer。")

        return attrs