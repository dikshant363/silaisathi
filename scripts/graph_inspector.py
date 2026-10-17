"""SilaiSathi Graph Inspector — Developer Tool & Pre-Mutation Radar.

Integrates with Graphify's AST knowledge graph (graphify-out/graph.json)
to provide dependency exploration, commit freshness verification, transitive
blast-radius analysis, and empirical Graph-vs-Grep comparisons.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

DEFAULT_GRAPH_PATH = Path("graphify-out/graph.json")
DEFAULT_REPORT_PATH = Path("graphify-out/GRAPH_REPORT.md")


def load_graph(graph_path: Path = DEFAULT_GRAPH_PATH) -> dict[str, Any]:
    """Load and validate the Graphify JSON knowledge graph.

    Raises:
        FileNotFoundError: If the graph has not been generated yet.
        ValueError: If the file does not contain a valid graph structure.
    """
    if not graph_path.exists():
        raise FileNotFoundError(
            f"Knowledge graph not found at '{graph_path}'. "
            "Please generate it first using: graphify extract . --code-only"
        )

    try:
        with open(graph_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        raise ValueError(f"Failed to parse graph JSON at '{graph_path}': {exc}") from exc

    if "nodes" not in data or "links" not in data:
        raise ValueError(f"Invalid graph schema in '{graph_path}': missing 'nodes' or 'links'")

    return data


def check_freshness(graph_data: dict[str, Any], repo_root: Path = Path(".")) -> dict[str, Any]:
    """Check whether the knowledge graph is synchronized with the current Git HEAD."""
    built_at = graph_data.get("built_at_commit", "")
    current_head = ""

    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        current_head = proc.stdout.strip()
    except Exception:
        current_head = "UNKNOWN"

    is_fresh = bool(built_at and current_head and built_at.startswith(current_head[:7]))

    message = (
        f"Graph is FRESH (synchronized at commit {built_at[:7]})."
        if is_fresh
        else (
            f"Graph is STALE (built at {built_at[:7] or 'UNKNOWN'}, current HEAD is {current_head[:7] or 'UNKNOWN'}). "
            "Run 'graphify update .' to synchronize."
        )
    )

    return {
        "is_fresh": is_fresh,
        "built_at": built_at,
        "current_head": current_head,
        "message": message,
    }


def get_graph_summary(graph_data: dict[str, Any]) -> dict[str, Any]:
    """Return high-level architectural metrics and god nodes from the graph."""
    nodes = graph_data.get("nodes", [])
    links = graph_data.get("links", [])

    # Node types and degree calculation
    in_degree: dict[str, int] = defaultdict(int)
    out_degree: dict[str, int] = defaultdict(int)
    node_by_id: dict[str, dict[str, Any]] = {}
    communities: set[Any] = set()

    for n in nodes:
        nid = n.get("id", "")
        node_by_id[nid] = n
        if "community" in n:
            communities.add(n["community"])

    for link in links:
        src = link.get("source", "")
        tgt = link.get("target", "")
        out_degree[src] += 1
        in_degree[tgt] += 1

    # Total degree
    total_degree: dict[str, int] = {}
    for nid in node_by_id:
        total_degree[nid] = in_degree[nid] + out_degree[nid]

    top_god_nodes = sorted(total_degree.items(), key=lambda item: item[1], reverse=True)[:10]
    god_nodes_summary = [
        {
            "id": nid,
            "label": node_by_id[nid].get("label", nid),
            "source_file": node_by_id[nid].get("source_file", ""),
            "total_degree": deg,
            "in_degree": in_degree[nid],
            "out_degree": out_degree[nid],
            "community": node_by_id[nid].get("community", 0),
        }
        for nid, deg in top_god_nodes
    ]

    return {
        "total_nodes": len(nodes),
        "total_edges": len(links),
        "total_communities": len(communities),
        "god_nodes": god_nodes_summary,
    }


def find_nodes_by_symbol(graph_data: dict[str, Any], symbol: str) -> list[dict[str, Any]]:
    """Search for nodes matching a given symbol name (exact or substring)."""
    clean_sym = symbol.strip().lower()
    nodes = graph_data.get("nodes", [])

    exact_matches: list[dict[str, Any]] = []
    partial_matches: list[dict[str, Any]] = []

    for n in nodes:
        lbl = str(n.get("label", "")).lower()
        nid = str(n.get("id", "")).lower()
        norm = str(n.get("norm_label", "")).lower()

        if clean_sym in (lbl, norm, lbl.rstrip("()")):
            exact_matches.append(n)
        elif clean_sym in lbl or clean_sym in nid:
            partial_matches.append(n)

    return exact_matches if exact_matches else partial_matches


def inspect_symbol(graph_data: dict[str, Any], symbol: str) -> dict[str, Any]:
    """Inspect a symbol's immediate architectural neighborhood in the graph."""
    matches = find_nodes_by_symbol(graph_data, symbol)
    if not matches:
        return {
            "symbol": symbol,
            "found": False,
            "message": f"No node found in graph matching symbol '{symbol}'",
        }

    target_node = matches[0]
    target_id = target_node.get("id", "")

    nodes_by_id = {n.get("id", ""): n for n in graph_data.get("nodes", [])}
    links = graph_data.get("links", [])

    inward_edges = []
    outward_edges = []

    for edge in links:
        src = edge.get("source", "")
        tgt = edge.get("target", "")

        if tgt == target_id:
            src_node = nodes_by_id.get(src, {})
            inward_edges.append(
                {
                    "source_id": src,
                    "source_label": src_node.get("label", src),
                    "source_file": edge.get("source_file", src_node.get("source_file", "")),
                    "relation": edge.get("relation", "relates_to"),
                    "confidence": edge.get("confidence", "EXTRACTED"),
                }
            )
        elif src == target_id:
            tgt_node = nodes_by_id.get(tgt, {})
            outward_edges.append(
                {
                    "target_id": tgt,
                    "target_label": tgt_node.get("label", tgt),
                    "target_file": tgt_node.get("source_file", ""),
                    "relation": edge.get("relation", "relates_to"),
                    "confidence": edge.get("confidence", "EXTRACTED"),
                }
            )

    return {
        "symbol": symbol,
        "found": True,
        "node": target_node,
        "inward_callers_count": len(inward_edges),
        "inward_callers": inward_edges,
        "outward_dependencies_count": len(outward_edges),
        "outward_dependencies": outward_edges,
        "multiple_candidates": len(matches) > 1,
        "all_candidates": [m.get("id") for m in matches],
    }


