"""Relationship skill — staleness scan + catch-up suggestion (scenario ③).

scan_stale calls GraphCore.decay_scan to find edges that have gone cold.
catchup_suggest reads the contact's CURRENT graph state (title, open topic/
project, days since last contact) and asks the LLM seam for a nudge. Because the
suggestion is derived from live graph state, correcting an edge and recomputing
changes the suggestion — the M3 payoff.
"""

from __future__ import annotations

from typing import Any

from graph import GraphCore
from llm import mock_llm


def scan_stale(graph: GraphCore, now: float, threshold_days: int = 90) -> dict[str, Any]:
    """Return {ok, stale:[{edge_id, subject, contact_id, contact_label,
    days, predicate, object}]}."""
    stale_edges = graph.decay_scan(now, threshold_days=threshold_days)
    items = []
    for e in stale_edges:
        contact = graph.get_node(e.subject)
        days = int((now - e.t) / 86400)
        items.append({
            "edge_id": e.id,
            "contact_id": e.subject,
            "contact_label": contact.label if contact else e.subject,
            "days": days,
            "predicate": e.predicate,
            "object": e.object,
        })
    return {"ok": True, "stale": items}


def _ctx_from_graph(graph: GraphCore, contact_id: str, now: float) -> dict[str, Any]:
    """Assemble catch-up context from the contact's live edges. Reads title from
    the trusted (corrected>confirmed) edge, the latest open topic/project, and
    the oldest contact timestamp as 'days since contact'."""
    person = graph.get_node(contact_id)
    name = person.label if person else contact_id

    title = None
    oldest_t = now
    topic = None
    project = None

    for e in graph.query(subject=contact_id):
        if e.status == "retired":
            continue
        if e.predicate == "has_title" and e.status in ("confirmed", "corrected"):
            # corrected wins; query order isn't guaranteed so prefer corrected.
            if title is None or e.status == "corrected":
                title = e.object
        if e.status in ("confirmed", "corrected"):
            oldest_t = min(oldest_t, e.t)

    for e in graph.query():
        if e.status == "retired":
            continue
        node = graph.get_node(e.object) if isinstance(e.object, str) else None
        if node and node.type == "topic":
            topic = node.label
        if node and node.type == "project":
            project = node.label

    days = int((now - oldest_t) / 86400)
    return {
        "name": name,
        "title": title,
        "topic": topic,
        "project": project,
        "days_since_contact": days,
    }


def catchup_suggest(graph: GraphCore, contact_id: str, now: float) -> dict[str, Any]:
    """Return {ok, contact_id, suggestion:{headline,why,suggested_message},
    context}. Recomputed from live graph state each call."""
    if graph.get_node(contact_id) is None:
        return {"ok": False, "error": f"unknown contact: {contact_id}"}
    ctx = _ctx_from_graph(graph, contact_id, now)
    suggestion = mock_llm.catchup_suggestion(ctx)
    return {"ok": True, "contact_id": contact_id, "suggestion": suggestion, "context": ctx}
