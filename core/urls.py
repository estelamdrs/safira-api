from django.urls import path
from .views import (
    health_check,
    gmail_auth,
    gmail_callback,
    gmail_messages,
    summarize_email,
    summarize_gmail_message,
    gmail_status,
    gmail_disconnect,
    apply_gmail_label,
    suggest_gmail_reply,
    send_gmail_reply,
    summarize_email_llama_view,
    compare_email_llms,
    register_llm_preference
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
    path("gmail/disconnect/", gmail_disconnect, name="gmail_disconnect"),
    path(
        "gmail/messages/<str:message_id>/apply-label/",
        apply_gmail_label,
        name="apply_gmail_label",
    ),
    path(
        "gmail/messages/<str:message_id>/suggest-reply/",
        suggest_gmail_reply,
        name="suggest_gmail_reply",
    ),
    path(
        "gmail/messages/<str:message_id>/send-reply/",
        send_gmail_reply,
        name="send_gmail_reply",
    ),
    path(
        "llm/summarize-email-llama/",
        summarize_email_llama_view,
        name="summarize_email_llama"
    ),
    path(
        "llm/compare-email/",
        compare_email_llms,
        name="compare_email_llms"
    ),
    path(
        "llm/register-preference/",
        register_llm_preference,
        name="register_llm_preference"
    ),
]