"""Order lifecycle management, job numbering, and safe CSV export for SilaiSathi."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from silaisathi import database
from silaisathi.schemas import JobCard, JobStatus
from silaisathi.validation import sanitize_for_csv

# Valid state transitions
VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.DRAFT: {JobStatus.CONFIRMED, JobStatus.CANCELLED},
    JobStatus.CONFIRMED: {JobStatus.IN_PROGRESS, JobStatus.CANCELLED},
    JobStatus.IN_PROGRESS: {JobStatus.READY, JobStatus.CONFIRMED, JobStatus.CANCELLED},
    JobStatus.READY: {JobStatus.COMPLETED, JobStatus.IN_PROGRESS, JobStatus.CANCELLED},
    JobStatus.COMPLETED: {JobStatus.IN_PROGRESS},  # For re-fitting/alterations
    JobStatus.CANCELLED: {JobStatus.CONFIRMED},  # Re-opening
}


def generate_job_number() -> str:
    """Generate a clean, professional, sequential job number e.g. SS-2610-0042."""
    now = datetime.now()
    year_month = now.strftime("%y%m")

    # Count jobs created in this month
    stats = database.get_dashboard_stats()
    total_existing = stats["total_jobs"] + stats["completed"]
    seq = (total_existing % 9999) + 1

    return f"SS-{year_month}-{seq:04d}"


def is_valid_status_transition(current: JobStatus, target: JobStatus) -> bool:
    """Verify if a state transition is permitted in the business workflow."""
    if current == target:
        return True
    return target in VALID_TRANSITIONS.get(current, set())


def check_potential_duplicate(
    customer_name: str,
    customer_phone: str | None,
    garment_type: str,
    raw_request: str | None = None,
) -> JobCard | None:
    """Check if a similar job was submitted recently to prevent accidental double-clicks."""
    if not customer_phone and not customer_name:
        return None

    recent_jobs = database.list_jobs(
        search_query=customer_phone or customer_name,
        limit=10,
    )

    for job in recent_jobs:
        if job.status == JobStatus.CANCELLED:
            continue
        # Compare name, phone, garment type and optionally request
        same_customer = (customer_phone and job.customer_phone == customer_phone) or (
            job.customer_name.strip().lower() == customer_name.strip().lower()
        )
        same_garment = job.garment_type.strip().lower() == garment_type.strip().lower()

        if (
            same_customer
            and same_garment
            and raw_request
            and job.raw_request
            and job.raw_request.strip() == raw_request.strip()
        ):
            return job

    return None


def export_jobs_to_csv(jobs: list[JobCard]) -> str:
    """Export job records into a sanitized CSV format safe against spreadsheet formula injection."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header
    writer.writerow(
        [
            "Job Number",
            "Customer Name",
            "Phone",
            "Garment Type",
            "Color",
            "Fabric",
            "Due Date",
            "Status",
            "Total (₹)",
            "Advance (₹)",
            "Balance Due (₹)",
            "Measurements",
            "Fitting Preference",
            "Notes",
            "Created At",
        ]
    )

    for job in jobs:
        meas_str = ", ".join(
            f"{k}: {v}{job.measurement_unit.value}" for k, v in job.measurements.items()
        )
        total_str = f"{job.total_price_rs:.2f}" if job.total_price_rs is not None else "Unset"
        advance_str = f"{job.advance_paid_rs:.2f}"
        balance_str = f"{job.balance_due_rs:.2f}" if job.balance_due_rs is not None else "Unset"

        writer.writerow(
            [
                sanitize_for_csv(job.job_number),
                sanitize_for_csv(job.customer_name),
                sanitize_for_csv(job.customer_phone or ""),
                sanitize_for_csv(job.garment_type),
                sanitize_for_csv(job.garment_color or ""),
                sanitize_for_csv(job.garment_fabric or ""),
                sanitize_for_csv(job.due_date or job.due_date_text or ""),
                sanitize_for_csv(job.status.value),
                sanitize_for_csv(total_str),
                sanitize_for_csv(advance_str),
                sanitize_for_csv(balance_str),
                sanitize_for_csv(meas_str),
                sanitize_for_csv(job.fitting_preference or ""),
                sanitize_for_csv(job.notes or ""),
                sanitize_for_csv(job.created_at),
            ]
        )

    return output.getvalue()
