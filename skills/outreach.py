"""Outreach skill — compose & send cold/re-engagement mail (scenario ②).

compose_mail asks the LLM seam for a draft, seeded with graph context plus any
remembered tone/angle preferences. send_mail produces a mock receipt, appends a
canned reply to the fixture thread, and signals the caller to run a digest so the
graph grows from the (mock) reply.

Only the email wording and the send receipt are mocked; the resulting graph
edges go through GraphCore via the digest step.
"""

from __future__ import annotations

from typing import Any

from graph import GraphCore
from llm import mock_llm
from skills import fixtures


def _ctx(graph: GraphCore, contact_id: str, angle: str | None, prefs: dict | None) -> dict[str, Any]:
    person = graph.get_node(contact_id)
    name = person.label if person else contact_id
    company = None
    project = None
    for e in graph.query(subject=contact_id):
        if e.predicate == "works_at" and e.status in ("confirmed", "corrected"):
            node = graph.get_node(e.object)
            company = node.label if node else e.object
    for e in graph.query():
        node = graph.get_node(e.object) if isinstance(e.object, str) else None
        if node and node.type == "project" and e.status != "retired":
            project = node.label
    prefs = prefs or {}
    return {
        "name": name,
        "company": company or "your team",
        "project": project or "your current initiative",
        "angle": angle or prefs.get("angle"),
        "tone": prefs.get("tone", "professional"),
    }


def compose_mail(graph: GraphCore, contact_id: str, angle: str | None = None,
                 prefs: dict | None = None) -> dict[str, Any]:
    """Return {ok, contact_id, body, thread_id}. body is an editable draft."""
    if graph.get_node(contact_id) is None:
        return {"ok": False, "error": f"unknown contact: {contact_id}"}
    body = mock_llm.compose_cold_mail(_ctx(graph, contact_id, angle, prefs))
    # The thread this contact's mail belongs to (canned). Used by send -> digest.
    thread_id = _thread_for(contact_id)
    return {"ok": True, "contact_id": contact_id, "body": body, "thread_id": thread_id}


def send_mail(contact_id: str, body: str) -> dict[str, Any]:
    """Mock-send: append the outbound body to the fixture thread so a later
    digest sees fresh content. Returns {ok, receipt, thread_id}."""
    thread_id = _thread_for(contact_id)
    try:
        fixtures.append_email_reply(thread_id, body)
    except KeyError as exc:
        # Constitution #3: surface the missing-thread case, don't swallow it.
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "receipt": f"Mail to {contact_id} queued (mock send). The reply has arrived.",
        "thread_id": thread_id,
    }


def _thread_for(contact_id: str) -> str:
    """Map a contact to its email thread. Single canned thread in the demo; a
    real build would look this up by participant."""
    for tid, thread in fixtures.EMAIL_THREADS.items():
        if thread.get("contact") == contact_id:
            return tid
    return "thread_andreas"
