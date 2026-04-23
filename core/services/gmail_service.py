from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


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


def list_messages(service, max_results: int = 10):
    results = service.users().messages().list(
        userId="me",
        maxResults=max_results,
    ).execute()

    return results.get("messages", [])


def get_message_details(service, message_id: str) -> dict:
    message = service.users().messages().get(
        userId="me",
        id=message_id,
        format="metadata",
        metadataHeaders=["Subject", "From", "Date"],
    ).execute()

    payload = message.get("payload", {})
    headers = extract_headers(payload)

    return {
        "id": message.get("id"),
        "threadId": message.get("threadId"),
        "subject": headers.get("Subject"),
        "from": headers.get("From"),
        "date": headers.get("Date"),
        "snippet": message.get("snippet"),
    }