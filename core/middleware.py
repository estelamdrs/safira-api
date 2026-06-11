from django.contrib.sessions.backends.db import SessionStore


class HeaderSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session_key = request.headers.get("X-Safira-Session-Key")

        if session_key:
            request.session = SessionStore(session_key=session_key)

        return self.get_response(request)