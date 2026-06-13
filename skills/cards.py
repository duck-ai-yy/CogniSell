"""Decision-card factory.

A decision card is the unit the human reviews in the inbox. Shape:

    {
      id, node_type,        # N1..N7 — which scenario stage produced it
      title, body,          # human-readable summary
      why,                  # optional rationale (audit: "why am I being asked?")
      options,              # optional list for "choose" cards (e.g. angles)
      fields,               # optional list for field-confirmation cards
      target_edge_id,       # optional edge this card acts on (confirm/correct)
      contact_id,           # optional contact context
      payload,              # free dict carrying anything resolve() needs
    }

node_type maps to the spec's N1..N7 inbox stages. Kept as plain dicts (no class)
to stay JSON-trivial over the API — constitution #4, don't add entities.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional


def make_card(
    node_type: str,
    title: str,
    *,
    body: str = "",
    why: Optional[str] = None,
    options: Optional[list] = None,
    fields: Optional[list] = None,
    target_edge_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    payload: Optional[dict] = None,
) -> dict[str, Any]:
    return {
        "id": "card_" + uuid.uuid4().hex[:8],
        "node_type": node_type,
        "title": title,
        "body": body,
        "why": why,
        "options": options,
        "fields": fields,
        "target_edge_id": target_edge_id,
        "contact_id": contact_id,
        "payload": payload or {},
    }
