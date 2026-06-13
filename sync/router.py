"""Frictionless-sync routing hub.

Decides whether a freshly extracted fact can flow straight into the graph as a
silent proposal ("auto") or must surface as a decision card for the human
("card"). This is the heart of "frictionless sync": high-confidence, non-acting
facts don't interrupt; low-confidence facts and anything that precedes an
outward action (sending mail, committing on the user's behalf) always ask.

PrefStore remembers what the human chose ("remember this") so future routing can
relax — e.g. a confirmed approach angle or email tone is reused without asking
again. In-memory only (MVP); a real build would persist per-user.
"""

from __future__ import annotations

from typing import Any

AUTO_THRESHOLD = 0.85


def route(confidence: float, about_to_act: bool = False) -> str:
    """Return "auto" (confidence >= threshold and not an outward action) or
    "card" (low confidence, OR about to act on the user's behalf)."""
    if about_to_act:
        return "card"
    return "auto" if confidence >= AUTO_THRESHOLD else "card"


class PrefStore:
    """Remembered human preferences. Keyed by (contact_id, key)."""

    def __init__(self) -> None:
        self._prefs: dict[tuple[str, str], Any] = {}
        # Per-contact relaxed thresholds: once a human confirms a kind of fact,
        # we can trust similar future facts more. Demonstrates "remember".
        self._relaxed: dict[tuple[str, str], float] = {}

    def remember(self, contact_id: str, key: str, value: Any) -> None:
        self._prefs[(contact_id, key)] = value

    def get(self, contact_id: str, key: str, default: Any = None) -> Any:
        return self._prefs.get((contact_id, key), default)

    def all_for(self, contact_id: str) -> dict[str, Any]:
        return {k[1]: v for k, v in self._prefs.items() if k[0] == contact_id}

    def relax_threshold(self, contact_id: str, predicate: str, new_threshold: float) -> None:
        self._relaxed[(contact_id, predicate)] = new_threshold

    def threshold_for(self, contact_id: str, predicate: str) -> float:
        return self._relaxed.get((contact_id, predicate), AUTO_THRESHOLD)
