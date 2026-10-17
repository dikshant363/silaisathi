# Graph Report - silaisathi  (2026-10-17)

## Corpus Check
- 25 files · ~76,092 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 4, .toml 1)

## Summary
- 402 nodes · 833 edges · 30 communities (20 shown, 10 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 76 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `39be96ab`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- JobStatus
- database.py
- test_silaisathi.py
- PaymentInfo
- extraction.py
- app.py
- silaisathi
- test_graph_inspector.py
- SilaiSathi (सिलाईसाथी)
- DEVTO_SUBMISSION.md
- resolve_due_date
- Walkthrough Timeline (Total: ~2 Minutes)
- Third-Party Notices and Open Source Attribution
- .from_rupees
- JobStatus
- SilaiSathi — DigitalOcean App Platform Deployment Guide
- SilaiSathi × Graphify — Hacktoberfest Release & Implementation Audit Report
- SilaiSathi × Graphify: Pre-Mutation Architectural Radar & Knowledge Graph
- run_offline_test
- JobCard
- temp_db
- test_payment_info_full_values
- clean_model_output
- test_build_draft_realistic_hinglish_sample
- test_request_text_length_limit
- test_config_popular_measurements_defined
- test_payment_info_from_rupees_keyword_aliases
- test_app_startup_import
- test_create_new_job_button_navigation
- test_payment_info_excess_advance

## God Nodes (most connected - your core abstractions)
1. `PaymentInfo` - 38 edges
2. `JobCard` - 35 edges
3. `JobStatus` - 21 edges
4. `load_graph()` - 18 edges
5. `get_connection()` - 18 edges
6. `MeasurementUnit` - 18 edges
7. `ExtractedDraft` - 16 edges
8. `build_draft_from_parsed()` - 15 edges
9. `create_job()` - 14 edges
10. `extract_with_llm()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `App Specification (`.do/app.yaml`)` --references--> `main()`  [INFERRED]
  DEPLOYMENT_DIGITALOCEAN.md → scripts/graph_inspector.py
- `Method 1: Automated Deploy via DigitalOcean Web Console` --references--> `main()`  [INFERRED]
  DEPLOYMENT_DIGITALOCEAN.md → scripts/graph_inspector.py
- `3. MLH Prize Category Eligibility Matrix` --references--> `GemmaProvider`  [INFERRED]
  HACKTOBERFEST_VERIFICATION_REPORT.md → silaisathi/extraction.py
- `Benchmark 1: Core Domain Abstraction (`PaymentInfo`)` --references--> `PaymentInfo`  [INFERRED]
  HACKTOBERFEST_SUBMISSION_GUIDE.md → silaisathi/schemas.py
- `Why Graphify in SilaiSathi?` --references--> `PaymentInfo`  [INFERRED]
  README.md → silaisathi/schemas.py

## Import Cycles
- None detected.

## Communities (30 total, 10 thin omitted)

### Community 0 - "JobStatus"
Cohesion: 0.22
Nodes (7): get_job_by_id(), _row_to_job(), update_job_status(), JobStatus, MeasurementUnit, test_job_persistence_crud(), run_checks()

### Community 1 - "database.py"
Cohesion: 0.12
Nodes (12): ensure_data_directories(), backup_database(), count_jobs(), delete_job(), get_connection(), get_dashboard_stats(), get_job_by_number(), init_db() (+4 more)

### Community 2 - "test_silaisathi.py"
Cohesion: 0.20
Nodes (4): test_csv_formula_injection_sanitization(), test_offline_sample_generator(), test_payment_info_unknown_total(), test_payment_negative_amounts_rejected()

### Community 3 - "PaymentInfo"
Cohesion: 0.16
Nodes (3): Why Open-Source AI & Local Knowledge Graphs Matter, 3. In-App Interactive Architecture Radar, PaymentInfo

### Community 4 - "extraction.py"
Cohesion: 0.06
Nodes (28): 1. Executive Summary, BaseExtractionProvider, build_draft_from_parsed(), check_gemma_health(), check_ollama_health(), extract_with_llm(), GemmaProvider, generate_sample_draft() (+20 more)

### Community 5 - "app.py"
Cohesion: 0.09
Nodes (3): export_jobs_to_csv(), calculate_payment_info(), sanitize_for_csv()

### Community 7 - "test_graph_inspector.py"
Cohesion: 0.09
Nodes (19): check_freshness(), compare_with_grep(), compute_blast_radius(), find_nodes_by_symbol(), format_cli_output(), get_graph_summary(), inspect_symbol(), load_graph() (+11 more)

### Community 8 - "SilaiSathi (सिलाईसाथी)"
Cohesion: 0.06
Nodes (31): 10. Project Structure, 11. License, 1. Developer CLI: `scripts/graph_inspector.py`, 1. Problem Statement, 1. Workshop Job Desk (Dashboard), 2. Core Architecture & Local-First Principles, 2. Empirical Benchmark: Naive Grep vs. Graphify AST, 2. Natural-Language AI Assistant (+23 more)

### Community 9 - "DEVTO_SUBMISSION.md"
Cohesion: 0.12
Nodes (16): 2-Minute Walkthrough Summary:, Code, Core Capabilities, Demo, Deterministic Financial Arithmetic (Paise-Based), Enter SilaiSathi (सिलाईसाथी), How I Built It, Key Architectural Excerpt: ChatML Prefill Bypasses Reasoning Delays (+8 more)

### Community 10 - "resolve_due_date"
Cohesion: 0.22
Nodes (4): resolve_due_date(), test_resolve_empty_due_date(), test_resolve_kal_and_parso(), test_resolve_relative_weekday_requires_confirmation()

### Community 11 - "Walkthrough Timeline (Total: ~2 Minutes)"
Cohesion: 0.20
Nodes (9): [0:00 - 0:25] 1. The Tailoring Problem, [0:25 - 0:50] 2. Natural-Language Request & Local AI Extraction, [0:50 - 1:20] 3. Safe Verification: Ambiguity & Truthful Unknowns, [1:20 - 1:40] 4. Save to Local SQLite & Instant Search, [1:40 - 2:00] 5. Dual-Language Karigar Work Slip & Offline Proof, Fallback Scenario: Demonstrating Without Ollama Running, Prerequisites, SilaiSathi: 2-Minute Demonstration Script (+1 more)

### Community 12 - "Third-Party Notices and Open Source Attribution"
Cohesion: 0.20
Nodes (9): 1. Streamlit, 2. Pydantic, 3. HTTPX, 4. Pytest, 5. Ruff, 6. Ollama, 7. Qwen Model Family (Alibaba Cloud), 8. Graphify (Graphify-Labs) (+1 more)

### Community 13 - ".from_rupees"
Cohesion: 0.20
Nodes (6): create_job(), test_csv_export_content_and_safety(), test_database_backup_and_restore(), test_duplicate_detection_permutations(), test_job_deletion_and_update_timestamps(), test_job_search_and_filter()

### Community 14 - "JobStatus"
Cohesion: 0.33
Nodes (3): is_valid_status_transition(), test_forbidden_status_transitions(), test_order_lifecycle_transitions()

### Community 15 - "SilaiSathi — DigitalOcean App Platform Deployment Guide"
Cohesion: 0.17
Nodes (11): 1. Architecture & Deployment Overview, 2. Authorization & Cost Checkpoint, 3. DigitalOcean App Platform Specifications, 4. Environment Variables & Runtime Secrets, 5. Deployment Methods, 6. Container & Persistence Limitations, 7. Post-Deployment Verification & Smoke Tests, App Specification (`.do/app.yaml`) (+3 more)

### Community 16 - "SilaiSathi × Graphify — Hacktoberfest Release & Implementation Audit Report"
Cohesion: 0.18
Nodes (10): 1. Automated Unit Tests (`pytest -v`), 2. Architecture & Data Flow, 2. Strict Offline Network Isolation (`tests/verify_offline_network.py`), 3. Live Runtime Inference (`tests/verify_runtime.py`), 3. MLH Prize Category Eligibility Matrix, 4. Code Quality & Formatting, 4. Verification Evidence & Test Execution, 5. Working Tree & File Audit (+2 more)

### Community 17 - "SilaiSathi × Graphify: Pre-Mutation Architectural Radar & Knowledge Graph"
Cohesion: 0.20
Nodes (9): 1. Project Pitch, 2. Architecture: Where Graphify Fits, 3. Measurable Value: Empirical Benchmark (Graphify vs. Naive Grep), 4. Live Demonstration Script (Step-by-Step), 5. Verification & Test Suite Summary, Benchmark 1: Core Domain Abstraction (`PaymentInfo`), Benchmark 2: Tracing the Real-World `POPULAR_MEASUREMENTS` Crash, In-App Workstation Demo (+1 more)

### Community 18 - "run_offline_test"
Cohesion: 0.29
Nodes (4): list_jobs(), check_potential_duplicate(), generate_job_number(), run_offline_test()

### Community 19 - "JobCard"
Cohesion: 0.18
Nodes (3): generate_printable_html(), JobCard, test_printable_html_truthful_labeling()

### Community 22 - "clean_model_output"
Cohesion: 0.33
Nodes (3): clean_model_output(), test_clean_model_output_with_markdown_fence(), test_clean_model_output_with_thinking_tags()

## Knowledge Gaps
- **1 isolated node(s):** `silaisathi`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 213 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PaymentInfo` connect `PaymentInfo` to `JobStatus`, `database.py`, `test_silaisathi.py`, `extraction.py`, `app.py`, `SilaiSathi (सिलाईसाथी)`, `.from_rupees`, `SilaiSathi × Graphify: Pre-Mutation Architectural Radar & Knowledge Graph`, `run_offline_test`, `JobCard`, `test_payment_info_full_values`, `test_payment_info_from_rupees_keyword_aliases`, `test_payment_info_excess_advance`?**
  _High betweenness centrality (0.165) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `PaymentInfo` (e.g. with `Benchmark 1: Core Domain Abstraction (`PaymentInfo`)` and `Why Open-Source AI & Local Knowledge Graphs Matter`) actually correct?**
  _`PaymentInfo` has 20 INFERRED edges - model-reasoned connections that need verification._
- **What connects `silaisathi` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `database.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11827956989247312 - nodes in this community are weakly interconnected._
- **Why does `8. Graphify Architectural Knowledge Graph & Agent Radar` connect `SilaiSathi (सिलाईसाथी)` to `PaymentInfo`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `JobCard` (e.g. with `Why Open-Source AI & Local Knowledge Graphs Matter` and `3. In-App Interactive Architecture Radar`) actually correct?**
  _`JobCard` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `extraction.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05706760316066725 - nodes in this community are weakly interconnected._