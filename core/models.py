from django.db import models

class EmailSummary(models.Model):
    gmail_message_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    summary = models.TextField()
    is_urgent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.subject or "E-mail sem assunto"
