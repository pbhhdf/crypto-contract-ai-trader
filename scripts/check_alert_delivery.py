from __future__ import annotations

import hashlib
import hmac
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


RECEIVED: list[dict[str, Any]] = []
EMAIL_SENT: list[dict[str, Any]] = []
SECRET = "delivery-test-secret"


class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length)
        RECEIVED.append(
            {
                "path": self.path,
                "headers": dict(self.headers),
                "body": body.decode("utf-8"),
                "signature": self.headers.get("X-Trader-Alert-Signature", ""),
            }
        )
        self.send_response(204)
        self.end_headers()


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


class FakeSmtp:
    def __init__(self, host: str, port: int, timeout: float | None = None):
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def starttls(self) -> None:
        EMAIL_SENT.append({"event": "starttls"})

    def login(self, username: str, password: str) -> None:
        EMAIL_SENT.append({"event": "login", "username": username, "password_set": bool(password)})

    def send_message(self, message: Any) -> None:
        EMAIL_SENT.append(
            {
                "event": "send_message",
                "subject": message["Subject"],
                "to": message["To"],
                "from": message["From"],
                "body": message.get_content(),
            }
        )


def main() -> int:
    server.init_db()
    webhook = ThreadingHTTPServer(("127.0.0.1", 0), WebhookHandler)
    port = webhook.server_address[1]
    thread = threading.Thread(target=webhook.serve_forever, daemon=True)
    thread.start()

    original = {
        "enabled": server.ALERT_WEBHOOK_ENABLED,
        "url": server.ALERT_WEBHOOK_URL,
        "secret": server.ALERT_WEBHOOK_SECRET,
        "min": server.ALERT_WEBHOOK_MIN_SEVERITY,
        "telegram_enabled": server.ALERT_TELEGRAM_ENABLED,
        "telegram_token": server.ALERT_TELEGRAM_BOT_TOKEN,
        "telegram_chat": server.ALERT_TELEGRAM_CHAT_ID,
        "telegram_base": server.ALERT_TELEGRAM_API_BASE,
        "email_enabled": server.ALERT_EMAIL_ENABLED,
        "email_host": server.ALERT_EMAIL_SMTP_HOST,
        "email_port": server.ALERT_EMAIL_SMTP_PORT,
        "email_user": server.ALERT_EMAIL_SMTP_USERNAME,
        "email_password": server.ALERT_EMAIL_SMTP_PASSWORD,
        "email_from": server.ALERT_EMAIL_FROM,
        "email_to": server.ALERT_EMAIL_TO,
        "email_tls": server.ALERT_EMAIL_USE_TLS,
        "email_starttls": server.ALERT_EMAIL_STARTTLS,
        "smtp": server.smtplib.SMTP,
    }
    try:
        server.ALERT_WEBHOOK_ENABLED = True
        server.ALERT_WEBHOOK_URL = f"http://127.0.0.1:{port}/alert"
        server.ALERT_WEBHOOK_SECRET = SECRET
        server.ALERT_WEBHOOK_MIN_SEVERITY = "info"
        server.ALERT_TELEGRAM_ENABLED = True
        server.ALERT_TELEGRAM_BOT_TOKEN = "telegram-test-token"
        server.ALERT_TELEGRAM_CHAT_ID = "123456"
        server.ALERT_TELEGRAM_API_BASE = f"http://127.0.0.1:{port}"
        server.ALERT_EMAIL_ENABLED = True
        server.ALERT_EMAIL_SMTP_HOST = "smtp.test.local"
        server.ALERT_EMAIL_SMTP_PORT = 587
        server.ALERT_EMAIL_SMTP_USERNAME = "smtp-user"
        server.ALERT_EMAIL_SMTP_PASSWORD = "smtp-password"
        server.ALERT_EMAIL_FROM = "alerts@example.test"
        server.ALERT_EMAIL_TO = "trader@example.test"
        server.ALERT_EMAIL_USE_TLS = False
        server.ALERT_EMAIL_STARTTLS = True
        server.smtplib.SMTP = FakeSmtp
        result = server.send_test_alert_delivery()
    finally:
        server.ALERT_WEBHOOK_ENABLED = original["enabled"]
        server.ALERT_WEBHOOK_URL = original["url"]
        server.ALERT_WEBHOOK_SECRET = original["secret"]
        server.ALERT_WEBHOOK_MIN_SEVERITY = original["min"]
        server.ALERT_TELEGRAM_ENABLED = original["telegram_enabled"]
        server.ALERT_TELEGRAM_BOT_TOKEN = original["telegram_token"]
        server.ALERT_TELEGRAM_CHAT_ID = original["telegram_chat"]
        server.ALERT_TELEGRAM_API_BASE = original["telegram_base"]
        server.ALERT_EMAIL_ENABLED = original["email_enabled"]
        server.ALERT_EMAIL_SMTP_HOST = original["email_host"]
        server.ALERT_EMAIL_SMTP_PORT = original["email_port"]
        server.ALERT_EMAIL_SMTP_USERNAME = original["email_user"]
        server.ALERT_EMAIL_SMTP_PASSWORD = original["email_password"]
        server.ALERT_EMAIL_FROM = original["email_from"]
        server.ALERT_EMAIL_TO = original["email_to"]
        server.ALERT_EMAIL_USE_TLS = original["email_tls"]
        server.ALERT_EMAIL_STARTTLS = original["email_starttls"]
        server.smtplib.SMTP = original["smtp"]
        webhook.shutdown()

    deliveries = result.get("deliveries") or []
    if len(deliveries) < 3:
        return fail(f"expected webhook, telegram, and email delivery results: {result}")
    by_channel = {item.get("channel"): item for item in deliveries}
    for channel in ("webhook", "telegram", "email"):
        if by_channel.get(channel, {}).get("status") != "sent":
            return fail(f"{channel} delivery did not send: {by_channel.get(channel)}")
    if len(RECEIVED) < 2:
        return fail("webhook did not receive a request")
    received = next((item for item in RECEIVED if item["path"] == "/alert"), RECEIVED[0])
    expected_signature = "sha256=" + hmac.new(
        SECRET.encode("utf-8"),
        received["body"].encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if received["signature"] != expected_signature:
        return fail("webhook signature mismatch")
    payload = json.loads(received["body"])
    if payload.get("transition") != "test":
        return fail(f"unexpected payload transition: {payload}")
    telegram = next((item for item in RECEIVED if item["path"].endswith("/sendMessage")), None)
    if not telegram:
        return fail("telegram endpoint did not receive sendMessage")
    telegram_payload = json.loads(telegram["body"])
    if telegram_payload.get("chat_id") != "123456" or "告警" not in telegram_payload.get("text", ""):
        return fail(f"unexpected telegram payload: {telegram_payload}")
    sent_email = next((item for item in EMAIL_SENT if item.get("event") == "send_message"), None)
    if not sent_email or "trader@example.test" not in sent_email.get("to", ""):
        return fail(f"email delivery was not captured: {EMAIL_SENT}")

    print(
        json.dumps(
            {
                "ok": True,
                "channels": sorted(by_channel),
                "statuses": {channel: by_channel[channel].get("status") for channel in sorted(by_channel)},
                "webhook_status_code": by_channel["webhook"].get("status_code"),
                "received_transition": payload.get("transition"),
                "telegram_path": telegram["path"],
                "email_to": sent_email.get("to"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
