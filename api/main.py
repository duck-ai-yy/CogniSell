"""FastAPI app — M1+M2+M3 demo loop.

Wires the decision-inbox + preference state on top of GraphCore and the skill
modules. All graph reads/writes go through GraphCore; this module owns only the
app-level inbox (list of decision cards) and a PrefStore. Skills produce cards;
this module routes resolutions back into the graph.

Constitution #1: api imports skills + graph + sync, never the front-end, and
skills never import api. #3: every failure path returns a visible error payload.
#5: every external input is mocked behind fixtures/extractor, default offline.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STORE_PATH = os.path.join(_ROOT, "graph_store.json")
_WEB_DIR = os.path.join(_ROOT, "web")

# Add the parent directory (BusinessCardOCR) to sys.path to import module_a and module_b
sys.path.append(os.path.dirname(_ROOT))

from graph import GraphCore, Node, Edge
from seed import seed_data
from sync.router import PrefStore
from skills import scout, strategist, outreach, digest, relationship, registry, cards



# Fixed "now" for the demo so decay_scan deterministically flags the 92-day edge
# regardless of wall-clock drift between seeding and serving. Seed anchors edges
# relative to import-time now(); we read the same clock here.
NOW = time.time()

app = FastAPI(title="Second Brain CRM", version="0.3-M1M2M3")

graph = GraphCore(store_path=_STORE_PATH)
if not graph.load():
    seed_data.load_into(graph)

# App-level state (in-memory, MVP). The inbox is the list of pending decision
# cards; prefs remembers human choices for frictionless re-sync.
INBOX: list[dict[str, Any]] = []
PREFS = PrefStore()

# The single demo contact thread.
DEMO_CONTACT = "n_andreas"
DEMO_CARD = "card_andreas"
DEMO_COMPANY = "n_stahlwerk"


def _require_skill(name: str) -> None:
    if not registry.is_enabled(name):
        # Don't silently no-op a disabled skill — tell the caller (constitution #3).
        raise HTTPException(status_code=409, detail=f"Skill '{name}' is disabled. Enable it to continue.")


def _push_cards(new_cards: list[dict]) -> None:
    INBOX.extend(new_cards)


def _find_card(card_id: str) -> Optional[dict]:
    return next((c for c in INBOX if c["id"] == card_id), None)


# --------------------------------------------------------------------------
# Request bodies
# --------------------------------------------------------------------------

class SelectBody(BaseModel):
    ids: list[str]


class ResolveBody(BaseModel):
    action: str  # confirm | correct | choose | approve
    payload: dict[str, Any] = {}


class ContactBody(BaseModel):
    contact_id: str


class ComposeBody(BaseModel):
    contact_id: str


class SendBody(BaseModel):
    contact_id: str
    body: str


class CorrectBody(BaseModel):
    new_object: str


class MeetBody(BaseModel):
    when: str
    where: str


class VoiceBody(BaseModel):
    transcript: str


class JobChangeBody(BaseModel):
    contact_id: str
    new_company_name: str


# --------------------------------------------------------------------------
# Core / health (unchanged behaviour)
# --------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/graph")
def get_graph() -> dict:
    return graph.snapshot()


# --------------------------------------------------------------------------
# Scenario ① — scan & select
# --------------------------------------------------------------------------

import shutil
from fastapi import File, UploadFile

@app.post("/api/scan")
def scan(file: Optional[UploadFile] = File(None)) -> dict:
    _require_skill("scout")
    
    if file is not None and getattr(file, "filename", None):
        print(f"Received file: {file.filename}")
        image_path = os.path.join(_ROOT, "temp_scan.png")
        contents = file.file.read()
        print(f"File size: {len(contents)} bytes")
        with open(image_path, "wb") as buffer:
            buffer.write(contents)
    else:
        print("No file received, falling back to sample_real.png")
        # Using the real sample image generated previously
        image_path = os.path.join(_ROOT, "..", "sample_real.png")
        
    result = scout.card_scan(graph, image_path)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "scan failed"))
    _push_cards(result["cards"])
    return {"ok": True, "candidates": result["candidates"], "cards_added": len(result["cards"])}

class AddNodeBody(BaseModel):
    name: str
    company: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

@app.post("/api/nodes")
def add_person(body: AddNodeBody) -> dict:
    import uuid
    import re
    def safe_id(prefix, text):
        if not text: return f"{prefix}_{uuid.uuid4().hex[:8]}"
        clean = re.sub(r'[^a-z0-9]', '', text.lower())
        return f"{prefix}_{clean}"
        
    name = body.name or "Unknown Contact"
    company = body.company or "Unknown Company"
    
    person_id = safe_id("n_person", name)
    company_id = safe_id("n_company", company)
    
    # Check if person already exists to prevent duplicate logically
    if graph.get_node(person_id):
        # Already exists, just return it or we could append random string
        # Let's just append random string if user wants multiple same name
        # But wait, user said "人物不要重复" (persons shouldn't duplicate). 
        # So we should reuse the same person_id and just add new edges or do nothing!
        pass 
        
    graph.upsert_node(Node(id=person_id, label=name, type="person"))
    if body.company:
        graph.upsert_node(Node(id=company_id, label=company, type="company"))
        graph.propose(Edge(subject=person_id, predicate="works_at", object=company_id, source="manual", extractor="human", confidence=1.0))
        
    if body.title:
        graph.propose(Edge(subject=person_id, predicate="title", object=body.title, source="manual", extractor="human", confidence=1.0))
    if body.email:
        graph.propose(Edge(subject=person_id, predicate="email", object=body.email, source="manual", extractor="human", confidence=1.0))
    if body.phone:
        graph.propose(Edge(subject=person_id, predicate="phone", object=body.phone, source="manual", extractor="human", confidence=1.0))
        
    return {"ok": True, "node_id": person_id}

@app.delete("/api/nodes/{node_id}")
def delete_node(node_id: str) -> dict:
    node = graph.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="node not found")
    graph.delete_node(node_id)
    return {"ok": True}

@app.post("/api/scan/select")
def scan_select(body: SelectBody) -> dict:
    _require_skill("scout")
    confirmed = []
    for node_id in body.ids:
        # Confirm the works_at edge for the selected contact, then enrich.
        company_id = None
        
        # Gather all works_at edges
        all_works_at = list(graph.query(subject=node_id, predicate="works_at"))
        proposed_edges = [e for e in all_works_at if e.status == "proposed"]
        
        if proposed_edges:
            # Confirm the latest proposed edge
            latest_proposed = proposed_edges[-1]
            graph.confirm(latest_proposed.id)
            confirmed.append(latest_proposed.id)
            company_id = latest_proposed.object
            
            # Retire any other active works_at edges (past companies)
            for e in all_works_at:
                if e.id != latest_proposed.id and e.status in ("proposed", "confirmed", "corrected"):
                    graph.retire(e.id)
                    
        # If we found a company, enrich it
        if company_id:
            # Get the actual company name to use for enrichment
            company_node = graph.get_node(company_id)
            if company_node:
                scout.lead_enrich(graph, person_id=node_id, company_id=company_id)
                
    return {"ok": True, "confirmed_edges": confirmed, "graph_changed": True}


# --------------------------------------------------------------------------
# Decision inbox
# --------------------------------------------------------------------------

@app.get("/api/inbox")
def inbox() -> dict:
    return {"cards": INBOX}


@app.post("/api/inbox/{card_id}/resolve")
def resolve(card_id: str, body: ResolveBody) -> dict:
    card = _find_card(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"card not found: {card_id}")

    action = body.action
    note = ""
    edge_id = card.get("target_edge_id") or card.get("payload", {}).get("edge_id")

    if action == "confirm":
        if not edge_id:
            raise HTTPException(status_code=400, detail="card has no edge to confirm")
        graph.confirm(edge_id)
        # Remember: relax the threshold for this predicate so similar future
        # facts can flow in without asking again (frictionless sync).
        edge = graph.get_edge(edge_id)
        if edge and card.get("contact_id"):
            PREFS.relax_threshold(card["contact_id"], edge.predicate, 0.6)
        note = "Edge confirmed; threshold relaxed for similar facts."

    elif action == "correct":
        if not edge_id:
            raise HTTPException(status_code=400, detail="card has no edge to correct")
        new_object = body.payload.get("new_object")
        if new_object is None:
            raise HTTPException(status_code=400, detail="correct requires payload.new_object")
        graph.correct(edge_id, {"object": new_object, "extractor": "human", "confidence": 1.0, "source": "user"})
        note = "Edge corrected (old retired, new corrected edge supersedes it)."

    elif action == "choose":
        choice = body.payload.get("choice")
        if choice is None:
            raise HTTPException(status_code=400, detail="choose requires payload.choice")
        if card.get("contact_id"):
            PREFS.remember(card["contact_id"], "angle", choice)
        note = f"Remembered approach angle: {choice}."

    elif action == "approve":
        if card.get("node_type") == "N8":
            # Signal card: capture the detected opportunity into the graph as a
            # confirmed lead the human chose to act on.
            company_id = card.get("payload", {}).get("company_id")
            if company_id:
                e = graph.propose(Edge(
                    subject=company_id, predicate="signal_tender",
                    object="Conveyor-systems procurement (rumored)",
                    source="social", extractor="LLM", confidence=0.6, status="proposed",
                ))
                graph.confirm(e.id)
            note = "Signal captured into the graph; follow-up flagged."
        else:
            # Approve-and-act cards (e.g. a commitment): confirm the underlying edge.
            if edge_id:
                graph.confirm(edge_id)
            note = "Action approved; underlying fact confirmed."

    else:
        raise HTTPException(status_code=400, detail=f"unknown action: {action}")

    INBOX.remove(card)
    return {"ok": True, "graph_changed": True, "note": note}


# --------------------------------------------------------------------------
# Scenario ① cont. — meeting details captured onto the left-side record
# --------------------------------------------------------------------------

@app.post("/api/contact/{contact_id}/meet")
def contact_meet(contact_id: str, body: MeetBody) -> dict:
    """Record where/when we met onto the contact's left-side record.

    Writes to node props AND lays down a confirmed `met_at` edge to an event
    node, so the meeting shows up on the graph (the left panel's job: who, and
    how connected). Human-entered => confirmed, full confidence.
    """
    node = graph.get_node(contact_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"contact not found: {contact_id}")
    node.props["met_when"] = body.when
    node.props["met_where"] = body.where
    graph.upsert_node(node)

    event_id = "n_event_meet"
    graph.upsert_node(Node(id=event_id, type="topic", label=body.where))
    edge = graph.propose(Edge(
        subject=contact_id, predicate="met_at", object=event_id,
        source="user", extractor="human", confidence=1.0, status="proposed",
    ))
    graph.confirm(edge.id)
    return {"ok": True, "graph_changed": True, "event_id": event_id, "edge_id": edge.id}


# --------------------------------------------------------------------------
# Scenario ② — strategy, compose, send
# --------------------------------------------------------------------------

@app.post("/api/strategy")
def strategy(body: ContactBody) -> dict:
    _require_skill("strategist")
    result = strategist.strategy_debate(graph, body.contact_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "strategy failed"))
    sc = result["debate"]["strategy_card"]
    # N3 card: let the human pick / lock the approach angle (choose -> remember).
    card = cards.make_card(
        "N3",
        title=f"Approach strategy for {result['context'].get('name', body.contact_id)}",
        body=sc["approach_angle"],
        why="Converged from a Champion/Skeptic/Closer debate over confirmed facts.",
        options=[sc["approach_angle"], "Lead with a direct value pitch", "Wait and nurture"],
        contact_id=body.contact_id,
        payload={"strategy_card": sc},
    )
    _push_cards([card])
    return {"ok": True, "debate": result["debate"], "context": result["context"], "card_added": card["id"]}


@app.post("/api/mail/compose")
def mail_compose(body: ComposeBody) -> dict:
    _require_skill("outreach")
    prefs = PREFS.all_for(body.contact_id)
    result = outreach.compose_mail(graph, body.contact_id, angle=prefs.get("angle"), prefs=prefs)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "compose failed"))
    card = cards.make_card(
        "N4",
        title="Review outreach draft",
        body=result["body"],
        why="Draft generated from graph context + remembered preferences. Edit before sending; edits are remembered.",
        contact_id=body.contact_id,
        payload={"editable": True, "thread_id": result["thread_id"]},
    )
    _push_cards([card])
    return {"ok": True, "body": result["body"], "card_added": card["id"]}


@app.post("/api/mail/send")
def mail_send(body: SendBody) -> dict:
    _require_skill("outreach")
    # Remember the sent body's tone choice: if the user kept it casual, learn it.
    if body.body and body.body.lower().startswith("hi "):
        PREFS.remember(body.contact_id, "tone", "casual")
    result = outreach.send_mail(body.contact_id, body.body)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "send failed"))

    # Remove the consumed N4 draft card(s) so the inbox can't double-send.
    INBOX[:] = [c for c in INBOX if not (c["node_type"] == "N4" and c.get("contact_id") == body.contact_id)]

    # Sending triggers a digest of the (now-grown) thread -> graph grows.
    dcards = []
    if registry.is_enabled("digest"):
        dres = digest.digest(graph, result["thread_id"])
        if dres.get("ok"):
            _push_cards(dres["cards"])
            dcards = dres["cards"]
    return {
        "ok": True,
        "receipt": result["receipt"],
        "graph_changed": True,
        "cards_added": len(dcards),
        "digest_skipped": not registry.is_enabled("digest"),
    }


# --------------------------------------------------------------------------
# Scenario ③ — staleness, catch-up, emotional-core correction
# --------------------------------------------------------------------------

@app.post("/api/catchup/scan")
def catchup_scan() -> dict:
    _require_skill("relationship")
    stale = relationship.scan_stale(graph, NOW)
    added = []
    seen: set[str] = set()
    for item in stale["stale"]:
        cid = item["contact_id"]
        # One warm-up per contact even if several of their edges went cold.
        if cid in seen:
            continue
        seen.add(cid)
        sug = relationship.catchup_suggest(graph, cid, NOW)
        if not sug.get("ok"):
            continue
        s = sug["suggestion"]
        card = cards.make_card(
            "N6",
            title=s["headline"],
            body=s["suggested_message"],
            why=s["why"],
            contact_id=cid,
            payload={"days": item["days"], "stale_edge_id": item["edge_id"]},
        )
        _push_cards([card])
        added.append(card)
    return {"ok": True, "stale": stale["stale"], "cards_added": len(added)}


@app.post("/api/edge/{edge_id}/correct")
def edge_correct(edge_id: str, body: CorrectBody) -> dict:
    if graph.get_edge(edge_id) is None:
        raise HTTPException(status_code=404, detail=f"edge not found: {edge_id}")
    old = graph.get_edge(edge_id)
    contact_id = old.subject
    new_edge = graph.correct(edge_id, {"object": body.new_object, "extractor": "human",
                                        "confidence": 1.0, "source": "user"})
    # Recompute the catch-up suggestion from the now-updated graph to prove
    # "change an edge -> the suggestion changes" (the M3 emotional-core payoff).
    recomputed = None
    if registry.is_enabled("relationship"):
        sug = relationship.catchup_suggest(graph, contact_id, NOW)
        if sug.get("ok"):
            recomputed = sug["suggestion"]
    return {
        "ok": True,
        "graph_changed": True,
        "new_edge_id": new_edge.id,
        "superseded": edge_id,
        "recomputed_catchup": recomputed,
    }


@app.post("/api/signals/scan")
def signals_scan() -> dict:
    """Proactive signal: a tracked contact posted something that may mean a
    tender is opening. Surfaces an N8 card for the human to act on or dismiss."""
    card = cards.make_card(
        "N8",
        title="Nordic Drives AB may be going to tender",
        body="Petra Lindqvist (Nordic Drives AB) just posted about an upcoming "
             "conveyor-systems procurement. An RFQ window may be opening.",
        why="Detected from a new social post; matches your conveyor-drive focus.",
        contact_id="n_noise_p2",
        payload={"company_id": "n_noise_c2"},
    )
    _push_cards([card])
    return {"ok": True, "card_added": card["id"]}


@app.post("/api/edge/{edge_id}/confirm")
def edge_confirm(edge_id: str) -> dict:
    if graph.get_edge(edge_id) is None:
        raise HTTPException(status_code=404, detail=f"edge not found: {edge_id}")
    edge = graph.confirm(edge_id)
    return {"ok": True, "graph_changed": True, "edge_id": edge.id, "status": edge.status}


# --------------------------------------------------------------------------
# Voice (mock NLU — keyword routing)
# --------------------------------------------------------------------------

@app.post("/api/voice")
def voice(body: VoiceBody) -> dict:
    t = body.transcript.lower().strip()
    if not t:
        return {"action": "none", "result": {"message": "Empty transcript — didn't catch that."}}

    # "keep <name>" -> treat as scan + select the demo contact.
    if "keep" in t:
        scan()  # ensures candidate/cards exist
        scan_select(SelectBody(ids=[DEMO_CONTACT]))
        return {"action": "scan_select", "result": {"message": f"Kept and enriched {DEMO_CONTACT}.", "graph_changed": True}}

    # "fix/correct ... company" -> locate the company (works_at) edge and correct.
    if ("fix" in t or "correct" in t) and "company" in t:
        target = None
        for e in graph.query(subject=DEMO_CONTACT, predicate="works_at"):
            if e.status in ("proposed", "confirmed", "corrected"):
                target = e
        if target is None:
            return {"action": "none", "result": {"message": "No company edge found to correct."}}
        return {"action": "correct_company", "result": {
            "message": "Found the company edge — provide the corrected name.",
            "edge_id": target.id, "needs_input": True}}

    # "catch up" -> run the staleness scan.
    if "catch up" in t or "catch-up" in t or "catchup" in t:
        res = catchup_scan()
        return {"action": "catchup_scan", "result": {"message": f"Found {res['cards_added']} catch-up(s).", **res}}

    # Constitution #3: don't fail silently on unrecognised commands.
    return {"action": "none", "result": {"message": f"Didn't understand: \"{body.transcript}\". Try 'keep Andreas', 'fix the company', or 'catch up'."}}


# --------------------------------------------------------------------------
# Skills hot-plug
# --------------------------------------------------------------------------

@app.get("/api/skills")
def skills_list() -> dict:
    return {"skills": registry.list_skills()}


@app.post("/api/skills/{name}/toggle")
def skills_toggle(name: str) -> dict:
    try:
        updated = registry.toggle(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown skill: {name}")
    return {"ok": True, "skill": updated}


# --------------------------------------------------------------------------
# Contact detail + job-change signal
# --------------------------------------------------------------------------

@app.get("/api/contact/{contact_id}")
def get_contact(contact_id: str) -> dict:
    node = graph.get_node(contact_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"contact not found: {contact_id}")
    edges = graph.query(subject=contact_id)
    active = [e.to_dict() for e in edges if e.status != "retired"]
    history = [e.to_dict() for e in edges if e.status == "retired"]
    return {"node": node.to_dict(), "edges": active, "history": history}


@app.post("/api/signals/job-change")
def job_change(body: JobChangeBody) -> dict:
    node = graph.get_node(body.contact_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"contact not found: {body.contact_id}")
    # Find the current works_at edge
    target_edge = None
    for e in graph.query(subject=body.contact_id, predicate="works_at"):
        if e.status in ("proposed", "confirmed", "corrected"):
            target_edge = e
            break
    if target_edge is None:
        raise HTTPException(status_code=400, detail="no active works_at edge to update")
    # Create new company node
    new_company_id = f"n_company_{body.new_company_name.lower().replace(' ', '_')[:12]}"
    graph.upsert_node(Node(id=new_company_id, type="company", label=body.new_company_name))
    # Correct the old edge (old -> retired, new -> corrected with supersedes)
    new_edge = graph.correct(target_edge.id, {
        "object": new_company_id,
        "extractor": "LLM",
        "confidence": 0.85,
        "source": "social_monitor"
    })
    return {
        "ok": True,
        "graph_changed": True,
        "new_edge_id": new_edge.id,
        "old_edge_id": target_edge.id,
        "new_company_id": new_company_id
    }


# --------------------------------------------------------------------------
# Static shell
# --------------------------------------------------------------------------

@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(_WEB_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=os.path.join(_WEB_DIR, "static")), name="static")
