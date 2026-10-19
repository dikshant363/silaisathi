"""Local AI Extraction Service for SilaiSathi.

Connects to local open-weight models running inside Ollama (default: Qwen 3.5 4B).
Processes natural language requests in Hindi, Hinglish, and English into structured drafts.
Enforces schema validation, handles model thinking tokens (<think>...</think>),
and safeguards against hallucinations and missing fields.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from silaisathi.config import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    GEMINI_API_KEY,
    GEMMA_API_BASE,
    GEMMA_DEFAULT_MODEL,
    INFERENCE_TIMEOUT_SECONDS,
    OLLAMA_HOST,
)
from silaisathi.schemas import (
    ExtractedDraft,
    FlagSeverity,
    MeasurementUnit,
    ReviewFlag,
)
from silaisathi.validation import (
    check_prompt_injection,
    normalize_indic_digits,
    resolve_due_date,
    validate_measurements_plausibility,
    validate_request_text,
)

SYSTEM_EXTRACTION_PROMPT = """You are SilaiSathi, an expert AI assistant for Indian tailoring shops and boutiques.
Your job is to extract tailoring job details from customer requests written in English, Hindi, or Hinglish.

Rules you MUST strictly follow:
1. Extract ONLY facts explicitly stated in the user text. Never invent customer names, phone numbers, prices, units, or measurements.
2. If total price was not stated, set "total_price": null. Never calculate or invent a total price.
3. If an advance was paid (e.g. "300 advance diya", "advance 500"), record it in "advance_paid".
4. If measurements are given (e.g. "length 44, chest 38, baju 18", "kamar 32", "teera 15", "mohari 7"), extract them as a key-value dictionary with numbers only.
5. Standard measurement unit is "in" (inches) unless centimeters ("cm") is explicitly mentioned.
6. Extract due date text as stated (e.g. "Sunday", "parso", "kal", "15 tarikh", "next week"). Do NOT assume a specific calendar year or date.
7. Extract fitting preferences (e.g. "pichhli baar wali fitting", "loose rakhna", "tight fitting", "deep back neck").
8. Always output valid JSON conforming exactly to this structure:

