"""SilaiSathi — Local-First AI Assistant Workstation for Tailoring Shops.

Transforms natural-language tailoring requests (Hindi, Hinglish, English)
into structured, editable, and printable job cards using local open-weight models.
Runs completely offline on Apple Silicon / macOS via Ollama and SQLite.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from silaisathi import database, orders, printing
from silaisathi.config import (
    BACKUP_DIR,
    DEFAULT_MODEL,
    GARMENT_TYPES,
    POPULAR_MEASUREMENTS,
    ensure_data_directories,
)
from silaisathi.extraction import (
    check_ollama_health,
    extract_with_llm,
    generate_sample_draft,
)
from silaisathi.schemas import (
    ExtractedDraft,
    FlagSeverity,
    JobCard,
    JobStatus,
    MeasurementUnit,
    PaymentInfo,
)
from silaisathi.validation import (
    validate_request_text,
)

# ---------------------------------------------------------------------------
# Streamlit Page Setup & Styling
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SilaiSathi — Tailoring Studio",
    page_icon="✂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
/* Apple-inspired clean typography and subtle borders */
.main {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
.metric-card {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
}
.metric-card h3 {
    margin: 0;
    font-size: 28px;
    font-weight: 700;
    color: #0f172a;
}
.metric-card p {
    margin: 4px 0 0 0;
    font-size: 13px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.status-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 9999px;
    font-size: 12px;
    font-weight: 600;
}
.badge-draft { background-color: #f1f5f9; color: #475569; }
.badge-confirmed { background-color: #eff6ff; color: #1d4ed8; }
.badge-in_progress { background-color: #fff7ed; color: #c2410c; }
.badge-ready { background-color: #faf5ff; color: #7e22ce; }
.badge-completed { background-color: #f0fdf4; color: #15803d; }
.badge-cancelled { background-color: #fef2f2; color: #b91c1c; }

.privacy-banner {
    background-color: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    color: #166534;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.offline-banner {
    background-color: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    color: #92400e;
    margin-bottom: 16px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------

ensure_data_directories()
database.init_db()

if "active_view" not in st.session_state:
    st.session_state.active_view = "Dashboard"

if "current_draft" not in st.session_state:
    st.session_state.current_draft = None

if "editing_job" not in st.session_state:
    st.session_state.editing_job = None

if "print_job_id" not in st.session_state:
    st.session_state.print_job_id = None

if "selected_sample_id" not in st.session_state:
    st.session_state.selected_sample_id = None


def switch_view(view_name: str) -> None:
    """Safely change view."""
    st.session_state.active_view = view_name


# ---------------------------------------------------------------------------
# Sidebar & Local Environment Health
# ---------------------------------------------------------------------------

ollama_online, ollama_msg, installed_models = check_ollama_health()

with st.sidebar:
    st.title("✂️ SilaiSathi")
    st.caption("Offline-First Tailoring Workstation")

    # Local Engine Status Indicator
    if ollama_online:
        st.markdown(
            """
            <div style="background-color: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 6px; padding: 8px; font-size: 12px; color: #065f46;">
                <strong>🟢 Ollama Active</strong><br>
                Local loopback inference ready.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="background-color: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 8px; font-size: 12px; color: #92400e;">
                <strong>🟡 Ollama Offline</strong><br>
                Heuristic sample mode enabled. Run <code>ollama serve</code> to activate AI.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")
    nav_options = [
        "Dashboard",
        "New Job (AI Assistant)",
        "Review & Edit",
        "Print Work Slip",
        "Data & Privacy",
    ]
    chosen_view = st.radio(
        "Navigation",
        options=nav_options,
        index=nav_options.index(st.session_state.active_view)
        if st.session_state.active_view in nav_options
        else 0,
        key="nav_radio",
    )
    if chosen_view != st.session_state.active_view:
        st.session_state.active_view = chosen_view
        st.rerun()

    st.divider()

    # Model selector if Ollama is online
    if ollama_online and installed_models:
        default_idx = (
            installed_models.index(DEFAULT_MODEL) if DEFAULT_MODEL in installed_models else 0
        )
        selected_model = st.selectbox(
            "AI Model",
            options=installed_models,
            index=default_idx,
            help="Locally running open-weight model inside Ollama.",
        )
    else:
        selected_model = DEFAULT_MODEL
        st.caption(f"Configured Model: `{DEFAULT_MODEL}`")

    st.divider()
    st.caption("🔒 **Privacy Guarantee**")
    st.caption(
        "• Bound to 127.0.0.1 (Loopback)\n• 0 Cloud Telemetry / External APIs\n• Data stored in local SQLite"
    )


