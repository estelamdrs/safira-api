from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework.decorators import api_view
from rest_framework.response import Response
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .services.google_auth import build_google_flow
from .services.gmail_service import (
    build_gmail_service,
    get_message_details,
    list_messages,
)
from .services.gemini_service import summarize_email_with_gemini

# Gmail API

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

    service = build_gmail_service(creds_data)
    messages = list_messages(service, max_results=10)

    detailed_messages = [
        get_message_details(service, message["id"])
        for message in messages
    ]

    return JsonResponse({
        "total": len(detailed_messages),
        "messages": detailed_messages,
    })

# Gemini API

@api_view(["POST"])
def summarize_email(request):
    subject = request.data.get("subject", "")
    body = request.data.get("body", "")

    if not body:
        return Response(
            {"error": "O campo 'body' é obrigatório."},
            status=400,
        )

    result = summarize_email_with_gemini(subject, body)

    return Response({
        "subject": subject,
        "analysis": result,
    })
