"""Graph Core data structures (see graph/contract.md for the SSOT schema)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

NODE_TYPES = ("person", "company", "project", "topic")
EXTRACTORS = ("GLiNER2", "human", "LLM", "GeminiVision", "Tavily")
STATUSES = ("proposed", "confirmed", "corrected", "retired")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class Node:
    type: str
    label: str
    id: str = ""
    props: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = _new_id("n")
        if self.type not in NODE_TYPES:
            raise ValueError(f"Node.type must be one of {NODE_TYPES}, got {self.type!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Node":
        return cls(type=d["type"], label=d["label"], id=d.get("id", ""), props=dict(d.get("props", {})))


@dataclass
class Edge:
    subject: str
    predicate: str
    object: Any  # node_id or literal value
    source: str
    extractor: str
    confidence: float
    status: str
    id: str = ""
    t: float = 0.0
    supersedes: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = _new_id("e")
        if self.t == 0.0:
            self.t = time.time()
        # Validate the closed enums up front so bad seed/extraction data fails loud,
        # not silently rendering as an unknown style in the UI (constitution #3).
        if self.extractor not in EXTRACTORS:
            raise ValueError(f"Edge.extractor must be one of {EXTRACTORS}, got {self.extractor!r}")
        if self.status not in STATUSES:
            raise ValueError(f"Edge.status must be one of {STATUSES}, got {self.status!r}")
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError(f"Edge.confidence must be in [0,1], got {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Edge":
        return cls(
            subject=d["subject"],
            predicate=d["predicate"],
            object=d["object"],
            source=d["source"],
            extractor=d["extractor"],
            confidence=float(d["confidence"]),
            status=d["status"],
            id=d.get("id", ""),
            t=float(d.get("t", 0.0)),
            supersedes=d.get("supersedes"),
        )
