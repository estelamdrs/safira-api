from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework.decorators import api_view
from rest_framework.response import Response
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .models import EmailSummary, LLMPreferenceLog
from django.conf import settings
from core.services.llama_service import summarize_email_llama

from .services.google_auth import build_google_flow
from .services.gmail_service import (
    build_gmail_service,
    get_message_details,
    list_messages,
    get_or_create_label,
    list_gmail_labels,
    apply_label_to_message,
    send_reply,
)
from .services.gemini_service import GeminiService

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

    return redirect(f"{settings.FRONTEND_URL}/?gmail_connected=true")


def gmail_messages(request):
    creds_data = request.session.get("gmail_credentials")
    if not creds_data:
        return JsonResponse(
            {"error": "Conta Gmail não conectada."},
            status=401
        )

    service = build_gmail_service(creds_data)
    page_token = request.GET.get("page_token")

    results = list_messages(
        service,
        max_results=10,
        page_token=page_token,
    )

    messages = results["messages"]

    detailed_messages = [
        get_message_details(service, message["id"])
        for message in messages
    ]

    return JsonResponse({
        "total": len(detailed_messages),
        "messages": detailed_messages,
        "next_page_token": results["next_page_token"],
    })


@api_view(["GET"])
def gmail_status(request):
    creds_data = request.session.get("gmail_credentials")

    return Response({
        "connected": bool(creds_data)
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

    force_refresh = request.data.get("force_refresh", False)

    existing = EmailSummary.objects.filter(
        gmail_message_id=message_id
    ).first()

    if existing and not force_refresh:
        label_name = existing.category.capitalize()

        return Response({
            "id": existing.id,
            "gmail_message_id": existing.gmail_message_id,
            "subject": existing.subject,
            "analysis": {
                "resumo": existing.summary,
                "urgente": existing.is_urgent,
                "motivo_urgencia": existing.urgency_reason,
                "categoria": existing.category,
            },
            "suggested_label": label_name,
            "label_applied": False,
            "from_cache": True,
        })


    email = get_message_details(service, message_id)

    subject = email.get("subject") or "Sem assunto"
    body = email.get("body", "") or email.get("snippet", "")
    has_attachments = email.get("has_attachments", False)
    attachments = email.get("attachments", [])

    if not body and has_attachments:
        attachment_names = ", ".join(
            attachment.get("filename", "arquivo sem nome")
            for attachment in attachments
        )

        body = (
            "Este e-mail não possui conteúdo textual disponível, "
            "mas contém anexos. "
            f"Arquivos encontrados: {attachment_names}."
        )

    if not body:
        return Response(
            {"error": "Não foi possível encontrar conteúdo no e-mail."},
            status=400,
        )

    existing_labels = list_gmail_labels(service)
    existing_label_names = [label["name"] for label in existing_labels]

    result = GeminiService().summarize_email_gemini(
        subject,
        body,
        existing_label_names,
    )

    category = result.get("categoria", "outro")
    label_name = result.get("gmail_label") or category.capitalize()

    email_summary, _ = EmailSummary.objects.update_or_create(
        gmail_message_id=message_id,
        defaults={
            "subject": subject,
            "summary": result.get("resumo", ""),
            "category": category,
            "is_urgent": result.get("urgente", False),
            "urgency_reason": result.get("motivo_urgencia", ""),
        }
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
        "suggested_label": label_name,
        "label_applied": False,
        "from_cache": False
    })


@api_view(["POST"])
def gmail_disconnect(request):
    request.session.pop("gmail_credentials", None)
    request.session.pop("google_oauth_state", None)
    request.session.pop("google_code_verifier", None)

    return Response({
        "message": "Conta Gmail desconectada com sucesso.",
        "connected": False,
    })


@api_view(["POST"])
def apply_gmail_label(request, message_id):
    creds_data = request.session.get("gmail_credentials")

    if not creds_data:
        return Response(
            {"error": "Conta Gmail não conectada."},
            status=401,
        )

    label_name = request.data.get("label_name")

    if not label_name:
        return Response(
            {"error": "O campo 'label_name' é obrigatório."},
            status=400,
        )

    service = build_gmail_service(creds_data)

    label_id = get_or_create_label(service, label_name)
    apply_label_to_message(service, message_id, label_id)

    return Response({
        "message": "Marcador aplicado com sucesso.",
        "gmail_message_id": message_id,
        "gmail_label": label_name,
        "label_applied": True,
    })


@api_view(["POST"])
def suggest_gmail_reply(request, message_id):
    creds_data = request.session.get("gmail_credentials")

    if not creds_data:
        return Response(
            {"error": "Conta Gmail não conectada."},
            status=401,
        )

    service = build_gmail_service(creds_data)

    email = get_message_details(service, message_id)

    subject = email.get("subject", "")

    body = email.get("body", "") or email.get("snippet", "")

    if not body:
        return Response(
            {"error": "Não foi possível encontrar conteúdo textual no e-mail."},
            status=400,
        )

    result = GeminiService().suggest_email_reply_gemini(subject, body)

    return Response({
        "gmail_message_id": message_id,
        "subject": subject,
        "needs_reply": result.get("needs_reply", False),
        "suggested_reply": result.get("suggested_reply", ""),
    })


@api_view(["POST"])
def send_gmail_reply(request, message_id):
    creds_data = request.session.get("gmail_credentials")

    if not creds_data:
        return Response(
            {"error": "Conta Gmail não conectada."},
            status=401,
        )

    reply_body = request.data.get("reply")

    if not reply_body:
        return Response(
            {"error": "Resposta não informada."},
            status=400,
        )

    service = build_gmail_service(creds_data)

    email = get_message_details(service, message_id)

    to_email = email.get("from")
    subject = email.get("subject")

    send_reply(
        service=service,
        to_email=to_email,
        subject=subject,
        body=reply_body,
    )

    return Response({
        "success": True,
        "message": "Resposta enviada com sucesso.",
    })


@api_view(["POST"])
def summarize_email_llama_view(request):
    subject = request.data.get("subject", "")
    body = request.data.get("body", "")

    if not body:
        return Response(
            {"error": "O campo body é obrigatório."},
            status=400,
        )
    
    try:
        summary = summarize_email_llama(subject, body)

        return Response({
            "provider": "llama",
            "model": "llama3.2",
            "summary": summary,
        })
    except Exception as exc:
        return Response(
            {
                "error": "Erro ao gerar resumo com Llama.",
                "details": str(exc),
            },
            status=500,
        )


@api_view(["POST"])
def compare_email_llms(request):
    subject = request.data.get("subject", "")
    body = request.data.get("body", "")
    existing_labels = request.data.get("existing_labels", [])

    if not body:
        return Response(
            {"error": "O campo body é obrigatório."},
            status=400,
        )

    gemini_result = None
    llama_result = None
    errors = {}

    try:
        gemini_result = GeminiService().summarize_email_gemini(
            subject=subject,
            body=body,
            existing_labels=existing_labels,
        )
    except Exception as exc:
        errors["gemini"] = str(exc)

    try:
        llama_result = summarize_email_llama(
            subject=subject,
            body=body,
            existing_labels=existing_labels,
        )
    except Exception as exc:
        errors["llama"] = str(exc)

    try:
        llama_result = summarize_email_llama(
            subject=subject,
            body=body,
            existing_labels=existing_labels,
        )
    except Exception as exc:
        errors["llama"] = str(exc)

    return Response({
        "email": {
            "subject": subject,
        },
        "results": {
            "gemini": gemini_result,
            "llama": llama_result,
        },
        "errors": errors,
    })


@api_view(["POST"])
def register_llm_preference(request):
    email_id = request.data.get("email_id")
    provider = request.data.get("provider")
    action = request.data.get("action")

    if not all([email_id, provider, action]):
        return Response(
            {
                "error": (
                    "email_id, provider e action "
                    "são obrigatórios."
                )
            },
            status=400,
        )

    log = LLMPreferenceLog.objects.create(
        email_id=email_id,
        provider=provider,
        action=action,
    )

    return Response(
        {
            "id": log.id,
            "message": "Preferência registrada com sucesso.",
        }
    )


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
