"""Strategist skill — multi-role approach debate (scenario ②).

Reads the contact's CONFIRMED facts from the graph, assembles context, and asks
the LLM seam for a 3-role debate (Champion / Skeptic / Closer) that converges
into a strategy card. The facts are real graph reads; only the argument prose is
canned via mock_llm.
"""

from __future__ import annotations

from typing import Any

from graph import GraphCore
from llm import mock_llm


def _ctx_from_graph(graph: GraphCore, contact_id: str) -> dict[str, Any]:
    """Pull what we know about the contact from confirmed/corrected edges, so the
    debate is grounded in current graph state."""
    person = graph.get_node(contact_id)
    name = person.label if person else contact_id

    company = None
    project = None
    topic = None

    # Walk the contact's own trusted edges for company; then hop to project/topic.
    for e in graph.query(subject=contact_id):
        if e.status in ("confirmed", "corrected") and e.predicate == "works_at":
            node = graph.get_node(e.object)
            company = node.label if node else e.object

    # Project/topic come from any non-retired edge touching the thread.
    for e in graph.query():
        if e.status == "retired":
            continue
        obj_node = graph.get_node(e.object) if isinstance(e.object, str) else None
        if obj_node and obj_node.type == "project":
            project = obj_node.label
        if obj_node and obj_node.type == "topic":
            topic = obj_node.label

    return {"name": name, "company": company, "project": project, "topic": topic}


def strategy_debate(graph: GraphCore, contact_id: str) -> dict[str, Any]:
    """Return {ok, contact_id, debate:{roles, strategy_card}}."""
    if graph.get_node(contact_id) is None:
        return {"ok": False, "error": f"unknown contact: {contact_id}"}
    ctx = _ctx_from_graph(graph, contact_id)
    debate = mock_llm.debate_arguments(ctx)
    return {"ok": True, "contact_id": contact_id, "debate": debate, "context": ctx}
