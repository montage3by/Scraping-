# Playwright's official image ships Chromium + all OS deps preinstalled —
# avoids the exact "browser executable not found" dance we hit in the dev
# sandbox (see collectors/google_maps.py's module docstring).
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

# Node is needed for report/build_docx.js (docx-js) — the base image is
# Python-only, so install Node + npm deps for the report package here.
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm libreoffice --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY report/package.json report/package-lock.json ./report/
RUN cd report && npm ci --omit=dev

COPY . .

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
