"""Worker: queue -> collectors -> report -> email.

Run as a loop (`python -m backend.worker`) once there's a server to run
Playwright on. Right now only google_maps has a real collector (see
collectors/registry.py) — every other platform in a job's plan comes back
as a clean "collector not implemented yet" result instead of silently
skipping it, so the report is honest about what it actually checked.

Requires `soffice` (LibreOffice) on PATH for PDF conversion — see Dockerfile.
Falls back to emailing the text summary alone when conversion isn't
available, so the pipeline still completes end to end either way.
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright

from backend import db
from backend.email_sender import send_report_email
from collectors.competitor_discovery import discover_competitors
from collectors.models import CollectionResult
from collectors.registry import get_collector
from report.analysis import build_report, render_text_summary, to_json_dict

logger = logging.getLogger("dailyyolk.worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

REPORT_DIR = Path(__file__).parents[1] / "report"
BUILD_DOCX_JS = REPORT_DIR / "build_docx.js"
# Plain "soffice" on PATH — works on any server with `apt install libreoffice`
# (see Dockerfile). Earlier versions of this file called a Claude-skill-specific
# helper script that only exists inside this dev sandbox and would have failed
# identically-but-for-a-different-reason on a real server — caught before deploy.
SOFFICE_BIN = "soffice"
JOB_OUTPUT_DIR = Path(__file__).parent / "_job_output"


async def collect_all(browser, restaurant_name: str, city: str, country: str, platforms: list[dict]) -> list[CollectionResult]:
    results: list[CollectionResult] = []
    for platform in platforms:
        platform_id = platform["id"]
        collector = get_collector(platform_id)
        if collector is None:
            results.append(CollectionResult(
                platform=platform_id,
                restaurant_name=restaurant_name,
                country=country,
                mentions=[],
                success=False,
                error="collector not implemented yet",
            ))
            continue
        result = await collector.collect(browser, restaurant_name, city, country)
        results.append(result)
    return results


def build_pdf(report_dict: dict, job_id: str) -> Path | None:
    """Returns the PDF path on success, None if conversion isn't available
    (matches report/demo.py's fallback — see module docstring)."""
    JOB_OUTPUT_DIR.mkdir(exist_ok=True)
    json_path = JOB_OUTPUT_DIR / f"{job_id}.json"
    docx_path = JOB_OUTPUT_DIR / f"{job_id}.docx"
    pdf_path = JOB_OUTPUT_DIR / f"{job_id}.pdf"

    json_path.write_text(json.dumps(report_dict, ensure_ascii=False, indent=2))

    build = subprocess.run(
        ["node", str(BUILD_DOCX_JS), str(json_path), str(docx_path)],
        capture_output=True, text=True,
    )
    if build.returncode != 0:
        logger.warning("build_docx.js failed: %s", build.stderr)
        return None

    convert = subprocess.run(
        [SOFFICE_BIN, "--headless", "--convert-to", "pdf", "--outdir", str(JOB_OUTPUT_DIR), str(docx_path)],
        capture_output=True, text=True,
    )
    if convert.returncode == 0 and pdf_path.exists():
        docx_path.unlink()
        return pdf_path

    logger.warning("PDF conversion unavailable (%s) — falling back to text-only email", convert.stderr.strip())
    return None


async def process_job(browser, job: dict) -> None:
    job_id = job["id"]
    logger.info("Processing job %s (%s, %s)", job_id, job["restaurant_name"], job["country"])
    db.set_job_status(job_id, "running")

    try:
        platforms = json.loads(job["platforms_json"])
        collection_results = await collect_all(
            browser, job["restaurant_name"], job["city"], job["country"], platforms
        )

        # Competitors run second, after the reputation collection is done —
        # "сначала анализ репутации, потом конкурентов". Best-effort: a
        # failure here (discover_competitors already swallows its own
        # exceptions) never blocks the report, it just ships without that section.
        competitors = await discover_competitors(
            browser, job["restaurant_name"], job["city"],
            competitor_hint=job.get("competitor_hint"),
        )

        report = build_report(
            collection_results,
            restaurant_name=job["restaurant_name"],
            city=job["city"],
            country=job["country"],
            competitors=competitors,
        )
        report_dict = to_json_dict(report)
        summary_text = render_text_summary(report)

        pdf_path = build_pdf(report_dict, job_id)

        send_report_email(
            to=job["email"],
            restaurant_name=job["restaurant_name"],
            pdf_path=pdf_path,
            summary_text=summary_text,
        )

        db.set_job_status(job_id, "done")
        logger.info("Job %s done (%d/%d sources succeeded)", job_id, len(report.sources_ok), len(platforms))

    except Exception as exc:  # noqa: BLE001 — a bad job must not kill the worker loop
        logger.exception("Job %s failed", job_id)
        db.set_job_status(job_id, "failed", error=str(exc))


async def run_forever(poll_interval: float = 5.0) -> None:
    db.init_db()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            logger.info("Worker started, polling every %.0fs", poll_interval)
            while True:
                job = db.next_queued_job()
                if job is None:
                    await asyncio.sleep(poll_interval)
                    continue
                await process_job(browser, job)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run_forever())
