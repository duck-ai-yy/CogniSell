"""Skill registry — hot-pluggable capability list for the demo.

Each skill is a named capability the CRM can run. The registry only tracks
enabled/disabled state and metadata; the actual logic lives in the skill modules
(scout / strategist / outreach / digest / relationship). Toggling here lets the
demo show capabilities being plugged in and out at runtime. In-memory (MVP).
"""

from __future__ import annotations

from typing import Any

# Ordered so the UI lists them along the demo's narrative arc.
_SKILLS: dict[str, dict[str, Any]] = {
    "scout": {
        "label": "Scout",
        "desc": "Scan business cards & enrich leads into the graph.",
        "enabled": True,
    },
    "strategist": {
        "label": "Strategist",
        "desc": "Multi-role debate -> approach strategy card.",
        "enabled": True,
    },
    "outreach": {
        "label": "Outreach",
        "desc": "Compose & send cold/re-engagement mail.",
        "enabled": True,
    },
    "digest": {
        "label": "Digest",
        "desc": "Extract commitments & next steps from email.",
        "enabled": True,
    },
    "relationship": {
        "label": "Relationship",
        "desc": "Spot stale ties & suggest catch-ups.",
        "enabled": True,
    },
}


def list_skills() -> list[dict[str, Any]]:
    return [{"name": name, **meta} for name, meta in _SKILLS.items()]


def is_enabled(name: str) -> bool:
    skill = _SKILLS.get(name)
    return bool(skill and skill["enabled"])


def set_enabled(name: str, enabled: bool) -> dict[str, Any]:
    if name not in _SKILLS:
        raise KeyError(f"unknown skill: {name}")
    _SKILLS[name]["enabled"] = enabled
    return {"name": name, **_SKILLS[name]}


def toggle(name: str) -> dict[str, Any]:
    if name not in _SKILLS:
        raise KeyError(f"unknown skill: {name}")
    return set_enabled(name, not _SKILLS[name]["enabled"])


class SkillDisabledError(RuntimeError):
    """Raised when a disabled skill is invoked, so the API surfaces it to the
    user instead of silently doing nothing (constitution #3)."""
