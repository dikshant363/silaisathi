"""Pydantic schemas and domain models for SilaiSathi.

Enforces strict schema validation, type safety, deterministic money representations
(using integer paise), and audit tracking of AI-extracted vs human-confirmed data.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class MeasurementUnit(StrEnum):
    INCHES = "in"
    CENTIMETERS = "cm"


class JobStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FlagSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ReviewFlag(BaseModel):
    """Flag highlighting an ambiguous, unverified, or missing field in the draft."""

    field: str
    severity: FlagSeverity
    message: str


class PaymentInfo(BaseModel):
    """Deterministic payment representation using integer paise to eliminate floating-point drift.

    1 Rupee = 100 Paise.
    Authoritative calculations occur strictly in integer arithmetic.
    """

    total_price_paise: int | None = Field(
        default=None,
        description="Total agreed price in paise. None if customer did not state price.",
    )
    advance_paid_paise: int = Field(
        default=0,
        description="Advance payment received in paise. Defaults to 0.",
    )
    balance_due_paise: int | None = Field(
        default=None,
        description="Remaining balance in paise. None if total price is unknown.",
    )
    is_excess_advance: bool = False
    is_balance_unknown: bool = False

    @field_validator("total_price_paise")
    @classmethod
    def validate_total(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("Total price cannot be negative.")
        return v

    @field_validator("advance_paid_paise")
    @classmethod
    def validate_advance(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Advance payment cannot be negative.")
        return v

    @model_validator(mode="after")
    def calculate_balance_and_flags(self) -> PaymentInfo:
        # Calculate balance only when total price is known
        if self.total_price_paise is None:
            self.balance_due_paise = None
            self.is_balance_unknown = True
            self.is_excess_advance = False
        else:
            self.is_balance_unknown = False
            balance = self.total_price_paise - self.advance_paid_paise
            self.balance_due_paise = balance
            self.is_excess_advance = self.advance_paid_paise > self.total_price_paise
        return self

    @classmethod
    def from_rupees(cls, total_rs: float | None, advance_rs: float | None = 0.0) -> PaymentInfo:
        """Create PaymentInfo safely from decimal rupee amounts."""
        total_paise: int | None = None
        if total_rs is not None and not math.isnan(total_rs):
            if total_rs < 0:
                raise ValueError("Total price cannot be negative.")
            total_paise = round(total_rs * 100)

        advance_paise = 0
        if advance_rs is not None and not math.isnan(advance_rs):
            if advance_rs < 0:
                raise ValueError("Advance payment cannot be negative.")
            advance_paise = round(advance_rs * 100)

        return cls(total_price_paise=total_paise, advance_paid_paise=advance_paise)

    @property
    def total_price_rs(self) -> float | None:
        return self.total_price_paise / 100.0 if self.total_price_paise is not None else None

    @property
    def advance_paid_rs(self) -> float:
        return self.advance_paid_paise / 100.0

    @property
    def balance_due_rs(self) -> float | None:
        return self.balance_due_paise / 100.0 if self.balance_due_paise is not None else None

    def display_balance(self) -> str:
        if self.is_balance_unknown:
            return "Unknown (Total not set)"
        if self.balance_due_rs is not None and self.balance_due_rs <= 0:
            return "Fully Paid (₹0.00)"
        return f"₹{self.balance_due_rs:.2f}"


class ExtractedDraft(BaseModel):
    """Raw structured data extracted by local LLM prior to human confirmation."""

    customer_name: str | None = None
    customer_phone: str | None = None
    garment_type: str | None = None
    garment_color: str | None = None
    garment_fabric: str | None = None
    measurements: dict[str, float] = Field(default_factory=dict)
    measurement_unit: MeasurementUnit = MeasurementUnit.INCHES
    due_date_text: str | None = None
    due_date_resolved: str | None = None  # ISO format YYYY-MM-DD
    due_date_needs_confirmation: bool = True
    total_price: float | None = None
    advance_paid: float | None = None
    fitting_preference: str | None = None
    additional_notes: str | None = None

    # Audit & Review Flags
    supplied_facts: list[str] = Field(default_factory=list)
    model_interpretations: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    ambiguous_fields: list[str] = Field(default_factory=list)
    review_flags: list[ReviewFlag] = Field(default_factory=list)

    raw_request: str = ""
    model_name: str = "qwen3.5:4b"
    extracted_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class JobCard(BaseModel):
    """Authoritative, persisted tailoring job card approved by human tailor."""

    id: int | None = None
    job_number: str = Field(..., description="Unique human-readable ID e.g. SS-2610-001")
    customer_name: str = Field(..., min_length=1, max_length=100)
    customer_phone: str | None = Field(default=None, max_length=20)
    garment_type: str = Field(..., min_length=1, max_length=50)
    garment_color: str | None = None
    garment_fabric: str | None = None
    measurements: dict[str, float] = Field(default_factory=dict)
    measurement_unit: MeasurementUnit = MeasurementUnit.INCHES
    due_date_text: str | None = None
    due_date: str | None = None  # ISO format YYYY-MM-DD
    due_date_confirmed: bool = False
    payment: PaymentInfo
    fitting_preference: str | None = None
    notes: str | None = None
    raw_request: str | None = None
    status: JobStatus = JobStatus.CONFIRMED
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @field_validator("measurements")
    @classmethod
    def validate_measurements(cls, v: dict[str, float]) -> dict[str, float]:
        clean: dict[str, float] = {}
        for k, val in v.items():
            if val is not None and not math.isnan(val):
                if val <= 0:
                    raise ValueError(f"Measurement '{k}' must be positive, got {val}")
                clean[k.strip().lower()] = round(float(val), 2)
        return clean

    @property
    def total_price_rs(self) -> float | None:
        return self.payment.total_price_rs

    @property
    def advance_paid_rs(self) -> float:
        return self.payment.advance_paid_rs

    @property
    def balance_due_rs(self) -> float | None:
        return self.payment.balance_due_rs
