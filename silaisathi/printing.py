"""Print layout and receipt generation for SilaiSathi.

Produces an Apple-inspired, high-contrast, clean physical tailoring slip (Karigar Slip).
Fully compatible with standard receipt printers and regular A4 / A5 paper.
Includes Hindi and English labels, workshop checklists, and truthful labeling of unknown fields.
"""

from __future__ import annotations

import html

from silaisathi.config import (
    COMMON_MEASUREMENTS,
    DEFAULT_SHOP_NAME,
    DEFAULT_SHOP_PHONE,
    DEFAULT_SHOP_TAGLINE,
)
from silaisathi.schemas import JobCard


def generate_printable_html(
    job: JobCard, shop_name: str = DEFAULT_SHOP_NAME, shop_phone: str = DEFAULT_SHOP_PHONE
) -> str:
    """Generate standalone, printer-optimized HTML tailoring work slip."""
    # Format measurements with dual English/Hindi labels where available
    meas_labels = dict(COMMON_MEASUREMENTS)
    meas_rows_html = []

    for key, val in job.measurements.items():
        clean_key = key.lower().strip()
        display_label = meas_labels.get(clean_key, clean_key.title())
        meas_rows_html.append(
            f"""
            <tr>
                <td class="meas-name">{html.escape(display_label)}</td>
                <td class="meas-val"><strong>{val}</strong> <span class="unit">{job.measurement_unit.value}</span></td>
            </tr>
            """
        )

    if not meas_rows_html:
        meas_rows_html.append(
            """
            <tr>
                <td colspan="2" class="empty-state">No measurements recorded. Please record on fitting.</td>
            </tr>
            """
        )

    # Format financials
    if job.total_price_rs is not None:
        total_display = f"₹{job.total_price_rs:.2f}"
    else:
        total_display = "<span class='badge-unknown'>Unset / Pending</span>"

    advance_display = f"₹{job.advance_paid_rs:.2f}"

    if job.balance_due_rs is not None:
        if job.balance_due_rs <= 0:
            balance_display = "<span class='badge-paid'>₹0.00 (Fully Paid)</span>"
        else:
            balance_display = f"<strong>₹{job.balance_due_rs:.2f}</strong>"
    else:
        balance_display = "<span class='badge-unknown'>Pending Price Confirmation</span>"

    due_date_display = (
        job.due_date or job.due_date_text or "<span class='badge-unknown'>Not Specified</span>"
    )
    if not job.due_date_confirmed and job.due_date_text:
        due_date_display += " <small style='color:#c05621;'>(Needs Confirmation)</small>"

    customer_phone_display = job.customer_phone or "<span class='badge-unknown'>Not Provided</span>"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Job Slip #{job.job_number} - {html.escape(job.customer_name)}</title>
