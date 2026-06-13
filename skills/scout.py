"""Scout skill — card scanning + lead enrichment (scenario ①).

Reads raw inputs via the extractor/fixtures, writes every resulting fact into
the graph as a *proposed* edge through GraphCore, and routes low-confidence
fields to the decision inbox via sync.router. High-confidence facts flow in
silently (auto); low-confidence ones become N2 confirmation cards.

All graph state changes are real GraphCore calls — only the raw extraction
inputs are mocked.
"""

from __future__ import annotations

from typing import Any

from graph import Edge, GraphCore, Node
from extract import mock_extractor
from skills import cards, fixtures
from sync import router


def card_scan(graph: GraphCore, card_id: str) -> dict[str, Any]:
    """Scan a business card -> candidate contact(s) + proposed edges in graph.

    Returns {ok, candidates:[{node_id,label,company,fields}], cards:[N2...]}.
    The candidate list feeds the N1 picker; low-confidence fields become N2
    cards the caller pushes to the inbox.
    """
    result = mock_extractor.scan_business_card(card_id)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "scan failed"), "candidates": [], "cards": []}

    fields = {f["key"]: f for f in result["fields"]}
    hints = result.get("node_hints", {})
    person_id = hints.get("person")
    company_id = hints.get("company")

    # Ensure person/company nodes exist (idempotent upsert). The company name is
    # the low-confidence field, so its node label is still provisional until
    # confirmed — but the node must exist to hang edges on.
    name = fields.get("name", {}).get("value", "Unknown contact")
    company_name = fields.get("company", {}).get("value", "Unknown company")
    if person_id:
        graph.upsert_node(Node(id=person_id, type="person", label=name,
                               props={"title": fields.get("title", {}).get("value", ""),
                                      "email": fields.get("email", {}).get("value", ""),
                                      "phone": fields.get("phone", {}).get("value", "")}))
    if company_id:
        graph.upsert_node(Node(id=company_id, type="company", label=company_name))

    new_cards: list[dict] = []

    # works_at edge: proposed, real GraphCore write. Its confidence = the company
    # field confidence (the weak link), so it routes to a card.
    company_conf = fields.get("company", {}).get("confidence", 0.5)
    if person_id and company_id:
        edge = graph.propose(Edge(
            subject=person_id, predicate="works_at", object=company_id,
            source="business_card", extractor="GLiNER2",
            confidence=company_conf, status="proposed",
        ))
        if router.route(company_conf) == "card":
            new_cards.append(cards.make_card(
                "N2",
                title=f"Confirm company for {name}",
                body=f"Extracted company: \"{company_name}\" (confidence {company_conf:.0%}).",
                why="Company name OCR was low-confidence; confirm or correct before trusting it.",
                target_edge_id=edge.id,
                contact_id=person_id,
                payload={"field": "company", "current": company_name, "edge_id": edge.id},
            ))

    candidates = [{
        "node_id": person_id,
        "label": name,
        "company": company_name,
        "fields": result["fields"],
    }]
    return {"ok": True, "candidates": candidates, "cards": new_cards}


def lead_enrich(graph: GraphCore, company_id: str) -> dict[str, Any]:
    """Enrich a company from fixtures -> multiple proposed edges in the graph.

    Returns {ok, edge_ids:[...]} . All edges are proposed; high-confidence ones
    still land as proposals (enrichment is machine-sourced, so a human can scan
    them on the graph rather than each becoming a card)."""
    enrich = fixtures.get_company_enrichment(company_id)
    if enrich is None:
        return {"ok": False, "error": f"no enrichment for {company_id}", "edge_ids": []}

    edge_ids = []
    for fact in enrich["facts"]:
        edge = graph.propose(Edge(
            subject=company_id,
            predicate=fact["predicate"],
            object=fact["object"],
            source=fact["source"],
            extractor="LLM",
            confidence=fact["confidence"],
            status="proposed",
        ))
        edge_ids.append(edge.id)
    return {"ok": True, "edge_ids": edge_ids}
