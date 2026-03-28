from django.contrib.auth.models import User
from django.db import models


class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.CharField(max_length=255, help_text="会话主题, 如'简历优化'或'模拟面试-Python'")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.topic}"


class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    ROLE_CHOICES = [("user", "User"), ("assistant", "Assistant")]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    metadata = models.JSONField(null=True, blank=True, help_text="存储结构化数据, 如分析结果")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.session_id} - {self.role}"


class AnalysisResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    source_type = models.CharField(max_length=50, help_text="来源类型, 如'jd', 'resume'")
    source_text = models.TextField()
    structured_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.source_type}"