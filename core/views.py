from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework.decorators import api_view
from rest_framework.response import Response
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .services.google_auth import build_google_flow


@api_view(["GET"])
def health_check(request):
    return Response({
        "status": "ok",
        "message": "API do TCC funcionando com sucesso."
    })

def gmail_auth(request):
    flow = build_google_flow()

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    request.session["google_oauth_state"] = state
    request.session["google_code_verifier"] = flow.code_verifier

    return redirect(authorization_url)

def gmail_callback(request):
    state = request.session.get("google_oauth_state")
    code_verifier = request.session.get("google_code_verifier")

    if not state or not code_verifier:
        return JsonResponse(
            {"error": "Sessão OAuth inválida ou expirada. Inicie a autenticação novamente."},
            status=400,
        )

    flow = build_google_flow()
    flow.state = state
    flow.code_verifier = code_verifier

    flow.fetch_token(authorization_response=request.build_absolute_uri())

    credentials = flow.credentials

    request.session["gmail_credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }

    return JsonResponse({"message": "Conta Gmail conectada com sucesso!"})

def gmail_messages(request):
    creds_data = request.session.get("gmail_credentials")
    if not creds_data:
        return JsonResponse(
            {"error": "Conta Gmail não conectada."},
            status=401
        )

    credentials = Credentials(**creds_data)
    service = build("gmail", "v1", credentials=credentials)

    results = service.users().messages().list(
        userId="me",
        maxResults=10
    ).execute()

    messages = results.get("messages", [])

    return JsonResponse({
        "total": len(messages),
        "messages": messages,
    })