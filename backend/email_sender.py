"""Sends the finished report by email via Resend's HTTP API.

No SDK dependency (just stdlib urllib) — one less thing to install before
there's a server. Falls back to DRY_RUN when RESEND_API_KEY isn't set, so
the whole pipeline is testable right now without real credentials: it
logs what *would* have been sent instead of failing.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("repas.email")

RESEND_API_URL = "https://api.resend.com/emails"
FROM_ADDRESS = os.environ.get("EMAIL_FROM", "Repas <reports@repas.example>")


class EmailSendError(Exception):
    pass


def send_report_email(to: str, restaurant_name: str, pdf_path: Path | None, summary_text: str) -> None:
    """Sends the report. Attaches the PDF if we have one; otherwise sends
    the summary as plain text (e.g. while PDF conversion is unavailable,
    same as in this sandbox — see report/demo.py)."""

    api_key = os.environ.get("RESEND_API_KEY")
    subject = f"Отчёт о репутации: {restaurant_name}"

    if not api_key:
        logger.info(
            "[DRY RUN — RESEND_API_KEY not set] Would send to %s\nSubject: %s\nAttachment: %s\n---\n%s",
            to, subject, pdf_path if pdf_path and pdf_path.exists() else "(none)", summary_text,
        )
        return

    payload = {
        "from": FROM_ADDRESS,
        "to": [to],
        "subject": subject,
        "text": summary_text,
    }

    if pdf_path and pdf_path.exists():
        import base64
        payload["attachments"] = [{
            "filename": pdf_path.name,
            "content": base64.b64encode(pdf_path.read_bytes()).decode("ascii"),
        }]

    req = urllib.request.Request(
        RESEND_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status >= 300:
                raise EmailSendError(f"Resend returned HTTP {resp.status}")
    except urllib.error.URLError as exc:
        raise EmailSendError(f"Failed to reach Resend: {exc}") from exc
