"""
Alexandria Graph — the core knowledge structure.

Builds a persistent NetworkX graph from three sources:
  1. Code structure (tree-sitter AST extraction)
  2. Bridge conversations (JSONL message log)
  3. Acacia knowledge (lessons, decisions, governance)

The graph persists to disk as JSON. Each session loads it,
queries it, and optionally extends it. No cold-start cost
after the first build.

Inspired by Graphify's build.py — same NetworkX foundation,
extended with Triad-specific node types and relationships.
"""

import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

import networkx as nx


ALEXANDRIA_DIR = Path(__file__).parent
DEFAULT_GRAPH_PATH = ALEXANDRIA_DIR / "knowledge.json"


class AlexandriaGraph:
    """The Triad's persistent knowledge graph."""

    def __init__(self, graph_path: str = None):
        self.graph_path = Path(graph_path) if graph_path else DEFAULT_GRAPH_PATH
        self.G = nx.DiGraph()
        self._load()

    def _load(self):
        """Load existing graph from disk, or start fresh."""
        if self.graph_path.exists():
            try:
                with open(self.graph_path) as f:
                    data = json.load(f)
                for node in data.get("nodes", []):
                    self.G.add_node(node["id"], **{k: v for k, v in node.items() if k != "id"})
                for edge in data.get("edges", []):
                    src = edge.get("source", edge.get("from"))
                    tgt = edge.get("target", edge.get("to"))
                    if src and tgt and src in self.G and tgt in self.G:
                        attrs = {k: v for k, v in edge.items() if k not in ("source", "target", "from", "to")}
                        self.G.add_edge(src, tgt, **attrs)
            except (json.JSONDecodeError, KeyError):
                self.G = nx.DiGraph()

    def save(self):
        """Persist graph to disk."""
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "nodes": [{"id": nid, **attrs} for nid, attrs in self.G.nodes(data=True)],
            "edges": [{"source": u, "target": v, **d} for u, v, d in self.G.edges(data=True)],
            "meta": {
                "version": "0.1.0",
                "updated_at": datetime.utcnow().isoformat(),
                "node_count": self.G.number_of_nodes(),
                "edge_count": self.G.number_of_edges(),
            }
        }
        with open(self.graph_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    # ── Node types ──

    def add_file(self, path: str, language: str = None, **kwargs):
        """Add a source file node."""
        nid = f"file:{path}"
        self.G.add_node(nid, type="file", path=path, language=language, **kwargs)
        return nid

    def add_function(self, name: str, file_path: str, line: int = None, **kwargs):
        """Add a function/method node linked to its file."""
        nid = f"func:{file_path}:{name}"
        self.G.add_node(nid, type="function", name=name, file=file_path, line=line, **kwargs)
        file_nid = f"file:{file_path}"
        if file_nid in self.G:
            self.G.add_edge(file_nid, nid, relation="defines")
        return nid

    def add_class(self, name: str, file_path: str, line: int = None, **kwargs):
        """Add a class node linked to its file."""
        nid = f"class:{file_path}:{name}"
        self.G.add_node(nid, type="class", name=name, file=file_path, line=line, **kwargs)
        file_nid = f"file:{file_path}"
        if file_nid in self.G:
            self.G.add_edge(file_nid, nid, relation="defines")
        return nid

    def add_endpoint(self, method: str, path: str, handler: str, file_path: str, **kwargs):
        """Add an API endpoint node — first-class in Alexandria."""
        nid = f"endpoint:{method}:{path}"
        self.G.add_node(nid, type="endpoint", method=method, path=path,
                        handler=handler, file=file_path, **kwargs)
        func_nid = f"func:{file_path}:{handler}"
        if func_nid in self.G:
            self.G.add_edge(nid, func_nid, relation="handled_by")
        return nid

    def add_model(self, name: str, table: str, file_path: str, **kwargs):
        """Add a database model node — domain-aware."""
        nid = f"model:{name}"
        self.G.add_node(nid, type="model", name=name, table=table,
                        file=file_path, **kwargs)
        return nid

    # ── Triad-specific nodes ──

    def add_sister(self, name: str, host: str, role: str, **kwargs):
        """Add a Triad instance node."""
        nid = f"sister:{name}"
        self.G.add_node(nid, type="sister", name=name, host=host, role=role, **kwargs)
        return nid

    def add_build(self, commit: str, description: str, builder: str, **kwargs):
        """Record a build event — who shipped what."""
        nid = f"build:{commit}"
        self.G.add_node(nid, type="build", commit=commit, description=description,
                        builder=builder, built_at=datetime.utcnow().isoformat(), **kwargs)
        sister_nid = f"sister:{builder}"
        if sister_nid in self.G:
            self.G.add_edge(sister_nid, nid, relation="built")
        return nid

    def add_lesson(self, title: str, source: str, **kwargs):
        """Record a lesson learned — links to code and sisters."""
        nid = f"lesson:{hashlib.md5(title.encode()).hexdigest()[:8]}"
        self.G.add_node(nid, type="lesson", title=title, source=source,
                        learned_at=datetime.utcnow().isoformat(), **kwargs)
        return nid

    def add_bridge_message(self, msg_id: str, sender: str, topic: str, body_preview: str, **kwargs):
        """Index a bridge message as a queryable node."""
        nid = f"msg:{msg_id}"
        self.G.add_node(nid, type="bridge_message", sender=sender, topic=topic,
                        preview=body_preview[:200], **kwargs)
        sister_nid = f"sister:{sender}"
        if sister_nid in self.G:
            self.G.add_edge(sister_nid, nid, relation="sent")
        return nid

    # ── Relationships ──

    def link(self, source_id: str, target_id: str, relation: str, **kwargs):
        """Add a relationship between any two nodes."""
        if source_id in self.G and target_id in self.G:
            self.G.add_edge(source_id, target_id, relation=relation, **kwargs)

    def add_import(self, importer_file: str, imported: str):
        """Record an import relationship."""
        src = f"file:{importer_file}"
        tgt = f"file:{imported}"
        if src in self.G and tgt in self.G:
            self.G.add_edge(src, tgt, relation="imports")

    # ── Queries ──

    def query(self, question: str, limit: int = 10) -> List[Dict]:
        """Search nodes by keyword matching on all attributes."""
        terms = question.lower().split()
        scored = []
        for nid, attrs in self.G.nodes(data=True):
            text = " ".join(str(v) for v in attrs.values()).lower() + " " + nid.lower()
            score = sum(1 for t in terms if t in text)
            if score > 0:
                scored.append((score, nid, attrs))
        scored.sort(key=lambda x: -x[0])
        return [{"id": nid, "score": s, **attrs} for s, nid, attrs in scored[:limit]]

    def neighbors(self, node_id: str, depth: int = 1) -> Dict:
        """Get a node and its neighbors up to N hops."""
        if node_id not in self.G:
            # Try fuzzy match
            matches = [n for n in self.G.nodes if node_id.lower() in n.lower()]
            if matches:
                node_id = matches[0]
            else:
                return {"error": f"Node '{node_id}' not found"}

        result_nodes = {node_id}
        result_edges = []
        frontier = {node_id}

        for _ in range(depth):
            next_frontier = set()
            for n in frontier:
                for neighbor in list(self.G.successors(n)) + list(self.G.predecessors(n)):
                    if neighbor not in result_nodes:
                        next_frontier.add(neighbor)
                        result_nodes.add(neighbor)
                    edge_data = self.G.get_edge_data(n, neighbor) or self.G.get_edge_data(neighbor, n) or {}
                    result_edges.append({"from": n, "to": neighbor, **edge_data})
            frontier = next_frontier

        return {
            "center": node_id,
            "nodes": [{"id": n, **self.G.nodes[n]} for n in result_nodes],
            "edges": result_edges,
        }

    def god_nodes(self, top_n: int = 10) -> List[Dict]:
        """Find the most connected nodes — the load-bearing pieces."""
        degrees = [(nid, self.G.degree(nid), self.G.nodes[nid])
                    for nid in self.G.nodes]
        degrees.sort(key=lambda x: -x[1])
        return [{"id": nid, "connections": deg, **attrs}
                for nid, deg, attrs in degrees[:top_n]]

    def stats(self) -> Dict:
        """Graph statistics."""
        type_counts = {}
        for _, attrs in self.G.nodes(data=True):
            t = attrs.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "nodes": self.G.number_of_nodes(),
            "edges": self.G.number_of_edges(),
            "by_type": type_counts,
        }
