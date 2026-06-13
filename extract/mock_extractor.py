"""Mock extractor — stands in for GLiNER2 (Pioneer A: card->fields, B: email->
triples).

Real deployment runs GLiNER2 over OCR text / email bodies and returns typed
spans with per-field confidence. Here we read canned fixtures and hand back the
same shape, so downstream skills exercise the real confidence-routing logic
offline (constitution #5). Swap these two bodies for GLiNER2 inference to go
real; the return contracts stay fixed.
"""

from __future__ import annotations

from typing import Any

from skills import fixtures


def scan_business_card(card_id: str) -> dict[str, Any]:
    """Pioneer A: business card -> structured fields with per-field confidence.

    Returns {ok, card_id, node_hints, fields:[{key,value,confidence}]}. The
    company field carries ~0.62 confidence on purpose to trigger low-confidence
    confirmation downstream.
    """
    card = fixtures.get_business_card(card_id)
    if card is None:
        # Constitution #3: don't return empty fields silently — say what failed.
        return {"ok": False, "card_id": card_id, "error": f"no business card fixture for {card_id!r}"}

    fields = [
        {"key": k, "value": f["value"], "confidence": f["confidence"]}
        for k, f in card["fields"].items()
    ]
    return {
        "ok": True,
        "card_id": card_id,
        "node_hints": card.get("node_hints", {}),
        "fields": fields,
    }


def digest_email_thread(thread_id: str) -> dict[str, Any]:
    """Pioneer B: email thread -> relationship triples with confidence.

    Returns {ok, thread_id, contact, triples:[{subject,predicate,object,kind,
    confidence}]}. 'kind' in {commitment,next_step,fact}; commitment/next_step
    are high-risk and routed to the inbox by the caller.
    """
    thread = fixtures.get_email_thread(thread_id)
    if thread is None:
        return {"ok": False, "thread_id": thread_id, "error": f"no email thread fixture for {thread_id!r}"}

    return {
        "ok": True,
        "thread_id": thread_id,
        "contact": thread.get("contact"),
        "triples": list(thread.get("extracted_triples", [])),
    }
