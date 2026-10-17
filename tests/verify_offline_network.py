"""Offline Network Isolation Verification for SilaiSathi.

Simulates strict network isolation by intercepting all non-loopback socket connections.
Verifies that:
1. Ollama on 127.0.0.1:11434 remains fully operational.
2. Real LLM extraction (Qwen 3.5 4B) completes successfully.
3. Review, validation, SQLite storage, search, and slip generation succeed.
4. Any external network calls are blocked and recorded.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

# Track external connection attempts
external_attempts: list[tuple[str, int]] = []
original_connect = socket.socket.connect


def isolated_connect(self, address):
    host = address[0]
    port = address[1] if len(address) > 1 else 0

    # Allow loopback connections only (Ollama on 127.0.0.1 / localhost)
    if host in ("127.0.0.1", "localhost", "::1") or host.startswith("127."):
        return original_connect(self, address)

    external_attempts.append((str(host), int(port)))
    raise OSError(f"NETWORK ISOLATION ENFORCED: Outbound connection to {host}:{port} blocked.")


# Monkeypatch socket.connect before importing/running application modules
socket.socket.connect = isolated_connect


def run_offline_test():
    print("=" * 65)
    print("SILAISATHI OFFLINE NETWORK ISOLATION VERIFICATION")
    print("=" * 65)
    print("Network Guard Status: ACTIVE (Non-loopback sockets blocked)")

    # Test that external connections are indeed blocked
    print("\n[VERIFICATION 0] Verifying Network Isolation Guard")
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.settimeout(1.0)
        test_sock.connect(("8.8.8.8", 53))
        print("FAIL: External connection succeeded! Isolation guard failed.")
        sys.exit(1)
    except OSError as e:
        print(f"PASS: External connection blocked as expected ({e})")

    from silaisathi import database, orders, printing
    from silaisathi.extraction import check_ollama_health, extract_with_llm
    from silaisathi.schemas import JobCard, JobStatus, MeasurementUnit, PaymentInfo

    # Test 1: Ollama health check under isolation
    print("\n[VERIFICATION 1] Checking Local Ollama Health on 127.0.0.1")
    healthy, msg, models = check_ollama_health()
    print(f"  • Status: {msg}")
    print(f"  • Models available: {models}")
    assert healthy, "Ollama must be reachable on loopback"
    print("PASS: Ollama loopback connectivity confirmed.")

    # Test 2: Real Local Inference with Qwen 3.5 4B under isolation
    print("\n[VERIFICATION 2] Real Local Model Extraction under Isolation")
    request_text = (
        "Namaste ji. Ek red silk blouse silna hai deep round neck wala. "
        "Chest 36, kamar 30, length 15, sleeves 10. Kal sham tak urgent chahiye. "
        "500 advance pay kiya hai cash me."
    )
    print(f'  • Input: "{request_text}"')

    draft = extract_with_llm(
        customer_request=request_text,
        manual_customer_name="Pooja Sharma",
        manual_customer_phone="9876512345",
    )

    print("  • Extracted Garment:", draft.garment_type)
    print("  • Extracted Color:", draft.garment_color)
    print("  • Extracted Measurements:", draft.measurements)
    print("  • Extracted Advance:", draft.advance_paid)
    print("  • Total Price:", draft.total_price)
    print("  • Due Date Text:", draft.due_date_text)
    print("  • Resolved Due Date:", draft.due_date_resolved)

    assert draft.garment_type is not None, "Garment type must be extracted"
    assert draft.advance_paid == 500.0, "Advance must be 500.0"
    assert "chest" in draft.measurements, "Chest measurement must be present"
    assert "length" in draft.measurements, "Length measurement must be present"
    print("PASS: Real local inference succeeded under network isolation.")

    # Test 3: Save Job to Local SQLite Database
    print("\n[VERIFICATION 3] Saving Job to Local SQLite Database")
    test_db = Path("data/test_offline.db")
    test_db.parent.mkdir(parents=True, exist_ok=True)
    if test_db.exists():
        test_db.unlink()

    database.init_db(test_db)
    job_number = orders.generate_job_number(path=test_db)
    payment = PaymentInfo.from_rupees(total_rs=1200.0, advance_rs=draft.advance_paid or 0.0)

    job = JobCard(
        job_number=job_number,
        customer_name=draft.customer_name,
        customer_phone=draft.customer_phone,
        garment_type=draft.garment_type or "Blouse",
        garment_color=draft.garment_color,
        garment_fabric="Silk",
        measurements=draft.measurements,
        measurement_unit=MeasurementUnit.INCHES,
        due_date=draft.due_date_resolved,
        due_date_confirmed=True,
        payment=payment,
        fitting_preference=draft.fitting_preference,
        notes="Deep round neck",
        raw_request=request_text,
        status=JobStatus.CONFIRMED,
    )

    created_job = database.create_job(job, path=test_db)
    print(f"  • Created Job: {created_job.job_number} (ID: {created_job.id})")
    print(f"  • Total: ₹{created_job.payment.total_price_rs}")
    print(f"  • Advance: ₹{created_job.payment.advance_paid_rs}")
    print(f"  • Balance: ₹{created_job.payment.balance_due_rs}")
    assert created_job.payment.balance_due_rs == 700.0, "Deterministic balance must be 700.0"
    print("PASS: SQLite persistence and integer paise arithmetic succeeded.")

    # Test 4: Search and Retrieve from SQLite
    print("\n[VERIFICATION 4] Searching Local SQLite Database")
    search_results = database.list_jobs(search_query="Pooja", path=test_db)
    assert len(search_results) == 1, "Must find saved job by customer name"
    retrieved_job = search_results[0]
    print(f"  • Retrieved: {retrieved_job.customer_name} ({retrieved_job.job_number})")
    print("PASS: Local search succeeded.")

    # Test 5: Generate Printable Karigar Work Slip
    print("\n[VERIFICATION 5] Generating Printable Karigar Slip & Receipt")
    slip_html = printing.generate_printable_html(retrieved_job, shop_name="SilaiSathi Workshop")
    assert "SilaiSathi Workshop" in slip_html
    assert "Pooja Sharma" in slip_html
    assert "₹700.00" in slip_html
    assert "कटाई (Cutting)" in slip_html
    print(f"  • Generated Slip HTML ({len(slip_html)} chars)")
    print("PASS: Work slip generation succeeded.")

    # Test 6: Verify Zero External Requests
    print("\n[VERIFICATION 6] Checking External Connection Attempts")
    # We ignore the initial intentional test probe to 8.8.8.8
    real_external = [att for att in external_attempts if att != ("8.8.8.8", 53)]
    print(f"  • Total external calls attempted during workflow: {len(real_external)}")
    if real_external:
        print(f"FAIL: The following external calls were attempted: {real_external}")
        sys.exit(1)
    else:
        print("PASS: ZERO external network connections attempted during entire workflow.")

    # Clean up test database
    if test_db.exists():
        test_db.unlink()

    print("\n" + "=" * 65)
    print("ALL 6 OFFLINE NETWORK ISOLATION CHECKS PASSED!")
    print("Evidence: SilaiSathi operates 100% offline via loopback 127.0.0.1")
    print("=" * 65)


if __name__ == "__main__":
    run_offline_test()
