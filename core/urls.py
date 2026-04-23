from django.urls import path
from .views import health_check, gmail_auth, gmail_callback, gmail_messages

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("gmail/auth/", gmail_auth, name="gmail_auth"),
    path("gmail/callback/", gmail_callback, name="gmail_callback"),
    path("gmail/messages/", gmail_messages, name="gmail_messages"),
]