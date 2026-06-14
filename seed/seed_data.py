"""Demo seed graph (fake data, deterministic — constitution #5).

This is the "existing book of relationships" BEFORE the demo scan: a handful of
contacts the salesperson already knows. The hero contact (Andreas Vogel) is NOT
seeded — he is built live when the user scans a business card, so the left panel
visibly grows during the demo.

What the seed provides:
  - Noise contacts (name + company) so the graph isn't empty and the new hero
    node stands out when it appears.
  - One established, going-cold customer (Markus Brandt) carrying a 92-day-old
    edge to trigger the warm-up reminder, plus a corrected->retired title pair so
    the four cognitive states are all visible from first paint (legend makes
    sense immediately) and the emotional-core correction has a target.

Edges are installed via load_objects so fixed timestamps and the supersedes pair
survive (propose/confirm/correct would stamp t=now).
"""

from __future__ import annotations

import time

from graph import Edge, GraphCore, Node

# Stable ids the API and front-end reference. Noise ids are kept exactly as the
# API expects (signals_scan targets n_noise_p2 / n_noise_c2 = Petra).
MARKUS = "n_noise_p1"
BREMER = "n_noise_c1"
MARKUS_TOPIC = "n_topic_pallet"

NOW = time.time()
T_92_DAYS_AGO = NOW - 92 * 86400
T_RECENT = NOW - 5 * 86400

NOISE = [
    (MARKUS, "Markus Brandt", BREMER, "Bremer Logistik AG"),
    ("n_noise_p2", "Petra Lindqvist", "n_noise_c2", "Nordic Drives AB"),
    ("n_noise_p3", "Henrik Sørensen", "n_noise_c3", "Aalborg Maskin"),
    ("n_noise_p4", "Claudia Reiter", "n_noise_c4", "Alpen Automation GmbH"),
]


_PERSON_PROPS: dict[str, dict[str, str]] = {
    MARKUS: {"title": "Head of Logistics", "email": "m.brandt@bremer-logistik.de"},
    "n_noise_p2": {"title": "Supply Chain Director", "email": "p.lindqvist@nordic-drives.se"},
    "n_noise_p3": {"title": "Technical Lead", "email": "h.sorensen@aalborg-maskin.dk"},
    "n_noise_p4": {"title": "Plant Manager", "email": "c.reiter@alpen-automation.de"},
}


def build_nodes() -> list[Node]:
    nodes: list[Node] = []
    for pid, pname, cid, cname in NOISE:
        props = dict(_PERSON_PROPS.get(pid, {}))
        nodes.append(Node(id=pid, type="person", label=pname, props=props))
        nodes.append(Node(id=cid, type="company", label=cname))
    nodes.append(Node(id=MARKUS_TOPIC, type="topic", label="Pallet Conveyor Upgrade"))
    return nodes


def build_edges() -> list[Edge]:
    edges: list[Edge] = [
        # Markus: the going-cold customer. works_at is 92 days old -> warm-up.
        Edge(id="e_mark_works", subject=MARKUS, predicate="works_at", object=BREMER,
             source="crm", extractor="human", confidence=0.99, status="confirmed",
             t=T_92_DAYS_AGO),
        # Cognitive-state showcase: title corrected from "Logistics Lead" to
        # "Head of Logistics". Old edge retired, new corrected edge supersedes it.
        Edge(id="e_mark_title_old", subject=MARKUS, predicate="has_title",
             object="Logistics Lead", source="business_card", extractor="GLiNER2",
             confidence=0.7, status="retired", t=T_92_DAYS_AGO),
        Edge(id="e_mark_title", subject=MARKUS, predicate="has_title",
             object="Head of Logistics", source="user", extractor="human",
             confidence=1.0, status="corrected", supersedes="e_mark_title_old",
             t=T_92_DAYS_AGO),
        # A low-confidence proposed edge so the "proposed" style shows at start.
        Edge(id="e_mark_topic", subject=MARKUS, predicate="interested_in",
             object=MARKUS_TOPIC, source="email", extractor="GLiNER2",
             confidence=0.44, status="proposed", t=T_RECENT),
    ]
    # Other noise contacts: recent, confirmed works_at.
    for pid, _pname, cid, _cname in NOISE[1:]:
        edges.append(Edge(
            id=f"e_{pid}_works", subject=pid, predicate="works_at", object=cid,
            source="crm", extractor="human", confidence=0.95, status="confirmed",
            t=T_RECENT,
        ))
    return edges


def load_into(graph: GraphCore) -> GraphCore:
    graph.load_objects(build_nodes(), build_edges())
    return graph
