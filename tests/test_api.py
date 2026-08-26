"""Tests for the FastAPI submit/job endpoints (backend/main.py).

Uses FastAPI's TestClient (in-process, no real network/server) against a
temp SQLite db so this runs anywhere, including this sandbox.
"""

import pytest
from fastapi.testclient import TestClient

from backend import db, main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "queue.db")
    db.init_db()
    return TestClient(main.app)


def test_submit_valid_request_returns_job_id(client):
    resp = client.post("/api/submit", json={
        "restaurant_name": "Picasso",
        "city": "Tbilisi",
        "country": "GE",
        "email": "owner@example.com",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "job_id" in body and body["job_id"]
    assert len(body["platforms_planned"]) > 0


def test_submit_persists_job_as_queued(client):
    resp = client.post("/api/submit", json={
        "restaurant_name": "Picasso",
        "city": "Tbilisi",
        "country": "GE",
        "email": "owner@example.com",
    })
    job_id = resp.json()["job_id"]
    job = db.get_job(job_id)
    assert job["status"] == "queued"
    assert job["restaurant_name"] == "Picasso"
    assert job["competitor_hint"] is None


def test_submit_with_competitor_hint_is_stored(client):
    resp = client.post("/api/submit", json={
        "restaurant_name": "Picasso",
        "city": "Tbilisi",
        "country": "GE",
        "email": "owner@example.com",
        "competitor_hint": "Cafe Rio",
    })
    job = db.get_job(resp.json()["job_id"])
    assert job["competitor_hint"] == "Cafe Rio"


def test_submit_blank_competitor_hint_becomes_none(client):
    resp = client.post("/api/submit", json={
        "restaurant_name": "Picasso",
        "city": "Tbilisi",
        "country": "GE",
        "email": "owner@example.com",
        "competitor_hint": "   ",
    })
    assert resp.status_code == 200
    job = db.get_job(resp.json()["job_id"])
    assert job["competitor_hint"] is None


def test_submit_rejects_blank_restaurant_name(client):
    resp = client.post("/api/submit", json={
        "restaurant_name": "   ",
        "city": "Tbilisi",
        "country": "GE",
        "email": "owner@example.com",
    })
    assert resp.status_code == 422


def test_submit_rejects_blank_city(client):
    resp = client.post("/api/submit", json={
        "restaurant_name": "Picasso",
        "city": "",
        "country": "GE",
        "email": "owner@example.com",
    })
    assert resp.status_code == 422


def test_submit_rejects_invalid_email(client):
    resp = client.post("/api/submit", json={
        "restaurant_name": "Picasso",
        "city": "Tbilisi",
        "country": "GE",
        "email": "not-an-email",
    })
    assert resp.status_code == 422


def test_submit_rejects_malformed_country_code(client):
    resp = client.post("/api/submit", json={
        "restaurant_name": "Picasso",
        "city": "Tbilisi",
        "country": "Georgia",  # must be 2-letter ISO code
        "email": "owner@example.com",
    })
    assert resp.status_code == 422


def test_submit_lowercase_country_code_normalized(client):
    resp = client.post("/api/submit", json={
        "restaurant_name": "Picasso",
        "city": "Tbilisi",
        "country": "ge",
        "email": "owner@example.com",
    })
    assert resp.status_code == 200
    job = db.get_job(resp.json()["job_id"])
    assert job["country"] == "GE"


def test_submit_rejects_unmapped_country(client):
    resp = client.post("/api/submit", json={
        "restaurant_name": "Picasso",
        "city": "Nowhere",
        "country": "ZZ",  # not in config/countries.json
        "email": "owner@example.com",
    })
    assert resp.status_code == 422


def test_submit_missing_required_field(client):
    resp = client.post("/api/submit", json={
        "restaurant_name": "Picasso",
        "city": "Tbilisi",
        "country": "GE",
        # email missing
    })
    assert resp.status_code == 422


def test_get_job_returns_submitted_job(client):
    submit_resp = client.post("/api/submit", json={
        "restaurant_name": "Picasso",
        "city": "Tbilisi",
        "country": "GE",
        "email": "owner@example.com",
    })
    job_id = submit_resp.json()["job_id"]
    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id


def test_get_job_404_for_unknown_id(client):
    resp = client.get("/api/jobs/does-not-exist")
    assert resp.status_code == 404
