from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework.decorators import api_view
from rest_framework.response import Response
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .models import EmailSummary

from .services.google_auth import build_google_flow
from .services.gmail_service import (
    build_gmail_service,
    get_message_details,
    list_messages,
    get_or_create_label,
    apply_label_to_message,
)
from .services.gemini_service import GeminiService

# Gmail API

@api_view(["GET"])
def health_check(request):
    return Response({
        "status": "ok",
        "message": "API do TCC funcionando com sucesso."
    })

def gmail_auth(request):
    request.session.pop("gmail_credentials", None)
    request.session.pop("google_oauth_state", None)
    request.session.pop("google_code_verifier", None)

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

    flow.fetch_token(
        authorization_response=request.build_absolute_uri(),
        code_verifier=code_verifier,
    )

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

@api_view(["POST"])
def summarize_gmail_message(request, message_id):
    creds_data = request.session.get("gmail_credentials")

    if not creds_data:
        return Response(
            {"error": "Conta Gmail não conectada."},
            status=401,
        )

    service = build_gmail_service(creds_data)

    existing = EmailSummary.objects.filter(
        gmail_message_id=message_id
    ).first()

    if existing:
        label_name = existing.category
        label_id = get_or_create_label(service, label_name)
        apply_label_to_message(service, message_id, label_id)

        return Response({
            "id": existing.id,
            "gmail_message_id": existing.gmail_message_id,
            "subject": existing.subject,
            "analysis": {
                "resumo": existing.summary,
                "urgente": existing.is_urgent,
                "motivo_urgencia": email_summary.urgency_reason,
                "categoria": existing.category,
            },
            "gmail_label": label_name,
            "from_cache": True,
        })


    email = get_message_details(service, message_id)

    subject = email.get("subject", "")
    body = email.get("body", "") or email.get("snippet", "")

    if not body:
        return Response(
            {"error": "Não foi possível encontrar conteúdo no e-mail."},
            status=400,
        )

    result = GeminiService().summarize_email_gemini(subject, body)

    category = result.get("categoria", "outro")
    label_name = category.capitalize()
    label_id = get_or_create_label(service, label_name)
    apply_label_to_message(service, message_id, label_id)

    email_summary = EmailSummary.objects.create(
        gmail_message_id=message_id,
        subject=subject,
        body=body,
        summary=result.get("resumo", ""),
        is_urgent=result.get("urgente", False),
        category=category,
        urgency_reason=result.get("motivo_urgencia", ""),
    )

    return Response({
        "id": email_summary.id,
        "gmail_message_id": email_summary.gmail_message_id,
        "subject": email_summary.subject,
        "analysis": {
            "resumo": email_summary.summary,
            "urgente": email_summary.is_urgent,
            "motivo_urgencia": email_summary.urgency_reason,
            "categoria": email_summary.category,
        },
        "gmail_label": label_name,
        "from_cache": False
    })

# Teste Gemini

@api_view(["POST"])
def summarize_email(request):
    subject = request.data.get("subject", "")
    body = request.data.get("body", "")

    if not body:
        return Response(
            {"error": "O campo 'body' é obrigatório."},
            status=400,
        )

    result = GeminiService().summarize_email_gemini(subject, body)

    email_summary = EmailSummary.objects.create(
        subject=subject,
        body=body,
        summary=result.get("resumo", ""),
        is_urgent=result.get("urgente", False),
    )

    return Response({
        "id": email_summary.id,
        "subject": email_summary.subject,
        "analysis": {
            "resumo": email_summary.summary,
            "urgente": email_summary.is_urgent,
        },
    })