def compute_blast_radius(
    graph_data: dict[str, Any], symbol: str, max_depth: int = 3
) -> dict[str, Any]:
    """Compute the transitive blast radius (reverse caller dependency tree) if a symbol is changed.

    Answers: If I modify this symbol, which callers and upstream modules are transitively impacted?
    """
    matches = find_nodes_by_symbol(graph_data, symbol)
    if not matches:
        return {"symbol": symbol, "found": False, "blast_radius_count": 0, "affected_files": []}

    target_node = matches[0]
    target_id = target_node.get("id", "")
    nodes_by_id = {n.get("id", ""): n for n in graph_data.get("nodes", [])}

    # Reverse adjacency map (target -> sources that depend on target)
    incoming_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in graph_data.get("links", []):
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        rel = edge.get("relation", "uses")
        incoming_map[tgt].append((src, rel))

    # BFS traversal backwards along incoming edges
    visited: set[str] = {target_id}
    queue: deque[tuple[str, int]] = deque([(target_id, 0)])

    levels: dict[int, list[dict[str, Any]]] = defaultdict(list)
    affected_files: set[str] = set()

    target_file = target_node.get("source_file")
    if target_file:
        affected_files.add(target_file)

    while queue:
        curr_id, depth = queue.popleft()
        if depth >= max_depth:
            continue

        for parent_id, relation in incoming_map.get(curr_id, []):
            if parent_id not in visited:
                visited.add(parent_id)
                parent_node = nodes_by_id.get(parent_id, {})
                src_file = parent_node.get("source_file", "")
                if src_file:
                    affected_files.add(src_file)

                levels[depth + 1].append(
                    {
                        "id": parent_id,
                        "label": parent_node.get("label", parent_id),
                        "source_file": src_file,
                        "relation": relation,
                        "depth": depth + 1,
                    }
                )
                queue.append((parent_id, depth + 1))

    total_affected = sum(len(items) for items in levels.values())

    return {
        "symbol": symbol,
        "found": True,
        "target_node": {
            "id": target_id,
            "label": target_node.get("label", target_id),
            "source_file": target_node.get("source_file", ""),
            "community": target_node.get("community", 0),
        },
        "blast_radius_count": total_affected,
        "max_depth_explored": max_depth,
        "affected_files": sorted(affected_files),
        "levels": dict(levels),
    }


