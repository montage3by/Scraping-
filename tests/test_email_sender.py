"""Tests for backend/email_sender.py — only the DRY_RUN path (no
RESEND_API_KEY) is exercised, since that's what's actually runnable
without real credentials/network. The real-send path is covered by
inspection only (see module docstring's own reasoning for the fallback).
"""

from pathlib import Path

import pytest

from backend.email_sender import send_report_email


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)


def test_dry_run_does_not_raise_without_pdf():
    # Must not raise and must not attempt a real network call.
    send_report_email(to="owner@example.com", restaurant_name="Picasso", pdf_path=None, summary_text="Report body")


def test_dry_run_does_not_raise_with_nonexistent_pdf_path(tmp_path):
    fake_pdf = tmp_path / "does_not_exist.pdf"
    send_report_email(to="owner@example.com", restaurant_name="Picasso", pdf_path=fake_pdf, summary_text="Report body")


def test_dry_run_logs_would_send_message(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="dailyyolk.email"):
        send_report_email(to="owner@example.com", restaurant_name="Picasso", pdf_path=None, summary_text="Report body")
    assert any("DRY RUN" in r.message for r in caplog.records)
    assert any("owner@example.com" in r.message for r in caplog.records)
