"""GraphCore — the single source of truth for the relationship graph.

Implements graph/contract.md exactly. Storage = in-memory dicts with JSON
persistence. The storage backend is intentionally hidden behind this class so it
can be swapped (e.g. SQLite) without touching callers (contract invariant #5).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

from .models import Edge, Node


class GraphCore:
    def __init__(self, store_path: Optional[str] = None) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, Edge] = {}
        self._store_path = store_path

    # ---- persistence ----------------------------------------------------

    def load(self) -> bool:
        """Load from JSON if the store file exists. Returns True if loaded."""
        if not self._store_path or not os.path.exists(self._store_path):
            return False
        with open(self._store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._nodes = {n["id"]: Node.from_dict(n) for n in data.get("nodes", [])}
        self._edges = {e["id"]: Edge.from_dict(e) for e in data.get("edges", [])}
        return True

    def save(self) -> None:
        if not self._store_path:
            return
        data = self.snapshot()
        # Write to a temp file then rename so a crash mid-write can't corrupt the
        # store (the JSON file is the only persistence we have in MVP).
        tmp = self._store_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._store_path)

    def snapshot(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
        }

    def load_objects(self, nodes: list[Node], edges: list[Edge]) -> None:
        """Bulk-load fully-formed Node/Edge objects (e.g. demo seed / restore).

        This is the only sanctioned way to install edges with a pre-set status
        and timestamp: the propose/confirm/correct path always stamps t=now, so
        it cannot reproduce a fixed 92-day-old edge or a pre-built corrected/
        retired pair. Validation still runs in Edge.__post_init__, so bad data
        fails loud here too. Callers do not touch internal storage directly."""
        for n in nodes:
            self._nodes[n.id] = n
        for e in edges:
            self._edges[e.id] = e
        self.save()

    # ---- reads ----------------------------------------------------------

    def query(
        self,
        *,
        node_type: Optional[str] = None,
        status: Optional[str] = None,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        min_confidence: Optional[float] = None,
    ) -> list[Edge]:
        results = []
        for e in self._edges.values():
            if status is not None and e.status != status:
                continue
            if subject is not None and e.subject != subject:
                continue
            if predicate is not None and e.predicate != predicate:
                continue
            if min_confidence is not None and e.confidence < min_confidence:
                continue
            if node_type is not None:
                subj = self._nodes.get(e.subject)
                if subj is None or subj.type != node_type:
                    continue
            results.append(e)
        return results

    def get_node(self, node_id: str) -> Optional[Node]:
        return self._nodes.get(node_id)

    def list_nodes(self, *, node_type: Optional[str] = None) -> list[Node]:
        nodes = self._nodes.values()
        if node_type is not None:
            nodes = [n for n in nodes if n.type == node_type]
        return list(nodes)

    def get_edge(self, edge_id: str) -> Optional[Edge]:
        return self._edges.get(edge_id)

    # ---- writes ---------------------------------------------------------

    def upsert_node(self, node: Node) -> Node:
        self._nodes[node.id] = node
        self.save()
        return node

    def propose(self, edge: Edge) -> Edge:
        edge.status = "proposed"
        edge.t = time.time()
        self._edges[edge.id] = edge
        self.save()
        return edge

    def confirm(self, edge_id: str) -> Edge:
        edge = self._require_edge(edge_id)
        edge.status = "confirmed"
        edge.t = time.time()
        self.save()
        return edge

    def correct(self, edge_id: str, new_fields: dict[str, Any]) -> Edge:
        """Retire the old edge and create a new corrected edge pointing back at
        it via supersedes. Never mutates the old edge's facts (invariant #1)."""
        old = self._require_edge(edge_id)
        old.status = "retired"
        old.t = time.time()

        # Start from the old edge's facts, apply the human's corrections on top.
        # id/status/supersedes/t are managed here, not taken from new_fields, so a
        # caller can't accidentally break the audit chain.
        protected = {"id", "status", "supersedes", "t"}
        merged = {
            "subject": old.subject,
            "predicate": old.predicate,
            "object": old.object,
            "source": old.source,
            "extractor": old.extractor,
            "confidence": old.confidence,
        }
        for k, v in new_fields.items():
            if k in protected:
                continue
            merged[k] = v

        new_edge = Edge(
            subject=merged["subject"],
            predicate=merged["predicate"],
            object=merged["object"],
            source=merged["source"],
            extractor=merged["extractor"],
            confidence=float(merged["confidence"]),
            status="corrected",
            supersedes=old.id,
        )
        self._edges[new_edge.id] = new_edge
        self.save()
        return new_edge

    def retire(self, edge_id: str, *, superseded_by: Optional[str] = None) -> Edge:
        edge = self._require_edge(edge_id)
        edge.status = "retired"
        edge.t = time.time()
        if superseded_by is not None:
            # The successor records that it supersedes this edge; we link forward
            # too only if asked, keeping the co-evolution trail symmetric.
            successor = self._edges.get(superseded_by)
            if successor is not None:
                successor.supersedes = edge.id
        self.save()
        return edge

    def decay_scan(self, now: float, *, threshold_days: int = 90) -> list[Edge]:
        """Return confirmed/corrected edges whose t is older than threshold."""
        cutoff = now - threshold_days * 86400
        return [
            e
            for e in self._edges.values()
            if e.status in ("confirmed", "corrected") and e.t < cutoff
        ]

    # ---- internals ------------------------------------------------------

    def _require_edge(self, edge_id: str) -> Edge:
        edge = self._edges.get(edge_id)
        if edge is None:
            # Raise loudly rather than no-op: a write against a missing edge is a
            # caller bug, and a silent no-op would corrupt the audit trail.
            raise KeyError(f"edge not found: {edge_id}")
        return edge
