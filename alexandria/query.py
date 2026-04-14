"""
Alexandria Query Layer — Vela's second +1.

Upgrades the naive keyword search with:
  1. Stemming-aware matching (equipment/equip, publish/publishing)
  2. Synonym expansion (auth → login, OAuth, session, JWT)
  3. Type-weighted scoring (decisions > lessons > endpoints > files)
  4. Path-aware traversal (follow imports/defines edges from seed nodes)
  5. Formatted output for Claude sessions (compact, token-efficient)

Usage:
    from alexandria.query import ask
    results = ask("what handles equipment publishing")
    print(format_results(results))
"""

import re
from typing import List, Dict, Optional
from alexandria.graph import AlexandriaGraph


# ── Stemming (poor man's — no nltk needed) ──

STEM_MAP = {
    "publishing": "publish",
    "published": "publish",
    "publishes": "publish",
    "importing": "import",
    "imported": "import",
    "imports": "import",
    "building": "build",
    "builder": "build",
    "builds": "build",
    "built": "build",
    "creating": "create",
    "created": "create",
    "creates": "create",
    "crashed": "crash",
    "crashes": "crash",
    "crashing": "crash",
    "handling": "handle",
    "handled": "handle",
    "handles": "handle",
    "handler": "handle",
    "syncing": "sync",
    "synced": "sync",
    "indexed": "index",
    "indexing": "index",
    "indexes": "index",
    "querying": "query",
    "queried": "query",
    "queries": "query",
    "connecting": "connect",
    "connected": "connect",
    "connections": "connect",
    "defines": "define",
    "defined": "define",
    "defining": "define",
}

# ── Synonyms ──

SYNONYMS = {
    "auth": ["login", "oauth", "session", "jwt", "authentication", "authorization"],
    "login": ["auth", "oauth", "session"],
    "equipment": ["pump", "surplus", "inventory", "item"],
    "publish": ["sync", "woocommerce", "gravco.net", "store"],
    "crash": ["oom", "locked", "died", "ghost", "compaction"],
    "bridge": ["inbox", "jsonl", "coordination", "sisters"],
    "frontend": ["react", "next", "tsx", "component", "page"],
    "backend": ["fastapi", "python", "router", "endpoint"],
    "database": ["model", "sqlmodel", "table", "migration", "alembic"],
    "deploy": ["docker", "compose", "droplet", "rebuild"],
}


def stem(word: str) -> str:
    """Poor man's stemmer — lookup table + suffix stripping."""
    w = word.lower()
    if w in STEM_MAP:
        return STEM_MAP[w]
    # Strip common suffixes
    for suffix in ["ing", "ed", "es", "er", "tion", "sion"]:
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            return w[:-len(suffix)]
    return w


def expand_terms(terms: List[str]) -> List[str]:
    """Expand query terms with synonyms."""
    expanded = set(terms)
    for t in terms:
        stemmed = stem(t)
        expanded.add(stemmed)
        if stemmed in SYNONYMS:
            expanded.update(SYNONYMS[stemmed])
        if t in SYNONYMS:
            expanded.update(SYNONYMS[t])
    return list(expanded)


# ── Type weights (some node types are more valuable answers) ──

TYPE_WEIGHTS = {
    "clue": 5.0,
    "decision": 4.0,
    "lesson": 3.5,
    "session": 3.0,
    "sister": 3.0,
    "build": 2.5,
    "endpoint": 2.0,
    "model": 2.0,
    "bridge_message": 1.5,
    "class": 1.5,
    "function": 1.2,
    "file": 1.0,
}


