"""Scout skill — card scanning + lead enrichment (scenario ①).

Reads raw inputs via the extractor/fixtures, writes every resulting fact into
the graph as a *proposed* edge through GraphCore, and routes low-confidence
fields to the decision inbox via sync.router. High-confidence facts flow in
silently (auto); low-confidence ones become N2 confirmation cards.

All graph state changes are real GraphCore calls — only the raw extraction
inputs are mocked.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from graph import Edge, GraphCore, Node
from extract import mock_extractor
from skills import cards, fixtures
from sync import router


def card_scan(graph: GraphCore, image_path: str) -> dict[str, Any]:
    """Scan a business card -> candidate contact(s) + proposed edges in graph.

    Returns {ok, candidates:[{node_id,label,company,fields}], cards:[N2...]}.
    The candidate list feeds the N1 picker; low-confidence fields become N2
    cards the caller pushes to the inbox.
    """
    cards_data = []
    try:
        import uuid
        import re
        import os
        import sys
        
        _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _ROOT not in sys.path:
            sys.path.append(_ROOT)
            
        from module_a.segmentation import segment_business_cards
        from module_a.agent import parse_business_card_image
        
        def safe_id(prefix, text):
            if not text: return f"{prefix}_{uuid.uuid4().hex[:8]}"
            clean = re.sub(r'[^a-z0-9]', '', text.lower())
            return f"{prefix}_{clean}"
            
        # Bypass OpenCV segmentation, just feed the raw image to the LLM directly
        parsed_result = parse_business_card_image(image_path)
        extracted_cards = parsed_result.get("cards", [])
        
        for info in extracted_cards:
            if info.get("name") or info.get("company"):
                name = info.get("name") or "Unknown Contact"
                company = info.get("company") or "Unknown Company"
                title = info.get("title") or ""
                email = info.get("email") or ""
                phone = info.get("phone") or ""
                
                person_id = safe_id("n_person", name)
                company_id = safe_id("n_company", company)
                
                cards_data.append({
                    "node_hints": {"person": person_id, "company": company_id},
                    "fields": [
                        {"key": "name", "value": name, "confidence": 0.95},
                        {"key": "company", "value": company, "confidence": 0.8},
                        {"key": "title", "value": title, "confidence": 0.9},
                        {"key": "email", "value": email, "confidence": 0.95},
                        {"key": "phone", "value": phone, "confidence": 0.95}
                    ]
                })
                
        if not cards_data:
            return {"ok": False, "error": "No business card detected in the image", "candidates": [], "cards": []}
            
    except Exception as e:
        print("Error during real scan:", e)
        return {"ok": False, "error": str(e), "candidates": [], "cards": []}

    new_cards: list[dict] = []
    candidates = []

    for card_data in cards_data:
        fields = {f["key"]: f for f in card_data["fields"]}
        hints = card_data.get("node_hints", {})
        person_id = hints.get("person")
        company_id = hints.get("company")

        name = fields.get("name", {}).get("value", "Unknown contact")
        company_name = fields.get("company", {}).get("value", "Unknown company")
        if person_id:
            graph.upsert_node(Node(id=person_id, type="person", label=name,
                                   props={"title": fields.get("title", {}).get("value", ""),
                                          "email": fields.get("email", {}).get("value", ""),
                                          "phone": fields.get("phone", {}).get("value", "")}))
        if company_id:
            graph.upsert_node(Node(id=company_id, type="company", label=company_name))

        company_conf = fields.get("company", {}).get("confidence", 0.5)
        if person_id and company_id:
            existing = [e for e in graph.query(subject=person_id, predicate="works_at") 
                        if e.object == company_id and e.status in ("proposed", "confirmed", "corrected")]
            if existing:
                edge = existing[0]
            else:
                edge = graph.propose(Edge(
                    subject=person_id, predicate="works_at", object=company_id,
                    source="business_card", extractor="GeminiVision",
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

        candidates.append({
            "node_id": person_id,
            "label": name,
            "company": company_name,
            "fields": card_data["fields"],
        })
        
    return {"ok": True, "candidates": candidates, "cards": new_cards}


def lead_enrich(graph: GraphCore, person_id: str, company_id: str) -> dict[str, Any]:
    """Enrich a person and company from real research agent -> multiple proposed edges in the graph.

    Returns {ok, edge_ids:[...]} . All edges are proposed; high-confidence ones
    still land as proposals (enrichment is machine-sourced, so a human can scan
    them on the graph rather than each becoming a card)."""
    
    company_node = graph.get_node(company_id)
    person_node = graph.get_node(person_id)
    if not company_node or not person_node:
        return {"ok": False, "error": f"no company or person node found", "edge_ids": []}
        
    company_name = company_node.label
    person_name = person_node.label
    
    try:
        from module_a.research_agent import enrich_business_card_data
    except ImportError:
        _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.append(os.path.dirname(_ROOT))
        from module_a.research_agent import enrich_business_card_data
        
    # Pass both names to do proper internet research
    structured_data = {"name": person_name, "company": company_name}
    try:
        enriched_data = enrich_business_card_data(structured_data)
    except Exception as e:
        return {"ok": False, "error": f"Research agent failed: {e}", "edge_ids": []}

    def _propose_unique(subj: str, pred: str, obj: Any, conf: float) -> Optional[Edge]:
        existing = [e for e in graph.query(subject=subj, predicate=pred) 
                    if e.object == obj and e.status in ("proposed", "confirmed", "corrected")]
        if not existing:
            return graph.propose(Edge(
                subject=subj, predicate=pred, object=obj,
                source="internet", extractor="Tavily", confidence=conf, status="proposed"
            ))
        return None

    edge_ids = []
    
    # Map the output of enrich_business_card_data to graph edges
    if enriched_data.get("company_website") and enriched_data["company_website"] != "N/A":
        edge = _propose_unique(company_id, "has_website", enriched_data["company_website"], 0.9)
        if edge: edge_ids.append(edge.id)
        
    if enriched_data.get("social_media_company") and isinstance(enriched_data["social_media_company"], list):
        for url in enriched_data["social_media_company"]:
            if url and url != "N/A":
                edge = _propose_unique(company_id, "has_social", url, 0.8)
                if edge: edge_ids.append(edge.id)

    if enriched_data.get("social_media_person") and isinstance(enriched_data["social_media_person"], list):
        for url in enriched_data["social_media_person"]:
            if url and url != "N/A":
                edge = _propose_unique(person_id, "has_social", url, 0.8)
                if edge: edge_ids.append(edge.id)

    if enriched_data.get("company_news_events"):
        news = enriched_data["company_news_events"]
        if isinstance(news, list):
            for n in news:
                edge = _propose_unique(company_id, "recent_news", n, 0.8)
                if edge: edge_ids.append(edge.id)
        elif isinstance(news, str) and news != "N/A":
            edge = _propose_unique(company_id, "recent_news", news, 0.8)
            if edge: edge_ids.append(edge.id)

    desc = enriched_data.get("other_crm_info", "")
    if desc and desc != "N/A":
        company_node.props["description"] = desc
        graph.upsert_node(company_node)

    return {"ok": True, "edge_ids": edge_ids}
