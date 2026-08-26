"""Tests for backend/telegram_sender.py — only the DRY_RUN path (no
TELEGRAM_BOT_TOKEN) is exercised, since that's what's runnable without
real credentials/network.
"""

import logging

import pytest

from backend.telegram_sender import send_document, send_message


@pytest.fixture(autouse=True)
def no_bot_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)


def test_send_message_dry_run_does_not_raise():
    send_message(chat_id="@repas_channel", text="Hello")


def test_send_message_dry_run_logs(caplog):
    with caplog.at_level(logging.INFO, logger="repas.telegram"):
        send_message(chat_id="@repas_channel", text="Hello world")
    assert any("DRY RUN" in r.message for r in caplog.records)
    assert any("@repas_channel" in r.message for r in caplog.records)


def test_send_document_dry_run_does_not_raise(tmp_path):
    fake_pdf = tmp_path / "report.pdf"
    fake_pdf.write_bytes(b"%PDF-fake")
    send_document(chat_id="@repas_channel", file_path=fake_pdf, caption="New report")


def test_send_document_dry_run_logs(tmp_path, caplog):
    fake_pdf = tmp_path / "report.pdf"
    fake_pdf.write_bytes(b"%PDF-fake")
    with caplog.at_level(logging.INFO, logger="repas.telegram"):
        send_document(chat_id="@repas_channel", file_path=fake_pdf, caption="New report")
    assert any("DRY RUN" in r.message for r in caplog.records)
