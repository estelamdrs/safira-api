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
    class Provider(models.TextChoices):
        GEMINI = "gemini", "Gemini"
        LLAMA = "llama", "Llama"

    class ReplyQuality(models.TextChoices):
        NAO_USOU = "nao_usou", "Não usou"
        BOA = "boa", "Boa"
        REGULAR = "regular", "Regular"
        RUIM = "ruim", "Ruim"

    email_id = models.CharField(max_length=255)

    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
    )

    category_correct = models.BooleanField(
        null=True,
        blank=True,
    )

    label_applied = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    reply_quality = models.CharField(
        max_length=20,
        choices=ReplyQuality.choices,
        default=ReplyQuality.NAO_USOU,
    )

    reply_sent = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["email_id", "provider"],
                name="unique_llm_log_per_email_provider",
            )
        ]

    def __str__(self):
        return f"{self.email_id} - {self.provider}"