def ask(question: str, graph: AlexandriaGraph = None, limit: int = 10,
        expand_synonyms: bool = True, follow_edges: bool = True) -> List[Dict]:
    """Query Alexandria with stemming, synonyms, and type weighting.

    This is the upgrade over graph.query() — same interface, smarter matching.
    """
    if graph is None:
        graph = AlexandriaGraph()

    raw_terms = [t.lower() for t in question.split() if len(t) > 1]
    terms = expand_terms(raw_terms) if expand_synonyms else raw_terms

    scored = []
    for nid, attrs in graph.G.nodes(data=True):
        text = " ".join(str(v) for v in attrs.values()).lower() + " " + nid.lower()
        # Count matches (stemmed)
        stemmed_text = " ".join(stem(w) for w in text.split())
        score = 0
        for t in terms:
            st = stem(t)
            # Exact match worth more
            if t in text:
                score += 2
            elif st in stemmed_text:
                score += 1

        if score > 0:
            # Apply type weight
            node_type = attrs.get("type", "unknown")
            weight = TYPE_WEIGHTS.get(node_type, 1.0)
            weighted_score = score * weight
            scored.append((weighted_score, score, nid, attrs))

    scored.sort(key=lambda x: -x[0])

    results = []
    for weighted, raw, nid, attrs in scored[:limit]:
        result = {"id": nid, "score": weighted, "raw_score": raw, **attrs}

        # Optionally follow edges from top results
        if follow_edges and len(results) < 3:
            neighbors = []
            for neighbor in list(graph.G.successors(nid)) + list(graph.G.predecessors(nid)):
                edge_out = graph.G.get_edge_data(nid, neighbor)
                edge_in = graph.G.get_edge_data(neighbor, nid)
                edge = edge_out or edge_in or {}
                rel = edge.get("relation", "related")
                neighbors.append({"id": neighbor, "relation": rel})
            if neighbors:
                result["neighbors"] = neighbors[:5]

        results.append(result)

    return results


def format_results(results: List[Dict], compact: bool = True) -> str:
    """Format query results for a Claude session — token efficient."""
    if not results:
        return "No results found."

    lines = []
    for r in results:
        nid = r["id"]
        score = r["score"]
        ntype = r.get("type", "?")

        # Build a one-line summary based on type
        if ntype == "decision":
            summary = r.get("title", "")
        elif ntype == "lesson":
            summary = r.get("title", "")
        elif ntype == "session":
            summary = f"{r.get('name', '')} — {r.get('note', '')}"
        elif ntype == "clue":
            summary = r.get("message", "")[:120]
        elif ntype == "endpoint":
            summary = f"{r.get('method', '')} {r.get('path', '')} → {r.get('handler', '')}"
        elif ntype == "build":
            summary = f"{r.get('builder', '')}: {r.get('description', '')}"
        elif ntype == "file":
            hot = " 🔥" if r.get("hot_path") else ""
            imports = f" (imported {r.get('import_count', 0)}x)" if r.get("import_count") else ""
            summary = f"{r.get('path', '')}{hot}{imports}"
        elif ntype == "bridge_message":
            summary = f"{r.get('sender', '')}: {r.get('preview', '')[:80]}"
        elif ntype == "sister":
            summary = f"{r.get('name', '')} on {r.get('host', '')} — {r.get('role', '')}"
        else:
            summary = str({k: v for k, v in r.items()
                          if k not in ("id", "score", "raw_score", "neighbors")})[:100]

        line = f"[{score:.1f}] {ntype:15s} {nid}"
        if compact:
            line += f"\n{'':20s}{summary}"
        else:
            line += f"\n  Summary: {summary}"

        # Show neighbors if present
        if "neighbors" in r:
            for n in r["neighbors"][:3]:
                line += f"\n{'':20s}  → {n['relation']}: {n['id']}"

        lines.append(line)

    return "\n".join(lines)


def god_report(graph: AlexandriaGraph = None, top_n: int = 10) -> str:
    """Formatted god node report — the load-bearing pieces."""
    if graph is None:
        graph = AlexandriaGraph()

    gods = graph.god_nodes(top_n)
    lines = ["GOD NODES — most connected:"]
    for g in gods:
        ntype = g.get("type", "?")
        lines.append(f"  {g['connections']:3d} connections  {ntype:12s}  {g['id']}")
    return "\n".join(lines)


# ── CLI ──

if __name__ == "__main__":
    import sys
    graph = AlexandriaGraph()

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "what is alexandria"

    print(f"Q: {question}")
    print(f"Terms expanded: {expand_terms(question.lower().split())}")
    print()
    results = ask(question, graph)
    print(format_results(results))
    print()
    print(god_report(graph))
