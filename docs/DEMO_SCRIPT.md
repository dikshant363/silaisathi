# SilaiSathi: 2-Minute Demonstration Script

This script provides a reproducible, step-by-step walkthrough of **SilaiSathi** (सिलाईसाथी) for live presentations, video recordings, and evaluation demos.

---

## Prerequisites

1. **Local Model Engine Running:**
   ```bash
   ollama serve
   # In another terminal or background:
   ollama list | grep qwen3.5:4b
   ```
2. **Start SilaiSathi Workstation:**
   ```bash
   source .venv/bin/activate
   streamlit run app.py --server.address=127.0.0.1 --server.port=8501
   ```
3. **Browser:** Open `http://127.0.0.1:8501`.

---

## Walkthrough Timeline (Total: ~2 Minutes)

### [0:00 - 0:25] 1. The Tailoring Problem
- **Voiceover / Presenter:**
  > *"Every day across India, millions of neighborhood tailors ('darzi masterjis') and boutique owners receive tailoring requests via WhatsApp, loose paper chits, and voice notes in messy Hindi and Hinglish.*
  > *Three critical failures cost tailors real money: missed deadlines from ambiguous dates like 'Sunday tak chahiye', missing measurements noticed only at the cutting table, and cash advance disputes.*
  > *Cloud SaaS apps fail here because shops often have spotty internet, recurring subscriptions are expensive, and merchants refuse to send customer phone numbers and body measurements to cloud servers.*
  > *This is SilaiSathi: a 100% offline, local-first AI workstation powered by open-weight models."*
- **Action on Screen:**
  - Show the **SilaiSathi Dashboard** with operational metrics: *Total Jobs, Awaiting Work, Due Soon, Completed*.
  - Point to the sidebar indicator: `🟢 Ollama Active (127.0.0.1:11434) — Local loopback inference ready`.

---

### [0:25 - 0:50] 2. Natural-Language Request & Local AI Extraction
- **Action on Screen:**
  - Click **"New Job (AI Assistant)"** in the sidebar.
  - In the Customer Details section, enter:
    - **Customer Name:** `Meena Kumari`
    - **Phone:** `9876543210`
  - In the **Customer Voice / Text Request** box, paste this authentic Hinglish request:
    ```text
    Bhaiya, blue kurti Sunday tak chahiye. Length 44, chest 38, sleeves 18. Pichhli baar wali fitting rakhna. 300 advance de diya.
    ```
  - Click the primary button: **"✨ Extract with Local AI"**.
- **Voiceover / Presenter:**
  > *"We paste a typical conversational note. Notice the mixture of Hindi and English, conversational instructions like 'pichhli baar wali fitting', and a relative deadline 'Sunday tak'.*
  > *When we click Extract, SilaiSathi invokes our local Qwen 3.5 4B model running on Apple Silicon via Ollama over 127.0.0.1 loopback. In less than two seconds, without sending a single byte to the internet, we get a structured draft."*

---

### [0:50 - 1:20] 3. Safe Verification: Ambiguity & Truthful Unknowns
- **Action on Screen:**
  - Show the **Review & Approval Screen**.
  - Highlight the **Audit & Safety Badges**:
    1. **Ambiguous Due Date Warning:** Point out the yellow badge:
       `Candidate relative day 'Sunday' points to [Next Sunday Date]. Requires confirmation.`
       Check the **"Confirm Due Date"** checkbox.
    2. **Truthful Financial Unknown:** Point out that **Total Price** is empty (`None`), and the balance is marked:
       `Total price not stated — Balance pending price confirmation`.
       Explain that the model is *prohibited* from hallucinating prices.
    3. Enter the total stitching price: `850`.
       Observe the balance immediately and deterministically recalculates to `₹550.00` (`850 - 300 = 550`) using integer paise arithmetic.
    4. Review extracted measurements: `Length: 44.0 in`, `Chest: 38.0 in`, `Sleeves: 18.0 in`.
- **Voiceover / Presenter:**
  > *"Notice our deterministic safety boundaries at work. SilaiSathi didn't invent a price or silently assume Sunday without asking. It flagged the date for tailor confirmation and left the total price as an honest unknown.*
  > *Once we enter 850 as the agreed stitching rate, deterministic Python integer arithmetic calculates the remaining 550 rupee balance—never the probabilistic language model."*

---

### [1:20 - 1:40] 4. Save to Local SQLite & Instant Search
- **Action on Screen:**
  - Click **"💾 Approve & Save Job Card"**.
  - A green notification banner appears: `Job SS-2610-0001 saved successfully!`.
  - Click **"Go to Dashboard"** or select **Dashboard** in navigation.
  - Show the job listed in the active jobs table.
  - In the **Search jobs** field, type `Meena` or `98765`.
  - The table filters instantly.
  - Click the **"In Progress"** button to advance the job lifecycle state.
- **Voiceover / Presenter:**
  > *"The job is committed to local SQLite in WAL mode with instant search across customer names, phone numbers, and garment types. We can track its lifecycle from Confirmed to In Progress to Ready."*

---

### [1:40 - 2:00] 5. Dual-Language Karigar Work Slip & Offline Proof
- **Action on Screen:**
  - Click **"Print Work Slip"** on Meena's job card.
  - Display the generated **Karigar Workshop Slip**:
    - Dual-language labels: `Length / लंबाई`, `Chest / सीना`, `Sleeves / आस्तीन`.
    - Workshop Quality Checklist: `कटाई (Cutting)`, `सिलाई (Stitching)`, `ओवरलॉक (Overlock)`, `प्रेस / फिनिशिंग (Ironing)`.
    - Detachable bottom customer receipt with job number, shop phone, and advance/balance breakdown.
  - Point out the **"🖨️ Print Slip (window.print)"** button.
  - Briefly show the automated verification terminal output:
    `tests/verify_offline_network.py: ZERO external network connections attempted during entire workflow.`
- **Voiceover / Presenter:**
  > *"Finally, SilaiSathi generates a dual-language Karigar slip designed for the realities of Indian workshops. The tailor gets a clear cutting checklist in Hindi and English, and the customer receives a tear-off advance receipt.*
  > *Every single operation—AI extraction, schema validation, persistence, search, and printing—runs entirely offline on local hardware with zero cloud dependencies. That is SilaiSathi."*

---

## Fallback Scenario: Demonstrating Without Ollama Running

If presenting in an environment where Ollama cannot be started:
1. The sidebar will honestly display: `🟡 Ollama Offline — Heuristic sample mode enabled`.
2. Under **New Job (AI Assistant)**, select any pre-loaded request from the dropdown.
3. Click **"✨ Extract with Local AI"**.
4. The system transparently falls back to the deterministic heuristic parser and displays:
   `[PREVIEW ONLY: Generated via offline heuristic draft rules because Ollama was offline. Not a live model result.]`
5. This demonstrates truthfulness in UI states without pretending a dead service is alive.
