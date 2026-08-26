"""End-to-end test of the worker pipeline (queue -> collect -> analyze ->
report -> email) with collection and competitor discovery mocked out —
this sandbox has no network for real collectors, so this exercises
everything AROUND them: db, report building, docx/pdf build step, and the
DRY_RUN email path.

PDF conversion (soffice) is known-broken in this sandbox (confirmed by
directly running `soffice --headless --convert-to pdf` on a trivial .txt
file — it fails with "source file could not be loaded" regardless of
input). That's a sandbox limitation, not a code bug, so this test accepts
either outcome for the PDF step (real PDF, or the documented text-only
fallback) rather than asserting one — the real server is what will confirm
which path actually runs there.
"""

import json
import os

import pytest

from backend import db, worker
from collectors.models import CollectionResult, Competitor, Mention


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "queue.db")
    db.init_db()
    return db


@pytest.fixture
def temp_job_output(tmp_path, monkeypatch):
    out_dir = tmp_path / "_job_output"
    monkeypatch.setattr(worker, "JOB_OUTPUT_DIR", out_dir)
    return out_dir


@pytest.fixture(autouse=True)
def no_real_email(monkeypatch):
    # Force the DRY_RUN path in email_sender regardless of the real
    # environment's RESEND_API_KEY, so this test never makes a network call.
    monkeypatch.delenv("RESEND_API_KEY", raising=False)


async def _fake_collect_all(browser, restaurant_name, city, country, platforms):
    return [
        CollectionResult(
            platform="google_maps", restaurant_name=restaurant_name, country=country,
            mentions=[
                Mention(platform="google_maps", text="Great food, very friendly staff", rating=5.0),
                Mention(platform="google_maps", text="Slow service, food was cold", rating=2.0),
            ],
            success=True,
        ),
        CollectionResult(
            platform="tripadvisor", restaurant_name=restaurant_name, country=country,
            mentions=[], success=False, error="ERR_CONNECTION_RESET",
        ),
    ]


async def _fake_discover_competitors(browser, restaurant_name, city, max_competitors=2, competitor_hint=None):
    return [Competitor(name="Rival Bistro", rating=4.8, source_url="https://maps.example/rival")]


def test_process_job_completes_and_marks_done(temp_db, temp_job_output, monkeypatch):
    monkeypatch.setattr(worker, "collect_all", _fake_collect_all)
    monkeypatch.setattr(worker, "discover_competitors", _fake_discover_competitors)

    job_id = db.enqueue_job(
        restaurant_name="Picasso", city="Tbilisi", country="GE", email="owner@example.com",
        platforms=[{"id": "google_maps"}, {"id": "tripadvisor"}],
        competitor_hint=None,
    )
    job = db.get_job(job_id)
    assert job["status"] == "queued"

    import asyncio
    asyncio.run(worker.process_job(browser=None, job=job))

    finished = db.get_job(job_id)
    assert finished["status"] == "done", f"job ended in unexpected state: {finished}"
    assert finished["error"] is None


def test_process_job_writes_report_json_with_correct_ordering(temp_db, temp_job_output, monkeypatch):
    monkeypatch.setattr(worker, "collect_all", _fake_collect_all)
    monkeypatch.setattr(worker, "discover_competitors", _fake_discover_competitors)

    job_id = db.enqueue_job(
        restaurant_name="Picasso", city="Tbilisi", country="GE", email="owner@example.com",
        platforms=[{"id": "google_maps"}, {"id": "tripadvisor"}],
    )
    job = db.get_job(job_id)

    import asyncio
    asyncio.run(worker.process_job(browser=None, job=job))

    json_path = temp_job_output / f"{job_id}.json"
    assert json_path.exists()
    report = json.loads(json_path.read_text())

    assert report["restaurant_name"] == "Picasso"
    assert report["total_mentions"] == 2
    assert report["sources_ok"] == ["google_maps"]
    assert report["sources_failed"] == ["tripadvisor"]
    # own rating = avg(5.0, 2.0) = 3.5; competitor Rival Bistro at 4.8 is a
    # 1.3 delta, above the 0.3 alert threshold.
    assert report["own_avg_rating"] == 3.5
    assert report["competitors"] == [{"name": "Rival Bistro", "rating": 4.8, "source_url": "https://maps.example/rival"}]
    assert any("Rival Bistro" in a["message"] for a in report["alerts"])
    # competitors key must be the last top-level key (see to_json_dict's ordering contract)
    assert list(report.keys())[-1] == "competitors"


def test_process_job_pdf_step_does_not_crash_pipeline_either_way(temp_db, temp_job_output, monkeypatch):
    """PDF conversion may or may not succeed depending on the environment
    (see module docstring) — either way process_job must finish as 'done',
    never leave the job stuck or crash the worker."""
    monkeypatch.setattr(worker, "collect_all", _fake_collect_all)
    monkeypatch.setattr(worker, "discover_competitors", _fake_discover_competitors)

    job_id = db.enqueue_job(
        restaurant_name="Picasso", city="Tbilisi", country="GE", email="owner@example.com",
        platforms=[{"id": "google_maps"}],
    )
    job = db.get_job(job_id)

    import asyncio
    asyncio.run(worker.process_job(browser=None, job=job))

    finished = db.get_job(job_id)
    assert finished["status"] == "done"

    pdf_path = temp_job_output / f"{job_id}.pdf"
    docx_path = temp_job_output / f"{job_id}.docx"
    # On success, build_pdf() deletes the intermediate .docx. On failure it
    # deliberately leaves the .docx on disk (useful for debugging a broken
    # conversion) — see build_pdf()'s docstring. Either way the job must
    # still finish, which is asserted above; here we just confirm the two
    # outcomes are mutually exclusive, not which one happened.
    assert pdf_path.exists() != docx_path.exists()


def test_collect_all_reports_not_implemented_for_unregistered_platform(temp_db, temp_job_output):
    import asyncio
    results = asyncio.run(worker.collect_all(
        browser=None, restaurant_name="Picasso", city="Tbilisi", country="GE",
        platforms=[{"id": "totally_made_up_platform"}],
    ))
    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error == "collector not implemented yet"