# ---------------------------------------------------------------------------
# VIEW 1: DASHBOARD
# ---------------------------------------------------------------------------

if st.session_state.active_view == "Dashboard":
    col_head1, col_head2 = st.columns([3, 1])
    with col_head1:
        st.title("Workshop Job Desk")
        st.caption("Real-time local job cards, pending alterations, and workshop schedules")
    with col_head2:
        st.write("")
        if st.button("➕ Create New Job", type="primary", use_container_width=True):
            switch_view("New Job (AI Assistant)")
            st.rerun()

    # Dashboard Metrics
    stats = database.get_dashboard_stats()
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f'<div class="metric-card"><h3>{stats["total_jobs"]}</h3><p>Total Active Jobs</p></div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="metric-card"><h3>{stats["awaiting_work"]}</h3><p>Awaiting Work</p></div>',
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f'<div class="metric-card"><h3>{stats["due_soon"]}</h3><p>Due Soon / Overdue</p></div>',
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f'<div class="metric-card"><h3>{stats["completed"]}</h3><p>Completed Jobs</p></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    # Search & Filter Bar
    f1, f2, f3 = st.columns([3, 2, 1])
    with f1:
        search_query = st.text_input(
            "🔍 Search orders", placeholder="Customer name, phone, garment type, or job #..."
        )
    with f2:
        status_filter = st.selectbox(
            "Filter by Status",
            options=[
                "All Statuses",
                "Confirmed",
                "In Progress",
                "Ready",
                "Completed",
                "Cancelled",
                "Draft",
            ],
            index=0,
        )
    with f3:
        st.write("")
        st.write("")
        if st.button("Reset Filters", use_container_width=True):
            search_query = ""
            status_filter = "All Statuses"

    status_filter_val = (
        None if status_filter == "All Statuses" else status_filter.lower().replace(" ", "_")
    )
    jobs = database.list_jobs(search_query=search_query or None, status_filter=status_filter_val)

    if not jobs:
        st.info(
            "No tailoring jobs found matching the selected filters. Click 'Create New Job' to record your first order."
        )
    else:
        # Render clean cards for each job
        for job in jobs:
            with st.container(border=True):
                c_top1, c_top2, c_top3, c_top4 = st.columns([2, 3, 2, 3])
                with c_top1:
                    st.markdown(f"**`{job.job_number}`**")
                    status_class = f"badge-{job.status.value}"
                    st.markdown(
                        f'<span class="status-badge {status_class}">{job.status.value.replace("_", " ").upper()}</span>',
                        unsafe_allow_html=True,
                    )

                with c_top2:
                    st.markdown(f"**{job.customer_name}**")
                    if job.customer_phone:
                        st.caption(f"📞 {job.customer_phone}")
                    garment_desc = f"{job.garment_color or ''} {job.garment_fabric or ''} {job.garment_type}".strip()
                    st.write(f"👗 {garment_desc}")

                with c_top3:
                    if job.due_date:
                        due_label = f"📅 Due: {job.due_date}"
                        if not job.due_date_confirmed:
                            due_label += " *(Unconfirmed)*"
                        st.write(due_label)
                    elif job.due_date_text:
                        st.write(f"📅 Due: {job.due_date_text} *(Unconfirmed)*")
                    else:
                        st.caption("📅 Due: Not specified")

                    # Payment Summary
                    if job.total_price_rs is not None:
                        st.caption(
                            f"Total: ₹{job.total_price_rs:.0f} | Bal: ₹{job.balance_due_rs:.0f}"
                        )
                    else:
                        st.caption(f"Advance: ₹{job.advance_paid_rs:.0f} | Bal: Unknown")

                with c_top4:
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        if st.button("✏️ Edit", key=f"edit_{job.id}", use_container_width=True):
                            st.session_state.editing_job = job
                            st.session_state.current_draft = None
                            switch_view("Review & Edit")
                            st.rerun()
                    with b2:
                        if st.button("🖨️ Slip", key=f"print_{job.id}", use_container_width=True):
                            st.session_state.print_job_id = job.id
                            switch_view("Print Work Slip")
                            st.rerun()
                    with b3:
                        # Quick advance status
                        if job.status == JobStatus.CONFIRMED and st.button(
                            "▶️ Start",
                            key=f"start_{job.id}",
                            use_container_width=True,
                            help="Mark In Progress",
                        ):
                            database.update_job_status(job.id, JobStatus.IN_PROGRESS)
                            st.rerun()
                        elif job.status == JobStatus.IN_PROGRESS and st.button(
                            "✅ Done",
                            key=f"done_{job.id}",
                            use_container_width=True,
                            help="Mark Ready",
                        ):
                            database.update_job_status(job.id, JobStatus.READY)
                            st.rerun()
                        elif job.status == JobStatus.READY and st.button(
                            "📦 Deliver",
                            key=f"deliv_{job.id}",
                            use_container_width=True,
                            help="Mark Completed",
                        ):
                            database.update_job_status(job.id, JobStatus.COMPLETED)
                            st.rerun()


