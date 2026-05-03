from django.urls import path
from .views import (
    health_check,
    gmail_auth,
    gmail_callback,
    gmail_messages,
    summarize_email,
    summarize_gmail_message,
    gmail_status,
)

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("gmail/auth/", gmail_auth, name="gmail_auth"),
    path("gmail/callback/", gmail_callback, name="gmail_callback"),
    path("gmail/messages/", gmail_messages, name="gmail_messages"),
    path(
        "gmail/messages/<str:message_id>/summarize/",
        summarize_gmail_message,
        name="summarize_gmail_message",
    ),
    path("gmail/status/", gmail_status, name="gmail_status"),
    path("llm/summarize-email/", summarize_email, name="summarize_email"),
]