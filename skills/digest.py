"""Digest skill — email thread -> proposed triples in the graph (scenario ②).

Runs the (mock) GLiNER2-B extractor over a thread and proposes each triple as a
real edge. Commitments and next steps are high-risk (they imply the user will
act), so they route to the inbox as N5 cards via sync.router with
about_to_act=True; plain facts flow in as proposals.
"""

from __future__ import annotations

from typing import Any

from graph import Edge, GraphCore, Node
from extract import mock_extractor
from skills import cards
from sync import router

# Predicate kinds the extractor labels as high-risk: acting on the user's behalf.
_HIGH_RISK = {"commitment", "next_step"}


def digest(graph: GraphCore, thread_id: str) -> dict[str, Any]:
    """Return {ok, edge_ids:[...], cards:[N5...]}."""
    result = mock_extractor.digest_email_thread(thread_id)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "digest failed"), "edge_ids": [], "cards": []}

    edge_ids: list[str] = []
    new_cards: list[dict] = []

    for tri in result["triples"]:
        # Literal-object triples (commitments, next steps) have no target node;
        # they render on the graph as a literal node (front-end handles that).
        edge = graph.propose(Edge(
            subject=tri["subject"],
            predicate=tri["predicate"],
            object=tri["object"],
            source=f"email:{thread_id}",
            extractor="GLiNER2",
            confidence=tri["confidence"],
            status="proposed",
        ))
        edge_ids.append(edge.id)

        kind = tri.get("kind", "fact")
        about_to_act = kind in _HIGH_RISK
        if router.route(tri["confidence"], about_to_act=about_to_act) == "card":
            new_cards.append(cards.make_card(
                "N5",
                title=f"Review extracted {kind.replace('_', ' ')}",
                body=tri["object"],
                why=("Extracted from the latest reply. "
                     + ("High-risk (implies you'll act), so confirm before it's trusted."
                        if about_to_act else "Low confidence; confirm or correct.")),
                target_edge_id=edge.id,
                contact_id=result.get("contact"),
                payload={"edge_id": edge.id, "kind": kind},
            ))

    return {"ok": True, "edge_ids": edge_ids, "cards": new_cards}