# ---------------------------------------------------------------------------
# VIEW 2: NEW JOB (AI ASSISTANT)
# ---------------------------------------------------------------------------

elif st.session_state.active_view == "New Job (AI Assistant)":
    st.title("New Tailoring Job Request")
    st.caption(
        "Enter customer request in Hindi, Hinglish, or English. Local AI extracts measurements, deadlines, and pricing."
    )

    # Load fictional sample requests for fast testing/demonstration
    sample_path = Path("samples/fictional_requests.json")
    samples_data = []
    if sample_path.exists():
        try:
            with open(sample_path, encoding="utf-8") as f:
                samples_data = json.load(f)
        except Exception:
            samples_data = []

    with st.expander("💡 Quick Sample Requests (Hindi / Hinglish / English)", expanded=False):
        st.caption("Click any sample scenario below to automatically load the request text.")
        s_cols = st.columns(4)
        for i, s in enumerate(samples_data):
            col_target = s_cols[i % 4]
            with col_target:
                if st.button(
                    f"{s['title']}", key=f"sample_btn_{s['id']}", use_container_width=True
                ):
                    st.session_state.sample_request_loaded = s["request_text"]
                    st.session_state.sample_name_loaded = s.get("customer_name", "")
                    st.session_state.sample_phone_loaded = s.get("customer_phone", "")
                    st.rerun()

    # Pre-populate if sample selected
    default_text = st.session_state.get("sample_request_loaded", "")
    default_name = st.session_state.get("sample_name_loaded", "")
    default_phone = st.session_state.get("sample_phone_loaded", "")

    # Input Form
    with st.form("new_job_form"):
        st.subheader("1. Customer Information (Optional Overrides)")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            customer_name_in = st.text_input(
                "Customer Name", value=default_name, placeholder="e.g. Meena Kumari / सुनीता"
            )
        with col_c2:
            customer_phone_in = st.text_input(
                "Customer Phone", value=default_phone, placeholder="e.g. 9876543210"
            )

        st.subheader("2. Customer Tailoring Request")
        request_text_in = st.text_area(
            "Raw Tailoring Request (Hindi / Hinglish / English)",
            value=default_text,
            height=130,
            placeholder="Bhaiya, blue kurti Sunday tak chahiye. Length 44, chest 38, sleeves 18. Pichhli baar wali fitting rakhna. 300 advance de diya.",
            help="Describe garment, measurements, color, deadlines, preferences, or payment details.",
        )

        char_count = len(request_text_in)
        if char_count > 2000:
            st.error(f"Character count: {char_count}/2000 — Please shorten the request text.")
        else:
            st.caption(f"Character count: {char_count}/2000 characters")

        btn_c1, btn_c2, _ = st.columns([2, 2, 3])
        with btn_c1:
            submit_ai = st.form_submit_button(
                "⚡ Extract with Local AI", type="primary", use_container_width=True
            )
        with btn_c2:
            submit_sample = st.form_submit_button(
                "🧪 Test Offline Heuristic", use_container_width=True
            )

    if submit_ai:
        if not request_text_in.strip():
            st.warning("Please enter a customer request before extracting.")
        else:
            valid, msg = validate_request_text(request_text_in)
            if not valid:
                st.error(msg)
            else:
                with st.spinner(
                    f"Extracting structured tailoring fields using local model `{selected_model}`..."
                ):
                    try:
                        draft = extract_with_llm(
                            customer_request=request_text_in,
                            model_name=selected_model,
                            manual_customer_name=customer_name_in or None,
                            manual_customer_phone=customer_phone_in or None,
                        )
                        st.session_state.current_draft = draft
                        st.session_state.editing_job = None
                        switch_view("Review & Edit")
                        st.rerun()
                    except ConnectionError as exc:
                        st.error(f"⚠️ {exc}")
                        st.info(
                            "Tip: You can use the '🧪 Test Offline Heuristic' button right next to it to test the workflow without a running Ollama server."
                        )
                    except Exception as exc:
                        st.error(f"Extraction error: {str(exc)}")

    if submit_sample:
        if not request_text_in.strip():
            st.warning("Please enter a customer request.")
        else:
            with st.spinner("Generating sample extraction draft..."):
                draft = generate_sample_draft(request_text_in)
                if customer_name_in:
                    draft.customer_name = customer_name_in
                if customer_phone_in:
                    draft.customer_phone = customer_phone_in
                st.session_state.current_draft = draft
                st.session_state.editing_job = None
                switch_view("Review & Edit")
                st.rerun()


