"""Canned external data for the offline demo.

In a real deployment every getter here is backed by an MCP / external service
(company DB, social, news, an email provider, business-card OCR). For the demo
they return fixed dicts so the whole flow runs offline and deterministically
(constitution #5). This is the ONE place fake external data lives; swap a getter
body for a live call to go real, callers don't change.

Edges/nodes derived from this data still go through GraphCore — only the *raw
inputs* are faked, not the cognitive state.
"""

from __future__ import annotations

from typing import Any

# Stable node ids shared with seed_data so re-scanning the demo card maps onto
# the existing Andreas/Stahlwerk thread instead of spawning duplicates.
ANDREAS = "n_andreas"
STAHLWERK = "n_stahlwerk"
PROJ_EXPANSION = "n_proj_expansion"
TOPIC_RFQ = "n_topic_rfq"


# --- business-card OCR (real: phone camera + OCR; here: canned text) --------
_BUSINESS_CARDS: dict[str, dict[str, Any]] = {
    "card_andreas": {
        "raw_ocr": (
            "STAHLWERK NORD GmbH\n"
            "Andreas Vogel\n"
            "Head of Procurement\n"
            "andreas.vogel@example.com\n"
            "demo-phone\n"
            "stahlwerk-nord.de"
        ),
        # Per-field confidence: the company line is smudged in the fixture, so it
        # comes back low (~0.62) and must route to the inbox for confirmation.
        "fields": {
            "name": {"value": "Andreas Vogel", "confidence": 0.95},
            "title": {"value": "Head of Procurement", "confidence": 0.88},
            "email": {"value": "andreas.vogel@example.com", "confidence": 0.93},
            "phone": {"value": "demo-phone", "confidence": 0.90},
            "company": {"value": "Stahlwerk Nord GmbH", "confidence": 0.62},
        },
        # Pre-known node ids so confirmed edges land on the seeded thread.
        "node_hints": {"person": ANDREAS, "company": STAHLWERK},
    },
}


# --- company enrichment (real: company DB / social / news; here: canned) ----
_COMPANY_ENRICHMENT: dict[str, dict[str, Any]] = {
    STAHLWERK: {
        "company_node": STAHLWERK,
        "facts": [
            {
                "predicate": "industry",
                "object": "Steel manufacturing",
                "source": "company_db",
                "confidence": 0.92,
            },
            {
                "predicate": "headcount",
                "object": "~1,200 employees",
                "source": "company_db",
                "confidence": 0.81,
            },
            {
                "predicate": "recent_news",
                "object": "Announced production line expansion (Q2)",
                "source": "news",
                "confidence": 0.74,
            },
            {
                "predicate": "runs_project",
                "object": PROJ_EXPANSION,
                "source": "news",
                "confidence": 0.7,
            },
        ],
    },
}


# --- email threads (real: email provider MCP; here: canned threads) ---------
# Mutable: send_mail appends a synthetic reply so digest has something to chew.
EMAIL_THREADS: dict[str, dict[str, Any]] = {
    "thread_andreas": {
        "contact": ANDREAS,
        "company": STAHLWERK,
        "messages": [
            {
                "from": "andreas.vogel@example.com",
                "body": (
                    "Thanks for reaching out. We're moving ahead on the production "
                    "line expansion and I'll need conveyor drive quotes by end of "
                    "month. I'll loop in our plant engineer Lena Krause next week."
                ),
            }
        ],
        # Triples GLiNER2-B would extract from the reply above.
        "extracted_triples": [
            {
                "subject": ANDREAS,
                "predicate": "committed_to",
                "object": "Send conveyor drive RFQ by end of month",
                "kind": "commitment",
                "confidence": 0.83,
            },
            {
                "subject": ANDREAS,
                "predicate": "next_step",
                "object": "Intro to plant engineer Lena Krause next week",
                "kind": "next_step",
                "confidence": 0.79,
            },
            {
                "subject": PROJ_EXPANSION,
                "predicate": "involves",
                "object": TOPIC_RFQ,
                "kind": "fact",
                "confidence": 0.86,
            },
        ],
    },
}


def get_business_card(card_id: str) -> dict[str, Any] | None:
    return _BUSINESS_CARDS.get(card_id)


def list_business_cards() -> list[str]:
    return list(_BUSINESS_CARDS.keys())


def get_company_enrichment(company_node_id: str) -> dict[str, Any] | None:
    return _COMPANY_ENRICHMENT.get(company_node_id)


def get_email_thread(thread_id: str) -> dict[str, Any] | None:
    return EMAIL_THREADS.get(thread_id)


def append_email_reply(thread_id: str, reply_body: str) -> None:
    """send_mail uses this to grow the thread, so a later digest has new content
    to extract — keeps the 'send -> graph grows' loop self-contained offline."""
    thread = EMAIL_THREADS.get(thread_id)
    if thread is None:
        raise KeyError(f"unknown thread: {thread_id}")
    thread["messages"].append({"from": "outbound", "body": reply_body})
