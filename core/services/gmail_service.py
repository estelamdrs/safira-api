import base64
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText

def build_gmail_service(creds_data: dict):
    credentials = Credentials(**creds_data)
    return build("gmail", "v1", credentials=credentials)

def extract_headers(payload: dict) -> dict:
    headers = payload.get("headers", [])
    header_map = {}

    for header in headers:
        name = header.get("name")
        value = header.get("value")
        if name and value:
            header_map[name] = value

    return header_map

def extract_attachments(payload: dict) -> list[dict]:
    attachments = []

    def walk_parts(part: dict):
        filename = part.get("filename")
        body = part.get("body", {})
        attachment_id = body.get("attachmentId")

        if filename and attachment_id:
            attachments.append({
                "filename": filename,
                "mime_type": part.get("mimeType"),
                "attachment_id": attachment_id,
                "size": body.get("size"),
            })

        for child_part in part.get("parts", []):
            walk_parts(child_part)

    walk_parts(payload)

    return attachments

def list_messages(service, max_results: int = 10, page_token: str = None):
    results = service.users().messages().list(
        userId="me",
        maxResults=max_results,
        pageToken=page_token,
    ).execute()

    return {
        "messages": results.get("messages", []),
        "next_page_token": results.get("nextPageToken"),
    }

def get_message_details(service, message_id: str) -> dict:
    message = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()

    payload = message.get("payload", {})
    headers = extract_headers(payload)
    attachments = extract_attachments(payload)

    return {
        "id": message.get("id"),
        "threadId": message.get("threadId"),
        "subject": headers.get("Subject") or "Sem assunto",
        "from": headers.get("From"),
        "date": headers.get("Date"),
        "snippet": message.get("snippet"),
        "has_attachments": len(attachments) > 0,
        "attachments": attachments,
    }

def get_or_create_label(service, label_name: str) -> str:
    labels = service.users().labels().list(userId="me").execute().get("labels", [])

    for label in labels:
        if label["name"].lower() == label_name.lower():
            return label["id"]

    try:
        created_label = service.users().labels().create(
            userId="me",
            body={
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        ).execute()

        return created_label["id"]

    except HttpError:
        labels = service.users().labels().list(userId="me").execute().get("labels", [])

        for label in labels:
            if label["name"].lower() == label_name.lower():
                return label["id"]

        raise

def list_gmail_labels(service):
    response = service.users().labels().list(userId="me").execute()
    labels = response.get("labels", [])

    return [
        {
            "id": label.get("id"),
            "name": label.get("name"),
            "type": label.get("type"),
        }
        for label in labels
        if label.get("type") == "user"
    ]
    
def apply_label_to_message(service, message_id: str, label_id: str):
    return service.users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "addLabelIds": [label_id],
        }
    ).execute()

def send_reply(service, to_email: str, subject: str, body: str):
    message = MIMEText(body)

    message["to"] = to_email
    message["subject"] = f"Re: {subject}"

    raw_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    return service.users().messages().send(
        userId="me",
        body={
            "raw": raw_message,
        },
    ).execute()