# ---------------------------------------------------------------------------
# VIEW 3: REVIEW & EDIT DRAFT
# ---------------------------------------------------------------------------

elif st.session_state.active_view == "Review & Edit":
    st.title("Review & Approve Job Card")
    st.caption(
        "Verify extracted facts, confirm ambiguous deadlines, and check financial balances before committing to database."
    )

    draft: ExtractedDraft | None = st.session_state.current_draft
    editing_job: JobCard | None = st.session_state.editing_job

    if not draft and not editing_job:
        st.info("No active draft or job selected for review.")
        if st.button("➕ Create New Job"):
            switch_view("New Job (AI Assistant)")
            st.rerun()
    else:
        # Determine source information
        is_editing_existing = editing_job is not None
        raw_text = draft.raw_request if draft else (editing_job.raw_request if editing_job else "")

        # Display Review Flags
        if draft and draft.review_flags:
            for flag in draft.review_flags:
                if flag.severity == FlagSeverity.WARNING:
                    st.warning(f"⚠️ **{flag.field.upper()}**: {flag.message}")
                elif flag.severity == FlagSeverity.INFO:
                    st.info(f"ℹ️ **{flag.field.upper()}**: {flag.message}")

        # Side-by-side or collapsible source request display
        with st.expander("📄 Original Customer Request (Untrusted Input)", expanded=True):
            st.code(raw_text or "No raw request text available.", language="text")

            if draft:
                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    st.markdown("**📌 Customer-Supplied Facts:**")
                    if draft.supplied_facts:
                        for fact in draft.supplied_facts:
                            st.markdown(f"- {fact}")
                    else:
                        st.caption("None identified.")
                with f_col2:
                    st.markdown("**🤖 Model Interpretations:**")
                    if draft.model_interpretations:
                        for interp in draft.model_interpretations:
                            st.markdown(f"- {interp}")
                    else:
                        st.caption("None.")

        st.divider()

        # Pre-fill initial form values
        init_name = (
            editing_job.customer_name if is_editing_existing else (draft.customer_name or "")
        )
        init_phone = (
            editing_job.customer_phone if is_editing_existing else (draft.customer_phone or "")
        )
        init_garment = (
            editing_job.garment_type if is_editing_existing else (draft.garment_type or "Kurti")
        )
        init_color = (
            editing_job.garment_color if is_editing_existing else (draft.garment_color or "")
        )
        init_fabric = (
            editing_job.garment_fabric if is_editing_existing else (draft.garment_fabric or "")
        )
        init_measurements = (
            editing_job.measurements
            if is_editing_existing
            else (draft.measurements if draft else {})
        )
        init_unit = (
            editing_job.measurement_unit.value
            if is_editing_existing
            else (draft.measurement_unit.value if draft else "in")
        )
        init_due_date = (
            editing_job.due_date
            if is_editing_existing
            else (draft.due_date_resolved if draft else None)
        )
        init_due_confirmed = (
            editing_job.due_date_confirmed
            if is_editing_existing
            else (not draft.due_date_needs_confirmation if draft else False)
        )
        init_total = (
            editing_job.total_price_rs
            if is_editing_existing
            else (draft.total_price if draft else None)
        )
        init_advance = (
            editing_job.advance_paid_rs
            if is_editing_existing
            else (draft.advance_paid if draft else 0.0)
        )
        init_fitting = (
            editing_job.fitting_preference
            if is_editing_existing
            else (draft.fitting_preference or "")
        )
        init_notes = editing_job.notes if is_editing_existing else (draft.additional_notes or "")
        init_status = editing_job.status if is_editing_existing else JobStatus.CONFIRMED

        # Editable Approval Form
        with st.form("approval_form"):
            st.subheader("1. Customer & Garment Details")
            r1_1, r1_2, r1_3 = st.columns(3)
            with r1_1:
                cust_name = st.text_input("Customer Name *", value=init_name)
            with r1_2:
                cust_phone = st.text_input("Phone Number", value=init_phone)
            with r1_3:
                # Garment selector
                garment_options = GARMENT_TYPES
                default_g_idx = (
                    garment_options.index(init_garment) if init_garment in garment_options else 0
                )
                garment_type = st.selectbox(
                    "Garment Type *", options=garment_options, index=default_g_idx
                )

            r2_1, r2_2, r2_3 = st.columns(3)
            with r2_1:
                garment_color = st.text_input("Garment Color", value=init_color)
            with r2_2:
                garment_fabric = st.text_input("Fabric Type", value=init_fabric)
            with r2_3:
                unit_choice = st.radio(
                    "Measurement Unit",
                    options=["in", "cm"],
                    index=0 if init_unit == "in" else 1,
                    horizontal=True,
                )

            st.subheader("2. Measurements")
            st.caption("Extracted measurements (editable). Enter numeric values only.")
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)

            # Standard popular measurements
            edited_measurements: dict[str, float] = {}
            col_list = [m_col1, m_col2, m_col3, m_col4]

            # Merge known popular with any custom extracted (prioritize extracted)
            all_meas_keys = list(
                dict.fromkeys(list(init_measurements.keys()) + POPULAR_MEASUREMENTS)
            )

            for idx, key in enumerate(all_meas_keys):
                c = col_list[idx % 4]
                with c:
                    default_val = float(init_measurements.get(key, 0.0))
                    val = st.number_input(
                        f"{key.title()} ({unit_choice})",
                        min_value=0.0,
                        max_value=200.0,
                        value=default_val,
                        step=0.5,
                        key=f"meas_{key}",
                    )
                    if val > 0:
                        edited_measurements[key] = val

            st.subheader("3. Delivery Deadline & Confirmation")
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                # Due date picker
                parsed_due_date = None
                if init_due_date:
                    try:
                        parsed_due_date = date.fromisoformat(init_due_date)
                    except Exception:
                        parsed_due_date = date.today()
                else:
                    parsed_due_date = date.today()

                selected_date = st.date_input("Delivery Due Date", value=parsed_due_date)
            with d_col2:
                st.write("")
                st.write("")
                due_confirmed = st.checkbox(
                    "✅ Confirm Delivery Date with Customer",
                    value=init_due_confirmed,
                    help="Mandatory confirmation required when dates are relative (e.g. 'Sunday').",
                )

            st.subheader("4. Financials (Deterministic Calculation in ₹)")
            p_col1, p_col2, p_col3 = st.columns(3)
            with p_col1:
                total_val = st.number_input(
                    "Total Stitching Price (₹)",
                    min_value=0.0,
                    value=float(init_total) if init_total is not None else 0.0,
                    step=50.0,
                    help="Leave 0 if total stitching price has not been settled.",
                )
            with p_col2:
                advance_val = st.number_input(
                    "Advance Payment Received (₹)",
                    min_value=0.0,
                    value=float(init_advance or 0.0),
                    step=50.0,
                )
            with p_col3:
                # Real-time deterministic balance display
                if total_val > 0:
                    balance_calc = max(0.0, total_val - advance_val)
                    if advance_val > total_val:
                        st.error(
                            f"⚠️ Advance (₹{advance_val:.0f}) exceeds Total (₹{total_val:.0f})!"
                        )
                    st.metric("Balance Due (₹)", f"₹{balance_calc:.2f}")
                else:
                    st.metric("Balance Due (₹)", "Unknown (Total Unset)")

            st.subheader("5. Tailoring Instructions & Workshop Notes")
            n_col1, n_col2 = st.columns(2)
            with n_col1:
                fitting_pref = st.text_input(
                    "Fitting Preference",
                    value=init_fitting,
                    placeholder="e.g. Loose fit / Pichhli baar wali",
                )
            with n_col2:
                job_status = st.selectbox(
                    "Job Status",
                    options=[
                        JobStatus.CONFIRMED.value,
                        JobStatus.IN_PROGRESS.value,
                        JobStatus.READY.value,
                        JobStatus.COMPLETED.value,
                    ],
                    index=0,
                )
            workshop_notes = st.text_area(
                "Workshop & Alteration Notes", value=init_notes, height=70
            )

            act_col1, act_col2, _ = st.columns([2, 2, 3])
            with act_col1:
                save_btn = st.form_submit_button(
                    "💾 Approve & Save Job Card", type="primary", use_container_width=True
                )
            with act_col2:
                discard_btn = st.form_submit_button("🗑️ Discard Draft", use_container_width=True)

        if discard_btn:
            st.session_state.current_draft = None
            st.session_state.editing_job = None
            switch_view("Dashboard")
            st.rerun()

        if save_btn:
            if not cust_name.strip():
                st.error("Customer Name is required to save a job card.")
            else:
                # Prepare PaymentInfo
                clean_total = total_val if total_val > 0 else None
                payment = PaymentInfo.from_rupees(total_rs=clean_total, advance_rs=advance_val)

                due_date_iso = selected_date.isoformat() if selected_date else None

                if is_editing_existing and editing_job:
                    # Update existing job
                    editing_job.customer_name = cust_name.strip()
                    editing_job.customer_phone = cust_phone.strip() or None
                    editing_job.garment_type = garment_type
                    editing_job.garment_color = garment_color.strip() or None
                    editing_job.garment_fabric = garment_fabric.strip() or None
                    editing_job.measurements = edited_measurements
                    editing_job.measurement_unit = MeasurementUnit(unit_choice)
                    editing_job.due_date = due_date_iso
                    editing_job.due_date_confirmed = due_confirmed
                    editing_job.payment = payment
                    editing_job.fitting_preference = fitting_pref.strip() or None
                    editing_job.notes = workshop_notes.strip() or None
                    editing_job.status = JobStatus(job_status)

                    updated = database.update_job(editing_job)
                    st.success(f"Job Card `{updated.job_number}` updated successfully!")
                    st.session_state.print_job_id = updated.id
                    st.session_state.current_draft = None
                    st.session_state.editing_job = None
                    switch_view("Print Work Slip")
                    st.rerun()
                else:
                    # Create new job card
                    job_number = orders.generate_job_number()

                    # Check for duplicate submission
                    duplicate = orders.check_potential_duplicate(
                        customer_name=cust_name.strip(),
                        customer_phone=cust_phone.strip() or None,
                        garment_type=garment_type,
                        raw_request=raw_text,
                    )
                    if duplicate:
                        st.warning(
                            f"⚠️ Potential duplicate detected: Job `{duplicate.job_number}` for {cust_name} ({garment_type}) already exists!"
                        )

                    new_job = JobCard(
                        job_number=job_number,
                        customer_name=cust_name.strip(),
                        customer_phone=cust_phone.strip() or None,
                        garment_type=garment_type,
                        garment_color=garment_color.strip() or None,
                        garment_fabric=garment_fabric.strip() or None,
                        measurements=edited_measurements,
                        measurement_unit=MeasurementUnit(unit_choice),
                        due_date_text=draft.due_date_text if draft else None,
                        due_date=due_date_iso,
                        due_date_confirmed=due_confirmed,
                        payment=payment,
                        fitting_preference=fitting_pref.strip() or None,
                        notes=workshop_notes.strip() or None,
                        raw_request=raw_text,
                        status=JobStatus(job_status),
                    )

                    saved = database.create_job(new_job)
                    st.success(f"Job Card `{saved.job_number}` created successfully!")
                    st.session_state.print_job_id = saved.id
                    st.session_state.current_draft = None
                    st.session_state.editing_job = None
                    switch_view("Print Work Slip")
                    st.rerun()