def compare_with_grep(symbol: str, repo_root: Path = Path(".")) -> dict[str, Any]:
    """Execute an empirical comparison between naive regex grep and Graphify AST structural analysis."""
    graph_data = load_graph(repo_root / DEFAULT_GRAPH_PATH)
    graph_inspection = inspect_symbol(graph_data, symbol)
    blast_radius = compute_blast_radius(graph_data, symbol, max_depth=2)

    # Run grep across Python files
    py_files = sorted(
        list(repo_root.glob("*.py"))
        + list(repo_root.glob("silaisathi/**/*.py"))
        + list(repo_root.glob("tests/**/*.py"))
    )

    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    matching_lines: list[dict[str, Any]] = []
    matching_files: set[str] = set()
    comment_matches = 0

    for py_file in py_files:
        rel_path = str(py_file.relative_to(repo_root))
        try:
            with open(py_file, encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    if pattern.search(line):
                        is_comment = line.strip().startswith("#")
                        if is_comment:
                            comment_matches += 1
                        matching_lines.append(
                            {
                                "file": rel_path,
                                "line_no": line_no,
                                "text": line.strip(),
                                "is_comment": is_comment,
                            }
                        )
                        matching_files.add(rel_path)
        except Exception:
            continue

    return {
        "symbol": symbol,
        "grep_results": {
            "total_matches": len(matching_lines),
            "files_with_matches": len(matching_files),
            "file_list": sorted(matching_files),
            "comment_matches": comment_matches,
            "limitations": [
                "Lacks call-graph direction (cannot distinguish caller from callee)",
                "Includes comments, strings, and docstrings without semantic distinction",
                "Zero transitive reachability (cannot determine what breaks downstream)",
                "No community or architectural boundary awareness",
            ],
        },
        "graphify_results": {
            "found_in_ast": graph_inspection.get("found", False),
            "definition_file": (
                graph_inspection.get("node", {}).get("source_file", "")
                if graph_inspection.get("found")
                else ""
            ),
            "community_id": (
                graph_inspection.get("node", {}).get("community", 0)
                if graph_inspection.get("found")
                else 0
            ),
            "direct_callers_count": graph_inspection.get("inward_callers_count", 0),
            "direct_dependencies_count": graph_inspection.get("outward_dependencies_count", 0),
            "transitive_blast_radius_depth_2": blast_radius.get("blast_radius_count", 0),
            "transitively_affected_files": blast_radius.get("affected_files", []),
            "advantages": [
                "True AST symbol resolution with exact source coordinates",
                "Directed caller-vs-dependency relationships",
                "Calculates transitive impact radius prior to code mutations",
                "Detects architectural hubs and community clusters",
            ],
        },
    }


def format_cli_output(action: str, result: dict[str, Any]) -> str:
    """Format structured results into clean, readable terminal output."""
    lines: list[str] = []

    if action == "freshness":
        status_symbol = "🟢" if result.get("is_fresh") else "🟡"
        lines.append(f"{status_symbol} Graph Freshness Check:")
        lines.append(f"   {result.get('message')}")
        lines.append(f"   Built at: {result.get('built_at') or 'N/A'}")
        lines.append(f"   Git HEAD: {result.get('current_head') or 'N/A'}")

    elif action == "summary":
        lines.append("============================================================")
        lines.append("SILAISATHI ARCHITECTURAL KNOWLEDGE GRAPH SUMMARY")
        lines.append("============================================================")
        lines.append(f"Total Symbols (Nodes):    {result['total_nodes']}")
        lines.append(f"Total Relationships:     {result['total_edges']}")
        lines.append(f"Detected Communities:    {result['total_communities']}")
        lines.append("\nTop Architectural Hubs ('God Nodes'):")
        for idx, g in enumerate(result["god_nodes"], 1):
            lines.append(
                f"  {idx:2d}. {g['label']:<32} "
                f"[Total: {g['total_degree']:2d} | In: {g['in_degree']:2d} | Out: {g['out_degree']:2d}] "
                f"({g['source_file']})"
            )

    elif action == "inspect":
        if not result.get("found"):
            lines.append(f"❌ {result.get('message')}")
        else:
            node = result["node"]
            lines.append("============================================================")
            lines.append(f"SYMBOL INSPECTOR: {node.get('label')}")
            lines.append("============================================================")
            lines.append(f"File:       {node.get('source_file')}:{node.get('source_location')}")
            lines.append(f"Community:  Community {node.get('community')}")
            lines.append(f"Direct Inward Callers:      {result['inward_callers_count']}")
            lines.append(f"Direct Outward Dependencies: {result['outward_dependencies_count']}")

            if result["inward_callers"]:
                lines.append("\nDirect Inward Callers (Who calls/imports this):")
                for c in result["inward_callers"][:12]:
                    lines.append(f"  • {c['source_label']} [{c['relation']}] ({c['source_file']})")

            if result["outward_dependencies"]:
                lines.append("\nDirect Outward Dependencies (What this calls/imports):")
                for d in result["outward_dependencies"][:12]:
                    lines.append(f"  • {d['target_label']} [{d['relation']}] ({d['target_file']})")

    elif action == "blast-radius":
        lines.append("============================================================")
        lines.append(f"PRE-MUTATION BLAST RADIUS: {result['symbol']}")
        lines.append("============================================================")
        if not result.get("found"):
            lines.append(f"❌ Symbol '{result['symbol']}' was not found in knowledge graph.")
        else:
            lines.append(
                f"Total Impacted Nodes (Depth <= {result['max_depth_explored']}): {result['blast_radius_count']}"
            )
            lines.append(f"Transitively Impacted Files ({len(result['affected_files'])}):")
            for f in result["affected_files"]:
                lines.append(f"  • {f}")

            for depth, items in result.get("levels", {}).items():
                lines.append(f"\n[Depth {depth}] Callers ({len(items)}):")
                for it in items[:10]:
                    lines.append(f"   - {it['label']} [{it['relation']}] ({it['source_file']})")
                if len(items) > 10:
                    lines.append(f"   ... and {len(items) - 10} more callers.")

    elif action == "compare":
        grep = result["grep_results"]
        graph = result["graphify_results"]
        lines.append("============================================================")
        lines.append(f"EMPIRICAL COMPARISON: NAIVE GREP VS GRAPHIFY ({result['symbol']})")
        lines.append("============================================================")
        lines.append(f"{'Metric':<35} | {'Naive Grep':<18} | {'Graphify AST Graph':<20}")
        lines.append("-" * 80)
        lines.append(
            f"{'Total Occurrences / Symbols':<35} | {grep['total_matches']:<18} | {'1 resolved AST node':<20}"
        )
        lines.append(
            f"{'Files Touched':<35} | {grep['files_with_matches']:<18} | {len(graph['transitively_affected_files']):<20}"
        )
        lines.append(
            f"{'Comment/Docstring False Matches':<35} | {grep['comment_matches']:<18} | {'0 (filtered in AST)':<20}"
        )
        lines.append(
            f"{'Direct Callers Identified':<35} | {'0 (flat text)':<18} | {graph['direct_callers_count']:<20}"
        )
        lines.append(
            f"{'Transitive Blast Radius':<35} | {'None (blind)':<18} | {graph['transitive_blast_radius_depth_2']:<20}"
        )
        lines.append("-" * 80)
        lines.append("Key Takeaway:")
        lines.append("  Grep floods developers with unstructured string occurrences.")
        lines.append("  Graphify isolates exact callers and upstream blast radius before editing.")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SilaiSathi Graph Inspector — Developer Tool & Pre-Mutation Radar"
    )
    parser.add_argument(
        "action",
        choices=["summary", "inspect", "blast-radius", "compare", "freshness"],
        help="Inspection action to execute",
    )
    parser.add_argument(
        "symbol",
        nargs="?",
        default="",
        help="Target symbol name (required for inspect, blast-radius, compare)",
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=DEFAULT_GRAPH_PATH,
        help=f"Path to graph.json (default: {DEFAULT_GRAPH_PATH})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text",
    )

    args = parser.parse_args()

    try:
        graph_data = load_graph(args.graph)
    except FileNotFoundError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"Error loading graph: {err}", file=sys.stderr)
        sys.exit(1)

    if args.action == "freshness":
        result = check_freshness(graph_data)
    elif args.action == "summary":
        result = get_graph_summary(graph_data)
    elif args.action == "inspect":
        if not args.symbol:
            print("Error: 'inspect' requires a target symbol argument.", file=sys.stderr)
            sys.exit(2)
        result = inspect_symbol(graph_data, args.symbol)
    elif args.action == "blast-radius":
        if not args.symbol:
            print("Error: 'blast-radius' requires a target symbol argument.", file=sys.stderr)
            sys.exit(2)
        result = compute_blast_radius(graph_data, args.symbol)
    elif args.action == "compare":
        if not args.symbol:
            print("Error: 'compare' requires a target symbol argument.", file=sys.stderr)
            sys.exit(2)
        result = compare_with_grep(args.symbol)
    else:
        result = {}

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(format_cli_output(args.action, result))


if __name__ == "__main__":
    main()
