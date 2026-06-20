"""
Gmail → Gemini → WhatsApp Bot
Fetches new emails, summarizes with Gemini AI, sends to WhatsApp via Green API.
Runs on GitHub Actions — no laptop needed.
"""

import os
import json
import base64
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from email import message_from_bytes
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google import genai
from google.genai import types

# ─── CONFIG (loaded from GitHub Secrets) ──────────────────────────────────────

GEMINI_API_KEY        = os.environ["GEMINI_API_KEY"]
GREENAPI_INSTANCE_ID  = os.environ["GREENAPI_INSTANCE_ID"]   # e.g. 1234567890
GREENAPI_TOKEN        = os.environ["GREENAPI_TOKEN"]          # your instance token
GREENAPI_PHONE        = os.environ["GREENAPI_PHONE"]          # e.g. 919876543210 (with country code, no +)

# Gmail OAuth tokens (stored as GitHub Secrets)
GMAIL_TOKEN_JSON      = os.environ["GMAIL_TOKEN_JSON"]        # Full contents of token.json

# ─── GMAIL AUTH ────────────────────────────────────────────────────────────────

def get_gmail_service():
    """Build Gmail service from token stored in environment."""
    token_data = json.loads(GMAIL_TOKEN_JSON)
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)

# ─── FETCH EMAILS ──────────────────────────────────────────────────────────────

def fetch_recent_emails(service, hours_ago=3):
    """Fetch emails received in the last N hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    epoch = int(since.timestamp())
    query = f"in:inbox after:{epoch}"

    results = service.users().messages().list(
        userId="me", q=query, maxResults=15
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        msg_data = service.users().messages().get(
            userId="me", id=msg["id"], format="raw"
        ).execute()

        raw = base64.urlsafe_b64decode(msg_data["raw"].encode("UTF-8"))
        email_msg = message_from_bytes(raw)

        subject = email_msg.get("Subject", "(No Subject)")
        sender  = email_msg.get("From", "Unknown")
        body    = extract_body(email_msg)

        emails.append({
            "subject": subject,
            "from":    sender,
            "body":    body[:1000]
        })

    return emails


def extract_body(email_msg):
    """Extract plain text from email."""
    body = ""
    if email_msg.is_multipart():
        for part in email_msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    break
                except Exception:
                    continue
    else:
        try:
            body = email_msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        except Exception:
            body = ""
    return body.strip()

# ─── SUMMARIZE WITH GEMINI ─────────────────────────────────────────────────────

def summarize_with_gemini(emails):
    """Send emails to Gemini Flash and get a WhatsApp-ready summary."""
    client = genai.Client(api_key=GEMINI_API_KEY)

    email_text = ""
    for i, e in enumerate(emails, 1):
        email_text += f"\nEmail {i}:\nFrom: {e['from']}\nSubject: {e['subject']}\nBody: {e['body']}\n"

    prompt = f"""You are a personal assistant summarizing emails for a student.

Here are {len(emails)} new email(s) from the last few hours:
{email_text}

Write ONE short paragraph (4-5 sentences max) that:
- Mentions who sent what and the key point of each email
- Flags anything urgent or that needs action
- Is casual and friendly, easy to read on a phone
- Starts with "📬 *Email Update:*"
- Ends with the total count like "(3 new emails)"

Be concise. No bullet points. Just one clean paragraph."""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    return response.text.strip()

# ─── SEND TO WHATSAPP VIA GREEN API ───────────────────────────────────────────

def send_whatsapp(message):
    """Send message to WhatsApp using Green API free tier."""
    url = (
        f"https://api.green-api.com/waInstance{GREENAPI_INSTANCE_ID}"
        f"/sendMessage/{GREENAPI_TOKEN}"
    )

    payload = json.dumps({
        "chatId": f"{GREENAPI_PHONE}@c.us",
        "message": message
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=15) as response:
        result = response.read().decode()
        print(f"[✓] Green API response: {result}")
    return result

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting email check...")

    # 1. Connect to Gmail
    print("[→] Connecting to Gmail...")
    service = get_gmail_service()

    # 2. Fetch recent emails
    print("[→] Fetching emails from last 3 hours...")
    emails = fetch_recent_emails(service, hours_ago=3)

    if not emails:
        print("[~] No new emails in the last 3 hours. Nothing to send.")
        return

    print(f"[✓] Found {len(emails)} email(s). Summarizing with Gemini...")

    # 3. Summarize
    summary = summarize_with_gemini(emails)
    print(f"\n--- Summary ---\n{summary}\n---------------\n")

    # 4. Send to WhatsApp
    print("[→] Sending to WhatsApp...")
    send_whatsapp(summary)
    print("[✓] Done! Message sent to your WhatsApp.")


if __name__ == "__main__":
    main()
