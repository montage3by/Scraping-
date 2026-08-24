"""FastAPI backend for the MVP.

Right now this only accepts quiz submissions and queues them — there is no
worker yet that actually runs the collectors (that needs the VPS, per the
whole "why is Google Maps blocked from this sandbox" saga). Wiring a worker
loop that calls next_queued_job() + the collectors + report pipeline is the
next step once a server exists.
"""

import re
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, field_validator

sys.path.insert(0, str(Path(__file__).parents[1]))  # so `config.platforms` resolves when run standalone
from config.platforms import get_platforms_for_country  # noqa: E402

from . import db

app = FastAPI(title="Restaurant Reputation MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten once the landing page has a real domain
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


class SubmitRequest(BaseModel):
    restaurant_name: str
    city: str
    country: str
    email: EmailStr

    @field_validator("restaurant_name", "city")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("country")
    @classmethod
    def _country_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", v):
            raise ValueError("country must be a 2-letter ISO code, e.g. 'GE'")
        return v


class SubmitResponse(BaseModel):
    job_id: str
    platforms_planned: list[str]


@app.post("/api/submit", response_model=SubmitResponse)
def submit(payload: SubmitRequest) -> SubmitResponse:
    try:
        platforms = get_platforms_for_country(payload.country)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job_id = db.enqueue_job(
        restaurant_name=payload.restaurant_name,
        city=payload.city,
        country=payload.country,
        email=payload.email,
        platforms=platforms,
    )
    return SubmitResponse(job_id=job_id, platforms_planned=[p["name"] for p in platforms])


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


# Serve the landing page itself so `uvicorn backend.main:app` is a complete local demo.
_landing_dir = Path(__file__).parents[1] / "landing"
if _landing_dir.exists():
    app.mount("/", StaticFiles(directory=_landing_dir, html=True), name="landing")