# ---------------------------------------------------------------------------
# VIEW 4: PRINT WORK SLIP
# ---------------------------------------------------------------------------

elif st.session_state.active_view == "Print Work Slip":
    st.title("Karigar Work Slip & Customer Receipt")
    st.caption(
        "Clean, high-contrast, printer-optimized workshop slip with Hindi/English labels and workshop checklist."
    )

    all_jobs = database.list_jobs(limit=100)
    if not all_jobs:
        st.info("No saved jobs available to print.")
    else:
        # Select job to print
        job_map = {f"{j.job_number} — {j.customer_name} ({j.garment_type})": j.id for j in all_jobs}
        job_labels = list(job_map.keys())

        # Set default index
        target_idx = 0
        if st.session_state.print_job_id:
            for idx, label in enumerate(job_labels):
                if job_map[label] == st.session_state.print_job_id:
                    target_idx = idx
                    break

        selected_label = st.selectbox("Select Job to Print", options=job_labels, index=target_idx)
        selected_job_id = job_map[selected_label]
        target_job = database.get_job_by_id(selected_job_id)

        if target_job:
            btn_col1, btn_col2 = st.columns([2, 5])
            with btn_col1:
                st.caption("Click below to trigger instant browser print dialog.")
            with btn_col2:
                if st.button("⬅️ Return to Dashboard"):
                    switch_view("Dashboard")
                    st.rerun()

            # Render printable HTML in iframe
            html_content = printing.generate_printable_html(target_job)
            components.html(html_content, height=840, scrolling=True)


