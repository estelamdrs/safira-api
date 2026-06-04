from django.db import models

class EmailSummary(models.Model):
    gmail_message_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    summary = models.TextField()
    is_urgent = models.BooleanField(default=False)
    urgency_reason = models.TextField(blank=True, default="")
    category = models.CharField(max_length=50, default="outro")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.subject or "E-mail sem assunto"

class LLMPreferenceLog(models.Model):
    PROVIDERS = [
        ("gemini", "Gemini"),
        ("llama", "Llama"),
    ]

    ACTIONS = [
        ("apply_label", "Apply Label"),
        ("suggest_reply", "Suggest Reply"),
        ("send_reply", "Send Reply"),
    ]

    email_id = models.CharField(max_length=255)

    provider = models.CharField(
        max_length=20,
        choices=PROVIDERS,
    )

    action = models.CharField(
        max_length=30,
        choices=ACTIONS,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return (
            f"{self.provider} - "
            f"{self.action} - "
            f"{self.email_id}"
        )