{
  "customer_name": "string or null",
  "customer_phone": "string or null",
  "garment_type": "string or null",
  "garment_color": "string or null",
  "garment_fabric": "string or null",
  "measurements": {
    "length": 44.0,
    "chest": 38.0,
    "sleeves": 18.0
  },
  "measurement_unit": "in",
  "due_date_text": "string or null",
  "total_price": null,
  "advance_paid": null,
  "fitting_preference": "string or null",
  "additional_notes": "string or null"
}
"""


def check_ollama_health() -> tuple[bool, str, list[str]]:
    """Check if the local Ollama server is accessible and list installed models."""
    try:
        response = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=3.0)
        if response.status_code == 200:
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            return True, "Ollama service is active and responsive.", models
        return False, f"Ollama returned unexpected status HTTP {response.status_code}.", []
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        return (
            False,
            f"Could not connect to Ollama at {OLLAMA_HOST} ({exc.__class__.__name__}).",
            [],
        )
    except Exception as exc:
        return False, f"Ollama health check error: {str(exc)}", []


def check_gemma_health() -> tuple[bool, str, list[str]]:
    """Check availability of the optional Gemma 4 provider via Google Gemini API."""
    if not GEMINI_API_KEY:
        return (
            False,
            "GEMINI_API_KEY environment variable is not configured. Gemma 4 hosted provider is optional and unconfigured.",
            [],
        )
    return (
        True,
        "Gemini API key configured. Ready for Gemma 4 extraction.",
        [GEMMA_DEFAULT_MODEL, "gemma-4-31b-it", "gemma-2-9b-it"],
    )


def clean_model_output(raw_text: str) -> str:
    """Clean model response by removing thinking tags and markdown code blocks."""
    # Remove Qwen/DeepSeek thinking tags <think>...</think>
    text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL)
    text = text.strip()

    # Extract JSON block if wrapped in markdown ```json ... ```
    json_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if json_block_match:
        return json_block_match.group(1).strip()

    # Find the outermost JSON curly braces
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1].strip()

    return text


class BaseExtractionProvider:
    """Base interface for SilaiSathi extraction providers."""

    provider_name: str = "base"

    def is_available(self) -> tuple[bool, str, list[str]]:
        raise NotImplementedError

    def extract(
        self,
        customer_request: str,
        model_name: str | None = None,
        manual_customer_name: str | None = None,
        manual_customer_phone: str | None = None,
    ) -> ExtractedDraft:
        raise NotImplementedError


class OllamaProvider(BaseExtractionProvider):
    """Local-first offline Ollama inference provider (Loopback 127.0.0.1)."""

    provider_name: str = "ollama"

    def is_available(self) -> tuple[bool, str, list[str]]:
        return check_ollama_health()

    def extract(
        self,
        customer_request: str,
        model_name: str | None = None,
        manual_customer_name: str | None = None,
        manual_customer_phone: str | None = None,
    ) -> ExtractedDraft:
        valid, msg = validate_request_text(customer_request)
        if not valid:
            raise ValueError(msg)

        prompt_injection_flag = check_prompt_injection(customer_request)
        normalized_request = normalize_indic_digits(customer_request)
        target_model = model_name or DEFAULT_MODEL

        # ChatML prefill format specifically bypasses thinking delays on reasoning models like Qwen 3.5
        prompt = (
            f"<|im_start|>system\n{SYSTEM_EXTRACTION_PROMPT}<|im_end|>\n"
            f'<|im_start|>user\nCustomer Request:\n"""{normalized_request}"""\n\nOutput JSON only:<|im_end|>\n'
            f"<|im_start|>assistant\n<think>\nDone.\n</think>\n{{"
        )

        payload = {
            "model": target_model,
            "prompt": prompt,
            "raw": True,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for deterministic factual extraction
                "num_predict": 1024,
            },
        }

        try:
            response = httpx.post(
                f"{OLLAMA_HOST}/api/generate",
                json=payload,
                timeout=float(INFERENCE_TIMEOUT_SECONDS),
            )
            response.raise_for_status()
            res_data = response.json()
            raw_output = res_data.get("response", "")
            if not raw_output.strip().startswith("{"):
                raw_output = "{" + raw_output
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Ollama server is not running or unreachable at {OLLAMA_HOST}. "
                "Please start Ollama with 'ollama serve' in your terminal."
            ) from exc
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"Local inference timed out after {INFERENCE_TIMEOUT_SECONDS} seconds. "
                "Consider using a smaller model like qwen3.5:4b or increasing the timeout."
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Error communicating with local AI model: {str(exc)}") from exc

        cleaned_json_text = clean_model_output(raw_output)

        try:
            parsed: dict[str, Any] = json.loads(cleaned_json_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Model produced invalid JSON output. Response was: {raw_output[:200]}..."
            ) from exc

        return build_draft_from_parsed(
            parsed=parsed,
            raw_request=customer_request,
            model_name=target_model,
            manual_name=manual_customer_name,
            manual_phone=manual_customer_phone,
            injection_detected=prompt_injection_flag,
        )


class GemmaProvider(BaseExtractionProvider):
    """Optional hosted Google Gemini API provider running Gemma 4 open weights."""

    provider_name: str = "gemma"

    def is_available(self) -> tuple[bool, str, list[str]]:
        return check_gemma_health()

    def extract(
        self,
        customer_request: str,
        model_name: str | None = None,
        manual_customer_name: str | None = None,
        manual_customer_phone: str | None = None,
    ) -> ExtractedDraft:
        valid, msg = validate_request_text(customer_request)
        if not valid:
            raise ValueError(msg)

        if not GEMINI_API_KEY:
            raise ValueError(
                "Gemini API key is not configured. "
                "Please set GEMINI_API_KEY or GOOGLE_API_KEY in your environment to use the Gemma 4 provider."
            )

        prompt_injection_flag = check_prompt_injection(customer_request)
        normalized_request = normalize_indic_digits(customer_request)
        target_model = model_name or GEMMA_DEFAULT_MODEL
        clean_model_id = target_model.replace("models/", "").strip()

        url = f"{GEMMA_API_BASE}/models/{clean_model_id}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY,
        }
        payload = {
            "systemInstruction": {
                "parts": [{"text": SYSTEM_EXTRACTION_PROMPT}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f'Customer Request:\n"""{normalized_request}"""\n\nOutput JSON only:'
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json",
            },
        }

        try:
            response = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=float(INFERENCE_TIMEOUT_SECONDS),
            )
            if response.status_code == 400:
                raise ValueError(f"Gemini API Bad Request (HTTP 400): {response.text}")
            if response.status_code == 403:
                raise PermissionError(
                    "Gemini API authentication failed (HTTP 403). Check your GEMINI_API_KEY."
                )
            if response.status_code == 429:
                raise RuntimeError(
                    "Gemini API rate limit exceeded (HTTP 429). Please try again shortly."
                )
            response.raise_for_status()

            res_data = response.json()
            candidates = res_data.get("candidates", [])
            if not candidates:
                raise ValueError("Gemma model returned empty candidate response.")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise ValueError("Gemma model returned empty content parts.")
            # Handle thinking models (e.g. Gemma 4) where earlier parts contain thought: true
            non_thought_parts = [p.get("text", "") for p in parts if not p.get("thought")]
            raw_output = non_thought_parts[-1] if non_thought_parts else parts[-1].get("text", "")
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Could not connect to Google Gemini API at {GEMMA_API_BASE}. Check internet connectivity."
            ) from exc
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"Gemma inference timed out after {INFERENCE_TIMEOUT_SECONDS} seconds."
            ) from exc
        except (ValueError, PermissionError, RuntimeError):
            raise
        except Exception as exc:
            raise RuntimeError(f"Error communicating with Gemma 4 model: {str(exc)}") from exc

        cleaned_json_text = clean_model_output(raw_output)

        try:
            parsed: dict[str, Any] = json.loads(cleaned_json_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Gemma model produced invalid JSON output. Response was: {raw_output[:200]}..."
            ) from exc

        draft = build_draft_from_parsed(
            parsed=parsed,
            raw_request=customer_request,
            model_name=target_model,
            manual_name=manual_customer_name,
            manual_phone=manual_customer_phone,
            injection_detected=prompt_injection_flag,
        )

        draft.review_flags.append(
            ReviewFlag(
                field="provider",
                severity=FlagSeverity.INFO,
                message=f"Extracted using optional hosted model '{target_model}' via Google Gemini API.",
            )
        )
        return draft


_OLLAMA_PROVIDER = OllamaProvider()
_GEMMA_PROVIDER = GemmaProvider()


def get_provider(name: str = "ollama") -> BaseExtractionProvider:
    """Retrieve an extraction provider instance by name ('ollama' or 'gemma')."""
    normalized = (name or "ollama").strip().lower()
    if normalized in ("gemma", "gemma-api", "gemini"):
        return _GEMMA_PROVIDER
    return _OLLAMA_PROVIDER


def extract_with_llm(
    customer_request: str,
    model_name: str | None = None,
    manual_customer_name: str | None = None,
    manual_customer_phone: str | None = None,
    provider: str | None = None,
) -> ExtractedDraft:
    """Send customer request to configured AI provider and return structured ExtractedDraft.

    Defaults strictly to local Ollama (127.0.0.1 loopback) with Qwen 3.5 4B.
    """
    selected_provider_name = provider
    if selected_provider_name is None:
        if model_name and (
            model_name.startswith("gemma-4")
            or model_name.startswith("gemma-2")
            or "gemma-cloud" in model_name
        ):
            selected_provider_name = "gemma"
        else:
            selected_provider_name = DEFAULT_PROVIDER

    provider_instance = get_provider(selected_provider_name)
    target_model = model_name or (
        DEFAULT_MODEL if provider_instance.provider_name == "ollama" else GEMMA_DEFAULT_MODEL
    )

    return provider_instance.extract(
        customer_request=customer_request,
        model_name=target_model,
        manual_customer_name=manual_customer_name,
        manual_customer_phone=manual_customer_phone,
    )


def build_draft_from_parsed(
    parsed: dict[str, Any],
    raw_request: str,
    model_name: str = "qwen3.5:4b",
    manual_name: str | None = None,
    manual_phone: str | None = None,
    injection_detected: bool = False,
) -> ExtractedDraft:
    """Build, audit, and flag an ExtractedDraft from parsed JSON dictionary."""
    draft = ExtractedDraft(
        raw_request=raw_request,
        model_name=model_name,
    )

    # 1. Customer details (prefer manual input if tailor typed it, else model extract)
    extracted_name = parsed.get("customer_name")
    draft.customer_name = (
        manual_name.strip() if manual_name else (extracted_name if extracted_name else None)
    )

    extracted_phone = parsed.get("customer_phone")
    draft.customer_phone = (
        manual_phone.strip() if manual_phone else (extracted_phone if extracted_phone else None)
    )

    # 2. Garment Details
    draft.garment_type = parsed.get("garment_type") or None
    draft.garment_color = parsed.get("garment_color") or None
    draft.garment_fabric = parsed.get("garment_fabric") or None
    draft.fitting_preference = parsed.get("fitting_preference") or None
    draft.additional_notes = parsed.get("additional_notes") or None

    # 3. Measurements
    raw_measurements = parsed.get("measurements") or {}
    clean_meas: dict[str, float] = {}
    if isinstance(raw_measurements, dict):
        for k, v in raw_measurements.items():
            try:
                if v is not None and float(v) > 0:
                    clean_meas[str(k).strip().lower()] = round(float(v), 2)
            except (ValueError, TypeError):
                pass
    draft.measurements = clean_meas

    unit_str = str(parsed.get("measurement_unit", "in")).lower().strip()
    draft.measurement_unit = (
        MeasurementUnit.CENTIMETERS if "cm" in unit_str else MeasurementUnit.INCHES
    )

    # 4. Financials
    try:
        draft.total_price = (
            float(parsed["total_price"]) if parsed.get("total_price") is not None else None
        )
    except (ValueError, TypeError):
        draft.total_price = None

    try:
        draft.advance_paid = (
            float(parsed["advance_paid"]) if parsed.get("advance_paid") is not None else None
        )
    except (ValueError, TypeError):
        draft.advance_paid = None

    # 5. Due date resolution
    draft.due_date_text = parsed.get("due_date_text") or None
    resolved_date, needs_conf, date_note = resolve_due_date(draft.due_date_text)
    draft.due_date_resolved = resolved_date
    draft.due_date_needs_confirmation = needs_conf

    # 6. Audit & Flag Generation
    flags: list[ReviewFlag] = []
    supplied: list[str] = []
    inferred: list[str] = []
    missing: list[str] = []
    ambiguous: list[str] = []

    # Injection Flag
    if injection_detected:
        flags.append(
            ReviewFlag(
                field="security",
                severity=FlagSeverity.WARNING,
                message="Suspicious instruction pattern detected in customer text. Input was strictly isolated as untrusted data.",
            )
        )

    # Customer Name Flag
    if draft.customer_name:
        supplied.append(f"Customer Name: {draft.customer_name}")
    else:
        missing.append("Customer Name")
        flags.append(
            ReviewFlag(
                field="customer_name",
                severity=FlagSeverity.CRITICAL,
                message="Customer name is missing. Please enter the customer's name.",
            )
        )

    # Customer Phone
    if draft.customer_phone:
        supplied.append(f"Phone: {draft.customer_phone}")
    else:
        flags.append(
            ReviewFlag(
                field="customer_phone",
                severity=FlagSeverity.INFO,
                message="Customer phone number was not provided.",
            )
        )

    # Garment Type Flag
    if draft.garment_type:
        supplied.append(f"Garment: {draft.garment_type}")
    else:
        missing.append("Garment Type")
        flags.append(
            ReviewFlag(
                field="garment_type",
                severity=FlagSeverity.CRITICAL,
                message="Garment type is unspecified. Please confirm the garment type.",
            )
        )

    # Measurements Check
    if draft.measurements:
        meas_items = [f"{k}={v}" for k, v in draft.measurements.items()]
        supplied.append(f"Measurements: {', '.join(meas_items)}")
        meas_flags = validate_measurements_plausibility(draft.measurements, draft.measurement_unit)
        flags.extend(meas_flags)
    else:
        missing.append("Measurements")
        flags.append(
            ReviewFlag(
                field="measurements",
                severity=FlagSeverity.WARNING,
                message="No body measurements found in request. Tailor must record measurements.",
            )
        )

    # Due Date Flag
    if draft.due_date_text:
        supplied.append(f"Delivery: '{draft.due_date_text}'")
        if draft.due_date_needs_confirmation:
            ambiguous.append("Due Date")
            flags.append(
                ReviewFlag(
                    field="due_date",
                    severity=FlagSeverity.WARNING,
                    message=date_note,
                )
            )
    else:
        missing.append("Due Date")
        flags.append(
            ReviewFlag(
                field="due_date",
                severity=FlagSeverity.INFO,
                message="No delivery deadline was specified.",
            )
        )

    # Price & Advance
    if draft.total_price is not None:
        supplied.append(f"Total Price: ₹{draft.total_price:.2f}")
    else:
        inferred.append("Total Price: Not provided (Balance remains Unknown)")
        flags.append(
            ReviewFlag(
                field="total_price",
                severity=FlagSeverity.INFO,
                message="Total stitching price was not stated. Balance cannot be computed until price is set.",
            )
        )

    if draft.advance_paid is not None:
        supplied.append(f"Advance Paid: ₹{draft.advance_paid:.2f}")
        if draft.total_price is not None and draft.advance_paid > draft.total_price:
            flags.append(
                ReviewFlag(
                    field="advance_paid",
                    severity=FlagSeverity.WARNING,
                    message=f"Advance payment (₹{draft.advance_paid:.2f}) exceeds total price (₹{draft.total_price:.2f}). Please verify.",
                )
            )

    draft.supplied_facts = supplied
    draft.model_interpretations = inferred
    draft.missing_fields = missing
    draft.ambiguous_fields = ambiguous
    draft.review_flags = flags

    return draft


def generate_sample_draft(request_text: str) -> ExtractedDraft:
    """Offline sample generator for testing when Ollama is unavailable.

    Provides a clearly labelled sample draft without pretending to be live AI output.
    Uses realistic regex heuristic extraction for fallback demo capability.
    """
    clean_text = normalize_indic_digits(request_text).lower()

    # Detect garment
    garment = "Kurti"
    for g in ["kurti", "blouse", "salwar", "suit", "pant", "shirt", "lehenga", "plazo"]:
        if g in clean_text:
            garment = g.title()
            break

    # Detect color
    color = None
    for c in ["blue", "red", "green", "black", "white", "yellow", "pink", "maroon", "navy"]:
        if c in clean_text:
            color = c.title()
            break

    # Detect measurements
    meas: dict[str, float] = {}
    for pattern, name in [
        (r"length\s*(\d+)", "length"),
        (r"chest\s*(\d+)", "chest"),
        (r"sleeves?\s*(\d+)", "sleeves"),
        (r"waist\s*(\d+)", "waist"),
        (r"hips?\s*(\d+)", "hips"),
        (r"kamar\s*(\d+)", "waist"),
        (r"baju\s*(\d+)", "sleeves"),
        (r"seena\s*(\d+)", "chest"),
    ]:
        m = re.search(pattern, clean_text)
        if m:
            meas[name] = float(m.group(1))

    # Detect advance
    adv = None
    adv_match = re.search(
        r"(?:advance|adv)\s*(?:rs|rupees|cash)?\s*(\d+)", clean_text
    ) or re.search(r"(\d+)\s*(?:rs|rupees)?\s*(?:advance|adv)", clean_text)
    if adv_match:
        adv = float(adv_match.group(1))

    # Detect due date
    due_text = None
    for d in [
        "sunday",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "parso",
        "kal",
    ]:
        if d in clean_text:
            due_text = d.title()
            break

    fitting = (
        "Pichhli baar wali fitting" if "pichhli" in clean_text or "fitting" in clean_text else None
    )

    parsed = {
        "customer_name": None,
        "customer_phone": None,
        "garment_type": garment,
        "garment_color": color,
        "garment_fabric": None,
        "measurements": meas,
        "measurement_unit": "in",
        "due_date_text": due_text,
        "total_price": None,
        "advance_paid": adv,
        "fitting_preference": fitting,
        "additional_notes": "Sample extraction (Ollama offline fallback)",
    }

    draft = build_draft_from_parsed(parsed, request_text, model_name="sample-offline-heuristic")
    draft.review_flags.insert(
        0,
        ReviewFlag(
            field="system",
            severity=FlagSeverity.WARNING,
            message="PREVIEW ONLY: Generated via offline heuristic draft rules because Ollama was offline. Not a live model result.",
        ),
    )
    return draft
