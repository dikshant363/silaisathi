# SilaiSathi — Vercel Serverless Function Deployment Guide

This guide documents the architecture, configuration, and verification steps for deploying **SilaiSathi** to [Vercel](https://vercel.com) as a Python Serverless Function API with an interactive web showcase.

---

## 1. Architecture Overview

SilaiSathi uses a dual-deployment architecture:

1. **Local Workstation & Container Environments** (`app.py`, `Dockerfile`, `.do/app.yaml`):
   - Runs full interactive Streamlit interface on loopback (`127.0.0.1:8501`) or container port (`0.0.0.0:8080`).
   - Maintains persistent WebSockets and Tornado session state for local tailors and container platforms (DigitalOcean, Streamlit Cloud).
2. **Vercel Serverless Function** (`api/index.py`, `vercel.json`, `.vercelignore`):
   - Runs serverless Python endpoints on Vercel's global edge network.
   - Reuses core `silaisathi` modules: input validation, prompt injection detection, Gemma 4 / heuristic extraction, and deterministic integer paise ledger arithmetic.
   - Serves an Apple-inspired HTML demonstration dashboard at the root path (`/`).

```
                    ┌───────────────────────────────────────────┐
                    │            Vercel Global Edge             │
                    │                                           │
  Client Request    │   ┌───────────────────────────────────┐   │
───────────────────►│   │  vercel.json Rewrites             │   │
  (HTTPS)           │   │  All traffic -> api/index.py      │   │
                    │   └─────────────────┬─────────────────┘   │
                    │                     │                     │
                    │                     ▼                     │
                    │   ┌───────────────────────────────────┐   │
                    │   │  Vercel Python Function           │   │
                    │   │  • GET  /         (HTML Console)  │   │
                    │   │  • GET  /api/health               │   │
                    │   │  • GET  /api/jobs                 │   │
                    │   │  • GET  /api/stats                │   │
                    │   │  • POST /api/extract              │   │
                    │   └─────────────────┬─────────────────┘   │
                    │                     │                     │
                    │          ┌──────────┴──────────┐          │
                    │          ▼                     ▼          │
                    │   ┌──────────────┐      ┌─────────────┐   │
                    │   │ Deterministic│      │ Optional    │   │
                    │   │ Integer Math │      │ Gemma 4 API │   │
                    │   │ (Paise)      │      │ (Hosted)    │   │
                    │   └──────────────┘      └─────────────┘   │
                    └───────────────────────────────────────────┘
```

---

## 2. Resolving `[PYTHON_ENTRYPOINT_NOT_FOUND]`

### The Problem
When Vercel detects a root `app.py`, its Python builder (`@vercel/python`) assumes it is a WSGI/ASGI application. Because Streamlit's `app.py` is an interactive script requiring persistent WebSockets, Vercel fails during `vercel build` with:
```text
Error: [PYTHON_ENTRYPOINT_NOT_FOUND] Found app.py but it does not export a top-level "app", "application", or "handler" variable.
```

### The Solution
1. [`.vercelignore`](.vercelignore): Excludes `app.py`, tests, and local databases from Vercel function packaging.
2. [`vercel.json`](vercel.json): Configures automatic routing to `api/index.py`.
3. [`api/index.py`](api/index.py): Implements a Vercel-compliant serverless handler exporting both:
   - `class Handler(BaseHTTPRequestHandler)` + `handler = Handler`
   - WSGI `app(environ, start_response)`

---

## 3. Environment Variables on Vercel

In your Vercel Project Settings (**Settings > Environment Variables**), configure the following optional variable:

| Variable | Required | Description | Example |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | Optional | Google Gemini API key for hosted Gemma 4 (`gemma-4-26b-a4b-it`) inference. | `AIzaSy...` |

*(If unconfigured, SilaiSathi automatically falls back to its deterministic heuristic sampler with zero crashes).*

---

## 4. API Endpoints Reference

### `GET /`
Returns the Apple-inspired interactive web console with a live Hinglish tailoring extraction test box, sample customer inputs, and system telemetry.

### `GET /api/health`
```json
{
  "status": "healthy",
  "service": "SilaiSathi Vercel Serverless API",
  "version": "0.1.0",
  "platform": "Vercel Serverless (Python)",
  "default_model": "gemma-4-26b-a4b-it",
  "gemini_api_configured": true,
  "math_quarantine": "integer paise in Python",
  "currency": "₹"
}
```

### `GET /api/jobs`
Returns realistic fictional tailoring job cards with customer names, garments, measurements, and payment ledger details.

### `POST /api/extract`
Parses raw tailoring notes or voice transcripts into structured JSON:

**Request:**
```bash
curl -X POST https://<your-app>.vercel.app/api/extract \
  -H "Content-Type: application/json" \
  -d '{"text": "Kamla ben ka blue blouse: chest 34, waist 28. Advance 200 pay kiya."}'
```

**Response:**
```json
{
  "success": true,
  "provider": "gemma",
  "warning": null,
  "draft": {
    "garment_type": "Blouse",
    "measurements": { "chest": 34.0, "waist": 28.0 },
    "advance_paid": 200.0
  },
  "payment_summary": {
    "total_paise": null,
    "advance_paise": 20000,
    "balance_paise": null,
    "formatted_total": "Not set",
    "formatted_advance": "₹200.00",
    "formatted_balance": "Unknown (Total not set)"
  }
}
```

---

## 5. Local Verification

To run the automated Vercel integration test suite locally:
```bash
pytest -v tests/test_vercel_api.py
```