# ---------------------------------------------------------------------------
# VIEW 5: DATA & PRIVACY
# ---------------------------------------------------------------------------

elif st.session_state.active_view == "Data & Privacy":
    st.title("Data Management, Backups & Privacy Audit")
    st.caption(
        "Inspect local privacy boundaries, export sanitized CSV files, or manage SQLite database backups."
    )

    # Privacy Guarantee Section
    st.markdown(
        """
        <div class="privacy-banner">
            <div>
                <strong>🔒 Verified Offline Local Operation:</strong><br>
                SilaiSathi operates strictly on loopback (<code>127.0.0.1</code>). No telemetry, no remote analytics,
                no cloud fonts, and no third-party API calls are made. Your customer records and measurements
                remain exclusively on this device.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    t1, t2, t3 = st.tabs(["📊 CSV Export", "💾 Database Backups", "🛡️ Privacy & Security Audit"])

    with t1:
        st.subheader("Sanitized CSV Export")
        st.write("Export all tailoring job cards to CSV for local spreadsheet bookkeeping.")
        st.caption(
            "🛡️ Includes automated protection against spreadsheet formula injection (`=`, `+`, `-`, `@`)."
        )

        all_records = database.list_jobs(limit=1000)
        if st.button("Generate CSV Export"):
            csv_data = orders.export_jobs_to_csv(all_records)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="📥 Download Jobs CSV",
                data=csv_data,
                file_name=f"silaisathi_jobs_{timestamp}.csv",
                mime="text/csv",
                type="primary",
            )
            st.success(f"Generated CSV export containing {len(all_records)} jobs.")

    with t2:
        st.subheader("Point-in-Time SQLite Backup")
        st.write(
            "Create a timestamped copy of your SQLite database without interrupting workshop operation."
        )

        b_col1, b_col2 = st.columns(2)
        with b_col1:
            if st.button("💾 Create Backup Now", type="primary"):
                try:
                    backup_file = database.backup_database()
                    st.success(f"Backup created successfully: `{backup_file.name}`")
                except Exception as exc:
                    st.error(f"Backup failed: {str(exc)}")

        with b_col2:
            st.write("Available Backups:")
            if BACKUP_DIR.exists():
                backups = sorted(BACKUP_DIR.glob("*.sqlite3"), reverse=True)
                if backups:
                    for b in backups[:5]:
                        st.caption(f"📁 {b.name} ({b.stat().st_size / 1024:.1f} KB)")
                else:
                    st.caption("No backups created yet.")

        st.divider()
        st.subheader("Restore from Backup")
        st.warning("⚠️ Restoring replaces all current records with the contents of the backup file.")
        uploaded_backup = st.file_uploader("Upload `.sqlite3` backup file", type=["sqlite3", "db"])
        if uploaded_backup and st.button("Confirm Restore", type="secondary"):
            temp_restore_path = BACKUP_DIR / f"temp_restore_{uploaded_backup.name}"
            with open(temp_restore_path, "wb") as f:
                f.write(uploaded_backup.getbuffer())
            try:
                database.restore_database(temp_restore_path)
                st.success("Database restored successfully! Reloading...")
                st.rerun()
            except Exception as exc:
                st.error(f"Restore failed: {str(exc)}")

    with t3:
        st.subheader("Privacy & Security Architecture")
        st.markdown(
            """
            - **Local Model Inference:** Uses Ollama API bound strictly to `127.0.0.1:11434`. No customer data leaves this machine.
            - **Untrusted Input Isolation:** Natural language customer requests are treated as untrusted data and strictly validated against length and prompt-injection patterns.
            - **Deterministic Arithmetic:** The language model NEVER calculates financial balances. All currency math is executed in deterministic Python integer paise.
            - **No Hallucinated Commitments:** Relative dates (such as *"Sunday"* or *"parso"*) are flagged and require human confirmation before saving.
            - **Local Storage Notice:** SQLite database is stored locally in `data/silaisathi.db`. It is not encrypted at rest by default; use FileVault on macOS for full-disk encryption.
            """
        )
