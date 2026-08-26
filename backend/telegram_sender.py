"""Sends messages/documents via the Telegram Bot API.

Generic on purpose — not report-specific like email_sender.py. Two users:
1. Negative-review alerts (worker/collectors -> a chat/channel)
2. Channel 2 of the marketing plan (marketing/article_pipeline/) posting
   articles to the Telegram channel — that's a Tier 1 (fully automatable)
   platform precisely because this is a plain Bot API call, no app review.

Falls back to DRY_RUN when TELEGRAM_BOT_TOKEN isn't set, same pattern as
email_sender.py — testable right now without a real bot.
"""

import json
import logging
import mimetypes
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

logger = logging.getLogger("dailyyolk.telegram")

API_BASE = "https://api.telegram.org/bot{token}/{method}"


class TelegramSendError(Exception):
    pass


def _api_url(method: str) -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("_api_url() called without TELEGRAM_BOT_TOKEN set — check dry-run guard first")
    return API_BASE.format(token=token, method=method)


def send_message(chat_id: str, text: str, parse_mode: str | None = None) -> None:
    """chat_id: numeric chat/user id, or "@channelusername" for a public channel."""
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        logger.info("[DRY RUN — TELEGRAM_BOT_TOKEN not set] Would send message to %s:\n%s", chat_id, text)
        return

    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    req = urllib.request.Request(
        _api_url("sendMessage"),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    _send(req)


def send_document(chat_id: str, file_path: Path, caption: str = "") -> None:
    """Uploads and sends a file (e.g. a PDF report) as a Telegram document."""
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        logger.info(
            "[DRY RUN — TELEGRAM_BOT_TOKEN not set] Would send document to %s: %s (caption: %s)",
            chat_id, file_path, caption,
        )
        return

    boundary = uuid.uuid4().hex
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"

    def _field(name: str, value: str) -> bytes:
        return (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n"
        ).encode("utf-8")

    body = bytearray()
    body += _field("chat_id", str(chat_id))
    if caption:
        body += _field("caption", caption)
    body += (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; "
        f"filename=\"{file_path.name}\"\r\nContent-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    body += file_path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        _api_url("sendDocument"),
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    _send(req)


def _send(req: urllib.request.Request) -> None:
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if not body.get("ok"):
                raise TelegramSendError(f"Telegram API returned ok=false: {body}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise TelegramSendError(f"Telegram API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise TelegramSendError(f"Failed to reach Telegram API: {exc}") from exc