<style>
    @page {{
        size: A5 portrait;
        margin: 12mm;
    }}
    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1a202c;
    }}
    body {{
        background: #f7fafc;
        padding: 20px;
        display: flex;
        justify-content: center;
    }}
    .slip-container {{
        background: #ffffff;
        width: 100%;
        max-width: 580px;
        padding: 24px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }}
    .shop-header {{
        text-align: center;
        border-bottom: 2px solid #2d3748;
        padding-bottom: 12px;
        margin-bottom: 16px;
    }}
    .shop-title {{
        font-size: 20px;
        font-weight: 800;
        letter-spacing: -0.5px;
        text-transform: uppercase;
    }}
    .shop-sub {{
        font-size: 11px;
        color: #718096;
        margin-top: 2px;
    }}
    .job-meta-bar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #edf2f7;
        padding: 8px 12px;
        border-radius: 6px;
        margin-bottom: 16px;
    }}
    .job-number {{
        font-size: 18px;
        font-weight: 800;
        letter-spacing: 0.5px;
        color: #2b6cb0;
    }}
    .job-status {{
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        padding: 3px 8px;
        border-radius: 4px;
        background: #e2e8f0;
        color: #4a5568;
    }}
    .info-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        margin-bottom: 16px;
    }}
    .info-block {{
        background: #f7fafc;
        border: 1px solid #edf2f7;
        border-radius: 6px;
        padding: 8px 12px;
    }}
    .info-label {{
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        color: #718096;
        margin-bottom: 2px;
    }}
    .info-val {{
        font-size: 13px;
        font-weight: 600;
    }}
    .section-title {{
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 14px;
        margin-bottom: 6px;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 4px;
        display: flex;
        justify-content: space-between;
    }}
    .meas-table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 14px;
        font-size: 12px;
    }}
    .meas-table tr {{
        border-bottom: 1px dashed #e2e8f0;
    }}
    .meas-table td {{
        padding: 5px 4px;
    }}
    .meas-name {{
        color: #4a5568;
    }}
    .meas-val {{
        text-align: right;
    }}
    .unit {{
        font-size: 10px;
        color: #718096;
    }}
    .notes-box {{
        background: #fffaf0;
        border-left: 3px solid #dd6b20;
        padding: 8px 12px;
        font-size: 12px;
        margin-bottom: 14px;
        border-radius: 0 4px 4px 0;
    }}
    .financials-table {{
        width: 100%;
        margin-bottom: 16px;
        font-size: 12px;
        border-collapse: collapse;
    }}
    .financials-table td {{
        padding: 4px 8px;
    }}
    .financials-table tr.total-row {{
        background: #edf2f7;
        font-weight: 700;
    }}
    .checklist {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
        font-size: 11px;
        margin-bottom: 16px;
        background: #f7fafc;
        padding: 10px;
        border-radius: 6px;
        border: 1px solid #edf2f7;
    }}
    .check-item {{
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .box {{
        width: 14px;
        height: 14px;
        border: 1.5px solid #4a5568;
        display: inline-block;
        border-radius: 2px;
    }}
    .slip-footer {{
        margin-top: 18px;
        padding-top: 10px;
        border-top: 1px solid #e2e8f0;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        font-size: 10px;
        color: #718096;
    }}
    .sig-line {{
        border-top: 1px solid #718096;
        width: 120px;
        text-align: center;
        padding-top: 4px;
    }}
    .badge-unknown {{
        color: #718096;
        font-style: italic;
    }}
    .badge-paid {{
        color: #38a169;
        font-weight: 700;
    }}
    .print-button-container {{
        text-align: center;
        margin-bottom: 16px;
    }}
    .btn-print {{
        background: #2b6cb0;
        color: #ffffff;
        border: none;
        padding: 8px 18px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
    }}
    @media print {{
        body {{
            background: #ffffff;
            padding: 0;
        }}
        .slip-container {{
            border: none;
            box-shadow: none;
            padding: 0;
            max-width: 100%;
        }}
        .print-button-container {{
            display: none !important;
        }}
    }}
</style>
</head>
<body>
<div class="slip-container">
    <div class="print-button-container">
        <button class="btn-print" onclick="window.print()">🖨️ Print Work Slip (प्रिंट निकालें)</button>
    </div>

    <div class="shop-header">
        <div class="shop-title">{html.escape(shop_name)}</div>
        <div class="shop-sub">{html.escape(DEFAULT_SHOP_TAGLINE)} &bull; {html.escape(shop_phone)}</div>
    </div>

    <div class="job-meta-bar">
        <div>
            <span style="font-size:10px; color:#718096; text-transform:uppercase; font-weight:700;">Job Card #</span><br>
            <span class="job-number">{html.escape(job.job_number)}</span>
        </div>
        <div style="text-align:right;">
            <span class="job-status">{html.escape(job.status.value.replace("_", " "))}</span>
        </div>
    </div>

    <div class="info-grid">
        <div class="info-block">
            <div class="info-label">Customer / ग्राहक</div>
            <div class="info-val">{html.escape(job.customer_name)}</div>
        </div>
        <div class="info-block">
            <div class="info-label">Phone / फोन</div>
            <div class="info-val">{customer_phone_display}</div>
        </div>
        <div class="info-block">
            <div class="info-label">Garment / पोशाक</div>
            <div class="info-val">{html.escape(job.garment_type)} {f"({html.escape(job.garment_color)})" if job.garment_color else ""}</div>
        </div>
        <div class="info-block">
            <div class="info-label">Due Date / डिलीवरी तारीख</div>
            <div class="info-val">{due_date_display}</div>
        </div>
    </div>

    <div class="section-title">
        <span>नाप / Measurements</span>
        <span style="font-size:10px; font-weight:600; text-transform:none; color:#718096;">Unit: {job.measurement_unit.value}</span>
    </div>
    <table class="meas-table">
        <tbody>
            {"".join(meas_rows_html)}
        </tbody>
    </table>

    {f'<div class="notes-box"><strong>Fitting / फिटिंग:</strong> {html.escape(job.fitting_preference)}</div>' if job.fitting_preference else ""}
    {f'<div class="notes-box" style="border-left-color:#3182ce; background:#ebf8ff;"><strong>Special Notes / निर्देश:</strong> {html.escape(job.notes)}</div>' if job.notes else ""}

    <div class="section-title">
        <span>Payment Details / भुगतान विवरण</span>
    </div>
    <table class="financials-table">
        <tr>
            <td>Total Stitching Amount (कुल रकम):</td>
            <td style="text-align:right;">{total_display}</td>
        </tr>
        <tr>
            <td>Advance Received (जमा अग्रिम):</td>
            <td style="text-align:right;">{advance_display}</td>
        </tr>
        <tr class="total-row">
            <td>Balance Due on Delivery (बाकी रकम):</td>
            <td style="text-align:right;">{balance_display}</td>
        </tr>
    </table>

    <div class="section-title">
        <span>Karigar Workflow Checklist / कारीगर चेकलिस्ट</span>
    </div>
    <div class="checklist">
        <div class="check-item"><span class="box"></span> 1. कटाई (Cutting)</div>
        <div class="check-item"><span class="box"></span> 2. सिलाई (Stitching)</div>
        <div class="check-item"><span class="box"></span> 3. नाप चेक (Fitting Check)</div>
        <div class="check-item"><span class="box"></span> 4. काज / हुक (Button / Hook)</div>
        <div class="check-item"><span class="box"></span> 5. प्रेस / फिनिशिंग (Ironing)</div>
        <div class="check-item"><span class="box"></span> 6. डिलीवरी तैयार (Ready)</div>
    </div>

    <div class="slip-footer">
        <div>
            Generated via SilaiSathi &bull; Local & Private<br>
            Date: {job.created_at[:10]}
        </div>
        <div class="sig-line">
            Masterji Signature
        </div>
    </div>
</div>
</body>
</html>
"""
    return html_content
