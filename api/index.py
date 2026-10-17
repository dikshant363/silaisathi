"""SilaiSathi — Vercel Serverless Function API Entrypoint.

Provides a Vercel-native serverless gateway for SilaiSathi:
- Exposes REST endpoints for system health, demo jobs, and AI extraction.
- Reuses core silaisathi validation, extraction, and schemas.
- Quarantines financial math in Python integer paise.
- Serves an interactive Apple-inspired web showcase at the root path.
- Exports both `handler` (BaseHTTPRequestHandler) and `app` (WSGI callable).
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Ensure project root is in sys.path for silaisathi imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from silaisathi.config import (  # noqa: E402
    CURRENCY_SYMBOL,
    DEFAULT_MODEL,
    GEMINI_API_KEY,
    GEMMA_DEFAULT_MODEL,
    MAX_INPUT_LENGTH,
)
from silaisathi.extraction import extract_with_llm, generate_sample_draft  # noqa: E402
from silaisathi.schemas import PaymentInfo  # noqa: E402
from silaisathi.validation import check_prompt_injection, validate_request_text  # noqa: E402

DEMO_FICTIONAL_JOBS = [
    {
        "id": "JOB-2026-0001",
        "customer_name": "Kamla Patel",
        "customer_phone": "9876543210",
        "garment_type": "Blouse",
        "status": "in_progress",
        "due_date": "2026-10-20",
        "measurements": {
            "chest": 34.0,
            "waist": 28.0,
            "length": 14.0,
            "front_neck": 6.0,
            "back_neck": 8.0,
        },
        "payment": {
            "total_amount_paise": 60000,
            "advance_paid_paise": 20000,
            "balance_due_paise": 40000,
            "total_rupees": 600.0,
            "advance_rupees": 200.0,
            "balance_rupees": 400.0,
        },
    },
    {
        "id": "JOB-2026-0002",
        "customer_name": "Rajeshwari Sharma",
        "customer_phone": "9823456789",
        "garment_type": "Salwar Suit",
        "status": "completed",
        "due_date": "2026-10-18",
        "measurements": {
            "kameez_length": 40.0,
            "chest": 38.0,
            "salwar_length": 38.0,
        },
        "payment": {
            "total_amount_paise": 120000,
            "advance_paid_paise": 120000,
            "balance_due_paise": 0,
            "total_rupees": 1200.0,
            "advance_rupees": 1200.0,
            "balance_rupees": 0.0,
        },
    },
    {
        "id": "JOB-2026-0003",
        "customer_name": "Ananya Gupta",
        "customer_phone": "9811223344",
        "garment_type": "Kurti",
        "status": "ready_for_trial",
        "due_date": "2026-10-22",
        "measurements": {"chest": 32.0, "length": 36.0, "shoulder": 13.5},
        "payment": {
            "total_amount_paise": 80000,
            "advance_paid_paise": 40000,
            "balance_due_paise": 40000,
            "total_rupees": 800.0,
            "advance_rupees": 400.0,
            "balance_rupees": 400.0,
        },
    },
]


def render_html_dashboard() -> str:
    """Renders the self-contained Apple-inspired HTML demonstration interface."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SilaiSathi — Tailoring Assistant (Vercel Edition)</title>
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --card-border: #30363d;
      --accent: #58a6ff;
      --accent-hover: #1f6feb;
      --text: #f0f6fc;
      --text-muted: #8b949e;
      --success: #3fb950;
      --warning: #d29922;
      --danger: #f85149;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 2rem 1rem;
    }
    .container {
      max-width: 960px;
      margin: 0 auto;
    }
    header {
      text-align: center;
      margin-bottom: 2.5rem;
    }
    .badge {
      display: inline-block;
      padding: 0.25rem 0.75rem;
      font-size: 0.8rem;
      font-weight: 600;
      border-radius: 9999px;
      background: rgba(88, 166, 255, 0.15);
      color: var(--accent);
      border: 1px solid rgba(88, 166, 255, 0.3);
      margin-bottom: 0.75rem;
    }
    h1 {
      font-size: 2.25rem;
      font-weight: 700;
      letter-spacing: -0.03em;
      margin-bottom: 0.5rem;
    }
    p.subtitle {
      color: var(--text-muted);
      font-size: 1.05rem;
      max-width: 640px;
      margin: 0 auto;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 1.5rem;
      margin-bottom: 2rem;
    }
    @media (min-width: 768px) {
      .grid-2 { grid-template-columns: 1fr 1fr; }
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.5rem;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .card h2 {
      font-size: 1.25rem;
      font-weight: 600;
      margin-bottom: 1rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    textarea {
      width: 100%;
      height: 140px;
      background: #090d13;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 0.75rem;
      color: var(--text);
      font-family: inherit;
      font-size: 0.95rem;
      resize: vertical;
      margin-bottom: 1rem;
    }
    textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.2);
    }
    .btn-group {
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    button {
      background: var(--accent);
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 0.6rem 1.2rem;
      font-weight: 600;
      font-size: 0.9rem;
      cursor: pointer;
      transition: background 0.15s ease;
    }
    button:hover { background: var(--accent-hover); }
    button.btn-secondary {
      background: #21262d;
      color: var(--text);
      border: 1px solid var(--card-border);
    }
    button.btn-secondary:hover { background: #30363d; }
    pre {
      background: #090d13;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 1rem;
      overflow-x: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85rem;
      color: #7ee787;
      max-height: 280px;
    }
    .info-list {
      list-style: none;
    }
    .info-list li {
      display: flex;
      justify-content: space-between;
      padding: 0.5rem 0;
      border-bottom: 1px solid rgba(48, 54, 61, 0.5);
      font-size: 0.9rem;
    }
    .info-list li:last-child { border-bottom: none; }
    .info-list span.val { font-weight: 600; color: var(--accent); }
    footer {
      text-align: center;
      margin-top: 3rem;
      color: var(--text-muted);
      font-size: 0.85rem;
    }
    footer a { color: var(--accent); text-decoration: none; }
    footer a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <span class="badge">Vercel Serverless Function Edition</span>
      <h1>✂️ SilaiSathi Workstation</h1>
      <p class="subtitle">
        AI Assistant for Indian Tailoring Shops — transforms multilingual Hinglish speech & notes into structured job cards with deterministic math quarantining.
      </p>
    </header>

    <div class="grid grid-2">
      <div class="card">
        <h2>⚡ Live Hinglish Extraction API</h2>
        <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.75rem;">
          Type or paste a tailoring request in Hinglish, Hindi, or English:
        </p>
        <textarea id="sampleInput">Kamla ben ka blue blouse: chest 34, waist 28, length 14, gala 6 aage 8 peeche. Delivery parso sham tak. Total 600, advance 200.</textarea>
        <div class="btn-group">
          <button id="extractBtn" onclick="runExtraction()">Extract Job Card</button>
          <button class="btn-secondary" onclick="loadSample(1)">Sample: Kurti</button>
          <button class="btn-secondary" onclick="loadSample(2)">Sample: Suit</button>
        </div>
      </div>

      <div class="card">
        <h2>📋 Structured Job Card JSON</h2>
        <div id="loading" style="display: none; color: var(--accent); font-size: 0.9rem; margin-bottom: 0.5rem;">
          Extracting structured measurements...
        </div>
        <pre id="outputJson">// Click "Extract Job Card" to parse request...</pre>
      </div>
    </div>

    <div class="grid grid-2">
      <div class="card">
        <h2>🛡️ Architecture & Verification</h2>
        <ul class="info-list">
          <li><span>Runtime</span><span class="val">Vercel Python Serverless</span></li>
          <li><span>Cloud Inference</span><span class="val">Google Gemma 4 (`gemma-4-26b-a4b-it`)</span></li>
          <li><span>Offline Fallback</span><span class="val">Deterministic Heuristic Sampler</span></li>
          <li><span>Financial Ledger</span><span class="val">Paise (Integer math quarantined in Python)</span></li>
          <li><span>Test Suite</span><span class="val">48 Unit & Integration Tests Passing</span></li>
        </ul>
      </div>

      <div class="card">
        <h2>🔗 Endpoints & Resources</h2>
        <ul class="info-list">
          <li><span>Health Check</span><span><a href="/api/health" style="color: var(--accent);"><code>GET /api/health</code></a></span></li>
          <li><span>Demo Jobs</span><span><a href="/api/jobs" style="color: var(--accent);"><code>GET /api/jobs</code></a></span></li>
          <li><span>Extraction</span><span><code>POST /api/extract</code></span></li>
          <li><span>Source Code</span><span><a href="https://github.com/dikshant363/silaisathi" target="_blank" style="color: var(--accent);">GitHub Repository</a></span></li>
          <li><span>Graphify Radar</span><span><a href="https://github.com/dikshant363/silaisathi/blob/main/graphify-out/GRAPH_REPORT.md" target="_blank" style="color: var(--accent);">AST Graph Report</a></span></li>
        </ul>
      </div>
    </div>

    <footer>
      SilaiSathi &copy; 2026 &bull; Designed for Indian Tailors and Boutiques &bull;
      <a href="https://github.com/dikshant363/silaisathi" target="_blank">dikshant363/silaisathi</a>
    </footer>
  </div>

  <script>
    const SAMPLES = {
      1: "Ananya ji: floral cotton kurti, length 38, chest 32, shoulder 13.5, sleeves 16. Total 750, 300 advance de diya. Deliver on Friday.",
      2: "Rajeshwari ji: silk salwar suit, kameez length 42, chest 38, waist 34, salwar length 39. Total 1400, pura pay kar diya hai."
    };

    function loadSample(id) {
      document.getElementById('sampleInput').value = SAMPLES[id] || "";
    }

    async function runExtraction() {
      const text = document.getElementById('sampleInput').value.trim();
      const output = document.getElementById('outputJson');
      const loading = document.getElementById('loading');
      if (!text) return;

      loading.style.display = 'block';
      output.textContent = "// Contacting SilaiSathi extraction API...";

      try {
        const res = await fetch('/api/extract', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        const data = await res.json();
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        output.textContent = JSON.stringify({ error: err.message }, null, 2);
      } finally {
        loading.style.display = 'none';
      }
    }
  </script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function HTTP Request Handler."""

    def _send_json(self, status: int, data: dict | list) -> None:
        payload = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, status: int, html_content: str) -> None:
        payload = html_content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        """Handles CORS preflight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        """Handles GET requests for health check, jobs, stats, and the HTML dashboard."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("/api/health", "/health"):
            data = {
                "status": "healthy",
                "service": "SilaiSathi Vercel Serverless API",
                "version": "0.1.0",
                "platform": "Vercel Serverless (Python)",
                "default_model": GEMMA_DEFAULT_MODEL if GEMINI_API_KEY else DEFAULT_MODEL,
                "gemini_api_configured": bool(GEMINI_API_KEY),
                "math_quarantine": "integer paise in Python",
                "currency": CURRENCY_SYMBOL,
            }
            self._send_json(200, data)
        elif path in ("/api/jobs", "/jobs"):
            self._send_json(200, {"jobs": DEMO_FICTIONAL_JOBS, "count": len(DEMO_FICTIONAL_JOBS)})
        elif path in ("/api/stats", "/stats"):
            total_paise = sum(job["payment"]["total_amount_paise"] for job in DEMO_FICTIONAL_JOBS)
            self._send_json(
                200,
                {
                    "total_jobs": len(DEMO_FICTIONAL_JOBS),
                    "active_jobs": 2,
                    "completed_jobs": 1,
                    "total_revenue_paise": total_paise,
                    "total_revenue_rupees": total_paise / 100.0,
                },
            )
        elif path in ("", "/", "/api"):
            # Check if query requests JSON
            query = parse_qs(parsed.query)
            if query.get("format", [""])[0] == "json":
                self._send_json(
                    200,
                    {
                        "service": "SilaiSathi Vercel Serverless API",
                        "version": "0.1.0",
                        "status": "online",
                        "endpoints": ["/api/health", "/api/jobs", "/api/stats", "/api/extract"],
                    },
                )
            else:
                self._send_html(200, render_html_dashboard())
        else:
            self._send_json(404, {"error": "Not Found", "path": path})

    def do_POST(self) -> None:
        """Handles POST requests for AI extraction."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path not in ("/api/extract", "/extract"):
            self._send_json(404, {"error": "Endpoint Not Found", "path": path})
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self._send_json(400, {"error": "Empty request body"})
                return

            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
            raw_text = payload.get("text", "").strip()

            if not raw_text:
                self._send_json(400, {"error": "Field 'text' is required"})
                return

            if len(raw_text) > MAX_INPUT_LENGTH:
                self._send_json(
                    400,
                    {
                        "error": f"Input text exceeds maximum length of {MAX_INPUT_LENGTH} characters"
                    },
                )
                return

            # Security sanitization and validation
            is_valid, validation_msg = validate_request_text(raw_text)
            if not is_valid:
                self._send_json(400, {"error": validation_msg})
                return

            has_injection = check_prompt_injection(raw_text)
            warning = (
                "Suspicious phrase detected in request; please review extracted draft carefully."
                if has_injection
                else None
            )

            requested_model = payload.get("model", GEMMA_DEFAULT_MODEL)

            # Perform extraction
            provider_used = "offline_heuristic_sampler"
            try:
                if GEMINI_API_KEY:
                    draft = extract_with_llm(raw_text, model_name=requested_model)
                    provider_used = "gemma"
                else:
                    draft = generate_sample_draft(raw_text)
            except Exception:
                # Resilient fallback to deterministic sampler
                draft = generate_sample_draft(raw_text)

            payment = PaymentInfo.from_rupees(
                total_rs=draft.total_price,
                advance_rs=draft.advance_paid or 0.0,
            )

            total_formatted = (
                f"{CURRENCY_SYMBOL}{payment.total_price_rs:.2f}"
                if payment.total_price_rs is not None
                else "Not set"
            )
            advance_formatted = f"{CURRENCY_SYMBOL}{payment.advance_paid_rs:.2f}"

            response_data = {
                "success": True,
                "provider": provider_used,
                "warning": warning,
                "draft": draft.model_dump(),
                "payment_summary": {
                    "total_paise": payment.total_price_paise,
                    "advance_paise": payment.advance_paid_paise,
                    "balance_paise": payment.balance_due_paise,
                    "formatted_total": total_formatted,
                    "formatted_advance": advance_formatted,
                    "formatted_balance": payment.display_balance(),
                },
            }
            self._send_json(200, response_data)

        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON payload"})
        except Exception as e:
            self._send_json(500, {"error": "Internal Server Error", "details": str(e)})


# Export canonical Vercel entrypoints
handler = Handler


def app(environ: dict, start_response: callable) -> list[bytes]:
    """Standard WSGI entrypoint callable for environments that check for `app`."""
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")

    if method == "GET":
        if path in ("/api/health", "/health"):
            data = json.dumps(
                {"status": "healthy", "service": "SilaiSathi WSGI API", "version": "0.1.0"}
            ).encode("utf-8")
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [data]
        elif path in ("", "/", "/api"):
            html = render_html_dashboard().encode("utf-8")
            start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
            return [html]

    data = json.dumps({"status": "running", "path": path}).encode("utf-8")
    start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
    return [data]
