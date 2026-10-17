# SilaiSathi — DigitalOcean App Platform Deployment Guide

This guide documents the exact, reproducible steps to deploy **SilaiSathi** to [DigitalOcean App Platform](https://cloud.digitalocean.com/apps) for public web demonstrations and evaluation.

---

## 1. Architecture & Deployment Overview

SilaiSathi is designed as an **offline-first workstation** for Indian tailoring shops. In local production, it runs 100% offline on the tailor's computer with zero cloud telemetry.

For hackathon judging, live demos, and public web evaluations, SilaiSathi can be deployed to DigitalOcean App Platform:
- **Runtime:** Minimal OCI container (`python:3.12-slim`).
- **Web Server:** Streamlit bound to `0.0.0.0` on the platform-assigned dynamic port (`$PORT`, default 8080).
- **Inference Mode:** Hosted Gemma 4 open weights (`gemma-4-26b-a4b-it`) via Google Gemini API (or fallback offline heuristic sampler).
- **Data Persistence:** Resettable SQLite demo database pre-seeded with realistic fictional tailoring requests (zero real customer PII).
- **SSL / HTTPS:** Automatic DigitalOcean-managed Let's Encrypt TLS certificate.

```
                    ┌───────────────────────────────────────────┐
                    │       DigitalOcean App Platform           │
                    │                                           │
  Internet HTTPS    │   ┌───────────────────────────────────┐   │
───────────────────►│   │  SilaiSathi Web Container         │   │
  (Let's Encrypt)   │   │  (python:3.12-slim, non-root)     │   │
                    │   │  Streamlit on 0.0.0.0:8080        │   │
                    │   └─────────────────┬─────────────────┘   │
                    │                     │                     │
                    │          ┌──────────┴──────────┐          │
                    │          ▼                     ▼          │
                    │   ┌──────────────┐      ┌─────────────┐   │
                    │   │ Fictional    │      │ Optional    │   │
                    │   │ Demo SQLite  │      │ Gemma 4 API │   │
                    │   │ (Ephemeral)  │      │ (Hosted)    │   │
                    │   └──────────────┘      └─────────────┘   │
                    └───────────────────────────────────────────┘
```

---

## 2. Authorization & Cost Checkpoint

> [!IMPORTANT]
> **Zero Unapproved Cloud Resources**: Before creating an App Platform resource in DigitalOcean, verify the cost tier.
> - **Recommended Tier:** `Basic (XXS)` — **1 vCPU / 512 MB RAM** ($5.00/month).
> - **Billing:** Prorated by the second. A 2-hour demonstration costs approximately **$0.014** (under 2 cents).
> - **MLH Credits:** If you received DigitalOcean credits at Hacktoberfest Hack Day, ensure they are applied to your team's team/billing account before launching.

---

## 3. DigitalOcean App Platform Specifications

### App Specification (`.do/app.yaml`)
The project includes a ready-to-deploy declarative App Platform spec in [`.do/app.yaml`](.do/app.yaml):

| Property | Value | Description |
| :--- | :--- | :--- |
| **Component Name** | `silaisathi-web` | Web service container |
| **Source Type** | Dockerfile | Builds using repository [`Dockerfile`](Dockerfile) |
| **Region** | `blr` (Bangalore) | Lowest latency for Indian tailoring users (or `fra` / `nyc`) |
| **Branch** | `main` | Production deployment branch |
| **HTTP Port** | `8080` | Assigned by App Platform via `$PORT` environment variable |
| **Instance Size** | `basic-xxs` | 512 MB RAM / 1 vCPU ($5/mo) |
| **Health Check Path** | `/_stcore/health` | Streamlit official healthcheck route |
| **Health Check Protocol** | HTTP | Expects status `200 OK` (returns `"ok"`) |
| **Initial Delay** | `15s` | Grace period for Python module initialization |

---

## 4. Environment Variables & Runtime Secrets

Configure these environment variables in the DigitalOcean App Platform console:

| Variable Name | Type | Value / Purpose | Scope |
| :--- | :--- | :--- | :--- |
| `PORT` | Plaintext | `8080` (Automatically injected by DigitalOcean) | Run-Time |
| `SILAISATHI_CLOUD_DEPLOYMENT` | Plaintext | `1` (Notifies UI that app is running in cloud) | Run-Time |
| `SILAISATHI_DEMO_MODE` | Plaintext | `1` (Seeds fictional demo requests on initial launch) | Run-Time |
| `SILAISATHI_AI_PROVIDER` | Plaintext | `gemma` (Selects Gemma 4 cloud provider by default) | Run-Time |
| `GEMINI_API_KEY` | **Secret (Encrypted)** | `AIzaSy...` (Your free Google AI Studio API key) | Run-Time |

> [!CAUTION]
> **Secret Key Safety:** Never commit `GEMINI_API_KEY` into git or paste it into public issues. In DigitalOcean App Platform, always select **Encrypt** when entering the key.

---

## 5. Deployment Methods

### Method 1: Automated Deploy via DigitalOcean Web Console
1. Navigate to **Apps** in [cloud.digitalocean.com/apps](https://cloud.digitalocean.com/apps).
2. Click **Create App** ➔ select **GitHub**.
3. Select repository: `dikshant363/silaisathi` and branch: `main`.
4. App Platform will auto-detect the [`Dockerfile`](Dockerfile).
5. In **App Settings**:
   - HTTP Port: `8080`
   - Health Check: `/_stcore/health`
6. In **Environment Variables**:
   - Add `SILAISATHI_CLOUD_DEPLOYMENT = 1`
   - Add `SILAISATHI_DEMO_MODE = 1`
   - Add `GEMINI_API_KEY` as an **Encrypted Secret**.
7. Select **Basic XXS** ($5/month).
8. Click **Create Resources** to launch.

### Method 2: Command-Line Deploy using DigitalOcean CLI (`doctl`)
If you have `doctl` installed and authenticated:
```bash
# Validate app specification
doctl apps spec validate .do/app.yaml

# Create app from spec
doctl apps create --spec .do/app.yaml
```

---

## 6. Container & Persistence Limitations

1. **Ephemeral Filesystem:**
   - DigitalOcean App Platform containers use ephemeral storage. Any SQLite databases created during the session are stored in `/home/appuser/.silaisathi/silaisathi.db`.
   - When a new deployment occurs or the container restarts, the database returns to its clean initial state.
   - For demo purposes, this is ideal: SilaiSathi automatically seeds 5 realistic fictional job cards on initial launch, preventing state corruption.
2. **Persistent Storage Alternative (Optional for Production):**
   - For continuous commercial use where orders must persist across deployments, attach a DigitalOcean Managed PostgreSQL database or mount a persistent volume (supported on Dedicated instance tiers).
3. **No Local Ollama in Cloud:**
   - The cloud container cannot communicate with your local machine's `127.0.0.1:11434` Ollama instance.
   - In cloud mode, SilaiSathi uses the hosted Gemma 4 model or the offline heuristic fallback. It never attempts to connect to localhost Ollama in the cloud.

---

## 7. Post-Deployment Verification & Smoke Tests

Once your DigitalOcean App Platform URL is active (e.g., `https://silaisathi-xxxxx.ondigitalocean.app`):

1. **Health Check Probe:**
   ```bash
   curl -i https://<your-app-domain>/_stcore/health
   # Expected output: HTTP/2 200 OK, body: "ok"
   ```
2. **Dashboard Rendering:**
   - Open `https://<your-app-domain>` in your browser.
   - Verify sidebar displays: `☁️ DigitalOcean App Platform`.
   - Verify metrics cards load: 5 Total Jobs, active awaiting jobs.
3. **Fictional Demo Seeding:**
   - Click through **Dashboard** job cards (Meena Kumari, Sunita Sharma, Kavita Verma).
   - Verify statuses (`Confirmed`, `In Progress`, `Ready`).
4. **AI Extraction Smoke Test:**
   - Navigate to **New Job (AI Assistant)**.
   - Click one of the quick sample buttons (e.g. *"Blue Kurti with Sunday Deadline"*).
   - Click **⚡ Extract with Local AI** (runs Gemma 4 via Gemini API if key is set) or **🧪 Test Offline Heuristic**.
   - Review the extracted fields and approve the job card.
5. **Printable Slip Smoke Test:**
   - Navigate to **Print Work Slip**.
   - Verify dual-language Hindi/English labels and workshop checklist render cleanly.
6. **Demo Reset Smoke Test:**
   - Navigate to **Data & Privacy** ➔ click **🔄 Reset Fictional Demo Data**.
   - Verify database resets to initial 5 demo jobs with zero errors.
