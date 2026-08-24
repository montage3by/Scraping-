"""End-to-end smoke test: mock mentions -> analysis -> docx.
No network, no VPS needed — proves the report pipeline works before we
have a live collector feeding it. Run: python -m report.demo
"""

import json
import subprocess
import sys
from pathlib import Path

from collectors.models import CollectionResult, Mention
from report.analysis import build_report, to_json_dict

MOCK_RESULTS = [
    CollectionResult(
        platform="google_maps",
        restaurant_name="Picasso",
        country="RU",
        success=True,
        mentions=[
            Mention(platform="google_maps", rating=5, author="Nino K.", text="Amazing seafood, the staff were so friendly and the place was cozy."),
            Mention(platform="google_maps", rating=5, author="David M.", text="Best fish restaurant in town, fresh and delicious every time."),
            Mention(platform="google_maps", rating=2, author="Anna P.", text="Got sick after eating here, possible food poisoning. Disappointing."),
            Mention(platform="google_maps", rating=4, author="Levan T.", text="Great atmosphere, a bit overpriced but worth it."),
        ],
    ),
    CollectionResult(
        platform="tripadvisor",
        restaurant_name="Picasso",
        country="RU",
        success=False,
        mentions=[],
        error="TimeoutError: navigation timed out after 30000ms",
    ),
]

if __name__ == "__main__":
    report = build_report(MOCK_RESULTS, restaurant_name="Picasso", city="Kazan", country="RU")
    data = to_json_dict(report)

    out_dir = Path(__file__).parent / "_demo_output"
    out_dir.mkdir(exist_ok=True)
    json_path = out_dir / "report_data.json"
    docx_path = out_dir / "report.docx"

    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"Wrote {json_path}")

    result = subprocess.run(
        ["node", str(Path(__file__).parent / "build_docx.js"), str(json_path), str(docx_path)],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    # Final deliverable is a PDF — convert the intermediate .docx.
    # NOTE: LibreOffice conversion is broken in this sandbox (fails to load
    # *any* file, verified against a plain .txt) — not specific to our docx.
    # Keep the .docx around if conversion doesn't produce a PDF, instead of
    # deleting the one artifact that did work.
    soffice = Path("/mnt/skills/public/docx/scripts/office/soffice.py")
    convert = subprocess.run(
        [sys.executable, str(soffice), "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)],
        capture_output=True, text=True,
    )
    pdf_path = out_dir / "report.pdf"
    if convert.returncode == 0 and pdf_path.exists():
        docx_path.unlink()
        print(f"Wrote {pdf_path}")
    else:
        print(f"PDF conversion unavailable in this environment ({convert.stderr.strip()}); keeping {docx_path}", file=sys.stderr)
