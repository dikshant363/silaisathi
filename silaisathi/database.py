"""SQLite persistence layer for SilaiSathi.

Stores tailoring job cards locally and privately on the device.
Implements parameterized SQL, strict schema versioning, transaction isolation,
and verified backup/restore mechanisms.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from silaisathi.config import BACKUP_DIR, DB_PATH, ensure_data_directories
from silaisathi.schemas import JobCard, JobStatus, MeasurementUnit, PaymentInfo

SCHEMA_VERSION = 1


@contextmanager
def get_connection(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection with row factories and foreign keys enabled.

    Ensures connection is committed and closed cleanly on exit.
    """
    target_path = path or DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Path | None = None) -> None:
    """Initialize the SQLite database schema and indices."""
    target_path = path or DB_PATH
    ensure_data_directories()

    with get_connection(target_path) as conn:
        # Schema version table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            """
        )

        # Job cards table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_number TEXT UNIQUE NOT NULL,
                customer_name TEXT NOT NULL,
                customer_phone TEXT,
                garment_type TEXT NOT NULL,
                garment_color TEXT,
                garment_fabric TEXT,
                measurements_json TEXT NOT NULL DEFAULT '{}',
                measurement_unit TEXT NOT NULL DEFAULT 'in',
                due_date_text TEXT,
                due_date TEXT,
                due_date_confirmed INTEGER NOT NULL DEFAULT 0,
                total_price_paise INTEGER,
                advance_paid_paise INTEGER NOT NULL DEFAULT 0,
                balance_due_paise INTEGER,
                fitting_preference TEXT,
                notes TEXT,
                raw_request TEXT,
                status TEXT NOT NULL DEFAULT 'confirmed',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        # Indices for search, status filtering, and deadlines
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_job_number ON jobs (job_number);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_customer_name ON jobs (customer_name);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_customer_phone ON jobs (customer_phone);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_due_date ON jobs (due_date);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at);")

        # Record migration
        now_iso = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, applied_at)
            VALUES (?, ?);
            """,
            (SCHEMA_VERSION, now_iso),
        )


def _row_to_job(row: sqlite3.Row) -> JobCard:
    """Convert a SQLite row into a validated JobCard Pydantic object."""
    measurements = {}
    try:
        measurements = json.loads(row["measurements_json"] or "{}")
    except json.JSONDecodeError:
        measurements = {}

    payment = PaymentInfo(
        total_price_paise=row["total_price_paise"],
        advance_paid_paise=row["advance_paid_paise"] or 0,
    )

    return JobCard(
        id=row["id"],
        job_number=row["job_number"],
        customer_name=row["customer_name"],
        customer_phone=row["customer_phone"],
        garment_type=row["garment_type"],
        garment_color=row["garment_color"],
        garment_fabric=row["garment_fabric"],
        measurements=measurements,
        measurement_unit=MeasurementUnit(row["measurement_unit"] or "in"),
        due_date_text=row["due_date_text"],
        due_date=row["due_date"],
        due_date_confirmed=bool(row["due_date_confirmed"]),
        payment=payment,
        fitting_preference=row["fitting_preference"],
        notes=row["notes"],
        raw_request=row["raw_request"],
        status=JobStatus(row["status"] or "confirmed"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_job(job: JobCard, path: Path | None = None) -> JobCard:
    """Persist a new job card into the SQLite database."""
    target_path = path or DB_PATH
    now_iso = datetime.now(UTC).isoformat()

    measurements_json = json.dumps(job.measurements, ensure_ascii=False)

    with get_connection(target_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO jobs (
                job_number, customer_name, customer_phone, garment_type,
                garment_color, garment_fabric, measurements_json, measurement_unit,
                due_date_text, due_date, due_date_confirmed, total_price_paise,
                advance_paid_paise, balance_due_paise, fitting_preference,
                notes, raw_request, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                job.job_number,
                job.customer_name,
                job.customer_phone,
                job.garment_type,
                job.garment_color,
                job.garment_fabric,
                measurements_json,
                job.measurement_unit.value,
                job.due_date_text,
                job.due_date,
                1 if job.due_date_confirmed else 0,
                job.payment.total_price_paise,
                job.payment.advance_paid_paise,
                job.payment.balance_due_paise,
                job.fitting_preference,
                job.notes,
                job.raw_request,
                job.status.value,
                job.created_at or now_iso,
                now_iso,
            ),
        )
        job_id = cursor.lastrowid
        job.id = job_id
        job.updated_at = now_iso
        return job


def get_job_by_id(job_id: int, path: Path | None = None) -> JobCard | None:
    """Fetch a single job card by its numeric ID."""
    target_path = path or DB_PATH
    with get_connection(target_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?;", (job_id,)).fetchone()
        if not row:
            return None
        return _row_to_job(row)


def get_job_by_number(job_number: str, path: Path | None = None) -> JobCard | None:
    """Fetch a single job card by its unique job number."""
    target_path = path or DB_PATH
    with get_connection(target_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_number = ?;", (job_number,)).fetchone()
        if not row:
            return None
        return _row_to_job(row)


def update_job(job: JobCard, path: Path | None = None) -> JobCard:
    """Update all fields of an existing job card."""
    if not job.id:
        raise ValueError("Cannot update job card without an ID.")

    target_path = path or DB_PATH
    now_iso = datetime.now(UTC).isoformat()
    measurements_json = json.dumps(job.measurements, ensure_ascii=False)

    with get_connection(target_path) as conn:
        conn.execute(
            """
            UPDATE jobs SET
                customer_name = ?, customer_phone = ?, garment_type = ?,
                garment_color = ?, garment_fabric = ?, measurements_json = ?,
                measurement_unit = ?, due_date_text = ?, due_date = ?,
                due_date_confirmed = ?, total_price_paise = ?, advance_paid_paise = ?,
                balance_due_paise = ?, fitting_preference = ?, notes = ?,
                status = ?, updated_at = ?
            WHERE id = ?;
            """,
            (
                job.customer_name,
                job.customer_phone,
                job.garment_type,
                job.garment_color,
                job.garment_fabric,
                measurements_json,
                job.measurement_unit.value,
                job.due_date_text,
                job.due_date,
                1 if job.due_date_confirmed else 0,
                job.payment.total_price_paise,
                job.payment.advance_paid_paise,
                job.payment.balance_due_paise,
                job.fitting_preference,
                job.notes,
                job.status.value,
                now_iso,
                job.id,
            ),
        )
        job.updated_at = now_iso
        return job


def update_job_status(job_id: int, new_status: JobStatus, path: Path | None = None) -> bool:
    """Update only the status of a job card."""
    target_path = path or DB_PATH
    now_iso = datetime.now(UTC).isoformat()

    with get_connection(target_path) as conn:
        cursor = conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?;",
            (new_status.value, now_iso, job_id),
        )
        return cursor.rowcount > 0


def list_jobs(
    search_query: str = "",
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    path: Path | None = None,
) -> list[JobCard]:
    """Search and filter job cards with pagination."""
    target_path = path or DB_PATH

    query = "SELECT * FROM jobs WHERE 1=1"
    params: list[Any] = []

    if status_filter and status_filter.lower() != "all":
        query += " AND status = ?"
        params.append(status_filter.lower())

    if search_query and search_query.strip():
        term = f"%{search_query.strip()}%"
        query += " AND (customer_name LIKE ? OR customer_phone LIKE ? OR job_number LIKE ? OR garment_type LIKE ? OR notes LIKE ?)"
        params.extend([term, term, term, term, term])

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
    params.extend([limit, offset])

    with get_connection(target_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_job(r) for r in rows]


def get_dashboard_stats(path: Path | None = None) -> dict[str, int]:
    """Compute dashboard metric counters."""
    target_path = path or DB_PATH
    soon = (date.today() + timedelta(days=2)).isoformat()

    with get_connection(target_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM jobs WHERE status != 'cancelled';").fetchone()[0]
        awaiting = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status IN ('confirmed', 'in_progress');"
        ).fetchone()[0]
        completed = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'completed';"
        ).fetchone()[0]
        due_soon = conn.execute(
            """
            SELECT COUNT(*) FROM jobs
            WHERE status IN ('confirmed', 'in_progress')
              AND due_date IS NOT NULL
              AND due_date <= ?;
            """,
            (soon,),
        ).fetchone()[0]

        return {
            "total_jobs": total,
            "awaiting_work": awaiting,
            "due_soon": due_soon,
            "completed": completed,
        }


def delete_job(job_id: int, path: Path | None = None) -> bool:
    """Delete a job card by ID."""
    target_path = path or DB_PATH
    with get_connection(target_path) as conn:
        cursor = conn.execute("DELETE FROM jobs WHERE id = ?;", (job_id,))
        return cursor.rowcount > 0


def backup_database(backup_target_path: Path | None = None, path: Path | None = None) -> Path:
    """Create a point-in-time timestamped backup copy of the SQLite database."""
    source_path = path or DB_PATH
    if not source_path.exists():
        raise FileNotFoundError(f"Database file does not exist at {source_path}")

    ensure_data_directories()
    if backup_target_path:
        dest_path = backup_target_path
    else:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_path = BACKUP_DIR / f"silaisathi_backup_{timestamp_str}.sqlite3"

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(source_path) as source_conn:
        dest_conn = sqlite3.connect(str(dest_path), timeout=15.0)
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()

    return dest_path


def restore_database(backup_source_path: Path, path: Path | None = None) -> None:
    """Restore the database from a verified backup file."""
    if not backup_source_path.exists():
        raise FileNotFoundError(f"Backup file not found at {backup_source_path}")

    target_path = path or DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Verify backup is a valid SQLite database
    test_conn = sqlite3.connect(str(backup_source_path), timeout=10.0)
    try:
        test_conn.execute("PRAGMA schema_version;").fetchone()
    finally:
        test_conn.close()

    # Use SQLite's online backup API to copy pages into target safely
    source_conn = sqlite3.connect(str(backup_source_path), timeout=10.0)
    try:
        with get_connection(target_path) as target_conn:
            source_conn.backup(target_conn)
    finally:
        source_conn.close()
