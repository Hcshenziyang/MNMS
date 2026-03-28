from django.urls import path

from .views import HealthCheckView, InterviewChatView, JDAnalyzeView, ResumeOptimizeView

urlpatterns = [
    path("health", HealthCheckView.as_view(), name="health"),
    path("jd/analyze", JDAnalyzeView.as_view(), name="jd-analyze"),
    path("resume/optimize", ResumeOptimizeView.as_view(), name="resume-optimize"),
    path("interview/chat", InterviewChatView.as_view(), name="interview-chat"),
]