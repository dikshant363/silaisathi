"""Tests for SilaiSathi Graph Inspector developer tool and Graphify integration."""

from pathlib import Path

import pytest

from scripts.graph_inspector import (
    DEFAULT_GRAPH_PATH,
    check_freshness,
    compare_with_grep,
    compute_blast_radius,
    find_nodes_by_symbol,
    format_cli_output,
    get_graph_summary,
    inspect_symbol,
    load_graph,
)


def test_load_graph_valid():
    """Verify loading the existing graphify knowledge graph succeeds and contains valid keys."""
    data = load_graph(DEFAULT_GRAPH_PATH)
    assert isinstance(data, dict)
    assert "nodes" in data
    assert "links" in data
    assert len(data["nodes"]) >= 200
    assert len(data["links"]) >= 500


def test_load_graph_missing(tmp_path: Path):
    """Verify loading a nonexistent graph file raises FileNotFoundError with helpful advice."""
    missing = tmp_path / "nonexistent.json"
    with pytest.raises(FileNotFoundError) as exc_info:
        load_graph(missing)
    assert "graphify extract . --code-only" in str(exc_info.value)


def test_check_freshness():
    """Verify graph freshness check against current git repository."""
    data = load_graph(DEFAULT_GRAPH_PATH)
    freshness = check_freshness(data)
    assert isinstance(freshness["is_fresh"], bool)
    assert "message" in freshness
    assert len(freshness["built_at"]) > 0


def test_get_graph_summary():
    """Verify architectural summary contains node/edge counts and god nodes."""
    data = load_graph(DEFAULT_GRAPH_PATH)
    summary = get_graph_summary(data)
    assert summary["total_nodes"] >= 200
    assert summary["total_edges"] >= 500
    assert summary["total_communities"] >= 5
    assert len(summary["god_nodes"]) == 10

    # PaymentInfo and JobCard should be recognized as top domain hubs
    god_labels = [g["label"] for g in summary["god_nodes"]]
    assert "PaymentInfo" in god_labels
    assert "JobCard" in god_labels


def test_find_nodes_by_symbol():
    """Verify symbol lookup by exact or normalized name."""
    data = load_graph(DEFAULT_GRAPH_PATH)
    matches = find_nodes_by_symbol(data, "PaymentInfo")
    assert len(matches) >= 1
    assert matches[0]["label"] == "PaymentInfo"

    job_matches = find_nodes_by_symbol(data, "JobCard")
    assert len(job_matches) >= 1
    assert job_matches[0]["label"] == "JobCard"


def test_inspect_symbol_known():
    """Verify inspection of a core domain model shows callers and outward dependencies."""
    data = load_graph(DEFAULT_GRAPH_PATH)
    result = inspect_symbol(data, "PaymentInfo")
    assert result["found"] is True
    assert result["node"]["label"] == "PaymentInfo"
    assert result["node"]["source_file"] == "silaisathi/schemas.py"
    assert result["inward_callers_count"] > 10
    assert result["outward_dependencies_count"] >= 5


def test_inspect_symbol_unknown():
    """Verify graceful handling for non-existent symbol."""
    data = load_graph(DEFAULT_GRAPH_PATH)
    result = inspect_symbol(data, "NonExistentSymbolXYZ")
    assert result["found"] is False
    assert "No node found" in result["message"]


def test_compute_blast_radius():
    """Verify blast radius calculation computes transitive upstream callers across levels."""
    data = load_graph(DEFAULT_GRAPH_PATH)
    blast = compute_blast_radius(data, "PaymentInfo", max_depth=3)
    assert blast["found"] is True
    assert blast["blast_radius_count"] > 20
    assert len(blast["affected_files"]) >= 5
    assert 1 in blast["levels"]
    assert 2 in blast["levels"]
    assert "app.py" in blast["affected_files"]
    assert "silaisathi/database.py" in blast["affected_files"]


def test_compare_with_grep():
    """Verify empirical comparison between flat regex text search and Graphify AST structural analysis."""
    result = compare_with_grep("PaymentInfo")
    grep = result["grep_results"]
    graph = result["graphify_results"]

    assert grep["total_matches"] > 0
    assert grep["files_with_matches"] > 0
    assert graph["found_in_ast"] is True
    assert graph["direct_callers_count"] > 10
    assert graph["transitive_blast_radius_depth_2"] > 20
    assert len(grep["limitations"]) == 4
    assert len(graph["advantages"]) == 4


def test_format_cli_output():
    """Verify formatting helper formats terminal output cleanly for all actions."""
    data = load_graph(DEFAULT_GRAPH_PATH)

    summary_text = format_cli_output("summary", get_graph_summary(data))
    assert "ARCHITECTURAL KNOWLEDGE GRAPH SUMMARY" in summary_text
    assert "PaymentInfo" in summary_text

    inspect_text = format_cli_output("inspect", inspect_symbol(data, "PaymentInfo"))
    assert "SYMBOL INSPECTOR: PaymentInfo" in inspect_text

    blast_text = format_cli_output("blast-radius", compute_blast_radius(data, "PaymentInfo"))
    assert "PRE-MUTATION BLAST RADIUS: PaymentInfo" in blast_text

    comp_text = format_cli_output("compare", compare_with_grep("PaymentInfo"))
    assert "EMPIRICAL COMPARISON: NAIVE GREP VS GRAPHIFY" in comp_text

    fresh_text = format_cli_output("freshness", check_freshness(data))
    assert "Graph Freshness Check" in fresh_text
