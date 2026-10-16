"""Validation, sanitization, and date/financial business rules for SilaiSathi.

Deterministic rules:
1. Never allow the LLM to calculate authoritative financial balances.
2. Never silently convert ambiguous relative dates (e.g. "Sunday") into an unverified deadline.
3. Sanitize inputs against prompt injection and exports against CSV formula injection.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from silaisathi.config import MAX_INPUT_LENGTH
from silaisathi.schemas import FlagSeverity, MeasurementUnit, PaymentInfo, ReviewFlag

# Suspicious prompt injection markers
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above)\s+instructions", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"you\s+are\s+now\s+a", re.I),
    re.compile(r"<\s*script", re.I),
    re.compile(r"drop\s+table", re.I),
    re.compile(r"delete\s+from", re.I),
    re.compile(r"exec(\s+|\()", re.I),
]

# Days of week mapping in English and Hindi/Hinglish
WEEKDAY_MAP = {
    "monday": 0,
    "somvar": 0,
    "somwaar": 0,
    "somwar": 0,
    "tuesday": 1,
    "mangal": 1,
    "mangalvar": 1,
    "mangalwaar": 1,
    "wednesday": 2,
    "budh": 2,
    "budhvar": 2,
    "budhwaar": 2,
    "thursday": 3,
    "guruvar": 3,
    "guruwaar": 3,
    "brihaspativar": 3,
    "veerwar": 3,
    "friday": 4,
    "shukravar": 4,
    "shukrawaar": 4,
    "jumma": 4,
    "saturday": 5,
    "shanivar": 5,
    "shaniwaar": 5,
    "shani": 5,
    "sunday": 6,
    "itvar": 6,
    "itwar": 6,
    "itwaar": 6,
    "ravivar": 6,
    "raviwaar": 6,
}

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def normalize_indic_digits(text: str) -> str:
    """Normalize Devanagari numerals (०-९) to standard ASCII digits (0-9)."""
    return text.translate(DEVANAGARI_DIGITS)


def validate_request_text(text: str) -> tuple[bool, str]:
    """Validate customer request text for length and cleanliness."""
    if not text or not text.strip():
        return False, "Customer request cannot be empty."

    if len(text) > MAX_INPUT_LENGTH:
        return (
            False,
            f"Customer request exceeds maximum allowed length of {MAX_INPUT_LENGTH} characters (got {len(text)}).",
        )

    return True, "Valid request."


def check_prompt_injection(text: str) -> bool:
    """Return True if text contains common prompt injection phrases."""
    return any(pattern.search(text) for pattern in INJECTION_PATTERNS)


def sanitize_for_csv(value: Any) -> str:
    """Sanitize a value for safe CSV export to prevent spreadsheet formula injection.

    Prepends a single quote if the field starts with =, +, -, @, tab, or carriage return.
    """
    if value is None:
        return ""

    text = str(value)
    # Characters that Excel/Calc interpret as formulas or commands
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{text}"
    return text


def resolve_due_date(
    date_text: str | None,
    base_date: date | None = None,
) -> tuple[str | None, bool, str]:
    """Safely parse or resolve due date text.

    Returns:
        (resolved_iso_date, needs_confirmation, explanation_reason)
    """
    if not date_text or not date_text.strip():
        return None, True, "No due date specified in request."

    ref_date = base_date or datetime.now(UTC).date()
    cleaned = date_text.strip().lower()

    # Relative day keywords
    if cleaned in ("aaj", "today"):
        return ref_date.isoformat(), False, "Resolved to today"

    if cleaned in ("kal", "tomorrow"):
        target = ref_date + timedelta(days=1)
        return target.isoformat(), False, "Resolved to tomorrow (kal)"

    if cleaned in ("parso", "parson", "day after tomorrow"):
        target = ref_date + timedelta(days=2)
        return target.isoformat(), False, "Resolved to day after tomorrow (parso)"

    # Check for weekday (e.g. "Sunday", "ravivaar", "itwaar")
    for name, target_weekday in WEEKDAY_MAP.items():
        if re.search(rf"\b{name}\b", cleaned):
            days_ahead = (target_weekday - ref_date.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # Next occurrence
            candidate = ref_date + timedelta(days=days_ahead)
            return (
                candidate.isoformat(),
                True,  # Crucial: Relative weekday MUST be confirmed by user!
                f"Candidate relative day '{date_text.title()}' points to {candidate.strftime('%d %b %Y')}. Requires confirmation.",
            )

    # Check for direct ISO date YYYY-MM-DD
    iso_match = re.search(r"\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b", cleaned)
    if iso_match:
        try:
            y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
            parsed = date(y, m, d)
            return parsed.isoformat(), False, "Explicit calendar date"
        except ValueError:
            pass

    # Check for Day Month (e.g. "15 oct", "25 november", "12 tarikh")
    month_names = {
        "jan": 1,
        "january": 1,
        "janwari": 1,
        "feb": 2,
        "february": 2,
        "farwari": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "mai": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }

    dm_match = re.search(r"\b(\d{1,2})\s*([a-zA-Z]+)\b", cleaned)
    if dm_match:
        day_val = int(dm_match.group(1))
        m_word = dm_match.group(2).lower()
        if m_word in month_names and 1 <= day_val <= 31:
            m_val = month_names[m_word]
            year_val = ref_date.year
            # If date has already passed this year, assume next year
            try:
                candidate = date(year_val, m_val, day_val)
                if candidate < ref_date:
                    candidate = date(year_val + 1, m_val, day_val)
                return (
                    candidate.isoformat(),
                    False,
                    f"Resolved to {candidate.strftime('%d %b %Y')}",
                )
            except ValueError:
                pass

    # Ambiguous date text (e.g. "jaldi chahiye", "end of week", "agla mahina")
    return (
        None,
        True,
        f"Ambiguous date phrase '{date_text}'. Please specify an exact delivery date.",
    )


def validate_measurements_plausibility(
    measurements: dict[str, float],
    unit: MeasurementUnit = MeasurementUnit.INCHES,
) -> list[ReviewFlag]:
    """Validate measurements for positive values and standard human body ranges."""
    flags: list[ReviewFlag] = []

    # Standard plausible adult body ranges in inches
    plausible_inch_ranges = {
        "chest": (24.0, 60.0),
        "bust": (24.0, 60.0),
        "waist": (20.0, 56.0),
        "hips": (24.0, 64.0),
        "length": (10.0, 65.0),
        "shoulder": (10.0, 24.0),
        "sleeves": (4.0, 32.0),
        "collar": (10.0, 22.0),
        "inseam": (15.0, 38.0),
        "outseam": (25.0, 48.0),
    }

    factor = 2.54 if unit == MeasurementUnit.CENTIMETERS else 1.0

    for field_name, value in measurements.items():
        if value <= 0:
            flags.append(
                ReviewFlag(
                    field=f"measurements.{field_name}",
                    severity=FlagSeverity.CRITICAL,
                    message=f"Measurement '{field_name}' must be positive (got {value}).",
                )
            )
            continue

        base_key = field_name.lower().strip()
        if base_key in plausible_inch_ranges:
            min_val, max_val = plausible_inch_ranges[base_key]
            min_val *= factor
            max_val *= factor
            if value < min_val or value > max_val:
                flags.append(
                    ReviewFlag(
                        field=f"measurements.{field_name}",
                        severity=FlagSeverity.WARNING,
                        message=f"{field_name.title()} value of {value} {unit.value} is outside common range ({min_val:.0f}-{max_val:.0f} {unit.value}). Please verify.",
                    )
                )

    return flags


def calculate_payment_info(total_rs: float | None, advance_rs: float | None) -> PaymentInfo:
    """Deterministic financial calculations using integer paise."""
    return PaymentInfo.from_rupees(total_rs, advance_rs)
