import csv
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect
from rest_framework.decorators import api_view
from rest_framework.response import Response
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
from core.services.llama_service import summarize_email_llama, suggest_email_reply_llama

PUBLIC_PROVIDER_TO_INTERNAL = {
    "modelo_1": "gemini",
    "modelo_2": "llama",
}

INTERNAL_PROVIDER_TO_PUBLIC = {
    "gemini": "modelo_1",
    "llama": "modelo_2",
}

def resolve_provider(public_provider: str) -> str | None:
    return PUBLIC_PROVIDER_TO_INTERNAL.get(public_provider)


def public_provider_name(internal_provider: str) -> str:
    return INTERNAL_PROVIDER_TO_PUBLIC.get(internal_provider)


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
            {
                "error": (
                    "Sessão OAuth inválida ou expirada. "
                    "Inicie a autenticação novamente."
                )
            },
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

    request.session.modified = True
    request.session.save()

    session_key = request.session.session_key

    return redirect(
        f"{settings.FRONTEND_URL}/"
        f"?gmail_connected=true"
        f"&safira_session_key={session_key}"
    )


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
    public_provider = request.data.get("provider", "modelo_1")
    provider = resolve_provider(public_provider)

    if not provider:
        return Response(
            {"error": "Provider inválido. Use 'modelo_1' ou 'modelo_2'."},
            status=400,
        )
    
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

    if provider == "llama":
        result = suggest_email_reply_llama(subject, body)
    else:
        result = GeminiService().suggest_email_reply_gemini(subject, body)

    return Response({
        "provider": public_provider_name(provider),
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

    public_results = {
        public_provider_name("gemini"): gemini_result,
        public_provider_name("llama"): llama_result,
    }

    public_errors = {}

    if "gemini" in errors:
        public_errors[public_provider_name("gemini")] = errors["gemini"]

    if "llama" in errors:
        public_errors[public_provider_name("llama")] = errors["llama"]

    return Response({
        "email": {
            "subject": subject,
        },
        "results": public_results,
        "errors": public_errors,
    })


@api_view(["POST"])
def register_llm_preference(request):
    email_id = request.data.get("email_id")
    public_provider = request.data.get("provider")
    provider = resolve_provider(public_provider)

    if not provider:
        return Response(
            {"error": "Provider inválido. Use 'modelo_1' ou 'modelo_2'."},
            status=400,
        )

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

    log, _ = LLMPreferenceLog.objects.get_or_create(
        email_id=email_id,
        provider=provider,
    )

    if action == "category_ok":
        log.category_correct = True

    elif action == "category_not_ok":
        log.category_correct = False

    elif action == "apply_label":
        log.label_applied = True

    elif action == "reply_good":
        log.reply_quality = LLMPreferenceLog.ReplyQuality.BOA

    elif action == "reply_medium":
        log.reply_quality = LLMPreferenceLog.ReplyQuality.REGULAR

    elif action == "reply_bad":
        log.reply_quality = LLMPreferenceLog.ReplyQuality.RUIM

    elif action == "send_reply":
        log.reply_sent = True

    else:
        return Response(
            {"error": "Ação inválida."},
            status=400,
        )
    
    log.save()

    return Response({
        "id": log.id,
        "email_id": log.email_id,
        "provider": log.provider,
        "category_correct": log.category_correct,
        "label_applied": log.label_applied,
        "reply_quality": log.reply_quality,
        "reply_sent": log.reply_sent,
        "message": "Log atualizado com sucesso.",
    })


@api_view(["GET"])
def llm_preference_stats(request):
    result = {
        "gemini": {},
        "llama": {},
        "total": 0,
    }

    for provider in ["gemini", "llama"]:
        queryset = LLMPreferenceLog.objects.filter(provider=provider)

        result[provider] = {
            "total": queryset.count(),
            "category_correct": queryset.filter(category_correct=True).count(),
            "category_incorrect": queryset.filter(category_correct=False).count(),
            "label_applied": queryset.filter(label_applied=True).count(),
            "reply_sent": queryset.filter(reply_sent=True).count(),
            "reply_quality": {
                "nao_usou": queryset.filter(reply_quality="nao_usou").count(),
                "boa": queryset.filter(reply_quality="boa").count(),
                "regular": queryset.filter(reply_quality="regular").count(),
                "ruim": queryset.filter(reply_quality="ruim").count(),
            },
        }

        result["total"] += result[provider]["total"]

    return Response(result)


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


@api_view(["GET"])
def export_llm_preference_logs_csv(request):
    response = HttpResponse(
        content_type="text/csv; charset=utf-8",
    )

    response["Content-Disposition"] = (
        'attachment; filename="llm_preference_logs.csv"'
    )

    response.write("\ufeff")

    writer = csv.writer(response)

    writer.writerow([
        "id",
        "email_id",
        "modelo",
        "categoria_correta",
        "aplicacao_marcador",
        "qualidade_resposta",
        "envio_resposta",
    ])

    logs = LLMPreferenceLog.objects.all().order_by("id")

    for log in logs:
        writer.writerow([
            log.id,
            log.email_id,
            log.provider,
            "" if log.category_correct is None else int(log.category_correct),
            int(log.label_applied),
            log.reply_quality,
            int(log.reply_sent),
        ])

    return response
