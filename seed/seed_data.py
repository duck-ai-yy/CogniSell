"""Demo seed graph (fake data, deterministic — constitution #5).

Builds the Andreas Vogel / Stahlwerk Nord storyline plus noise contacts, and
loads it into a GraphCore. Edges are constructed directly (not via propose/
confirm/correct) so the demo state — including the corrected->retired supersedes
chain and the 92-day-old timestamp — is fixed and reproducible, not dependent on
when seeding runs.
"""

from __future__ import annotations

import time

from graph import Edge, GraphCore, Node

# Stable ids so the supersedes chain and front-end references are deterministic.
ANDREAS = "n_andreas"
STAHLWERK = "n_stahlwerk"
PROJ_EXPANSION = "n_proj_expansion"
TOPIC_RFQ = "n_topic_rfq"

# The "last contact" anchor: ~92 days ago, the hook for M3's decay_scan.
NOW = time.time()
T_92_DAYS_AGO = NOW - 92 * 86400
T_RECENT = NOW - 5 * 86400


def build_nodes() -> list[Node]:
    nodes = [
        Node(
            id=ANDREAS,
            type="person",
            label="Andreas Vogel",
            props={
                "title": "Head of Procurement",
                "email": "andreas.vogel@example.com",
                "phone": "demo-phone",
                "met_at": "Hannover Messe",
            },
        ),
        Node(
            id=STAHLWERK,
            type="company",
            label="Stahlwerk Nord GmbH",
            props={"domain": "stahlwerk-nord.de", "industry": "Steel manufacturing"},
        ),
        Node(
            id=PROJ_EXPANSION,
            type="project",
            label="Production Line Expansion",
            props={"stage": "planning"},
        ),
        Node(
            id=TOPIC_RFQ,
            type="topic",
            label="Conveyor Drive RFQ",
            props={},
        ),
    ]

    # Noise contacts: name + company only, to make the main thread stand out.
    noise = [
        ("n_noise_p1", "Markus Brandt", "n_noise_c1", "Bremer Logistik AG"),
        ("n_noise_p2", "Petra Lindqvist", "n_noise_c2", "Nordic Drives AB"),
        ("n_noise_p3", "Henrik Sorensen", "n_noise_c3", "Aalborg Maskin"),
        ("n_noise_p4", "Claudia Reiter", "n_noise_c4", "Alpen Automation GmbH"),
    ]
    for pid, pname, cid, cname in noise:
        nodes.append(Node(id=pid, type="person", label=pname))
        nodes.append(Node(id=cid, type="company", label=cname))
    return nodes


def build_edges() -> list[Edge]:
    edges = [
        # confirmed: solid, full colour.
        Edge(
            id="e_works_at",
            subject=ANDREAS,
            predicate="works_at",
            object=STAHLWERK,
            source="business_card",
            extractor="GLiNER2",
            confidence=0.97,
            status="confirmed",
            t=T_92_DAYS_AGO,  # last contact anchor for decay_scan
        ),
        # proposed, low confidence: dashed, grey, semi-transparent.
        Edge(
            id="e_interested_in",
            subject=ANDREAS,
            predicate="interested_in",
            object=PROJ_EXPANSION,
            source="email#2",
            extractor="GLiNER2",
            confidence=0.41,
            status="proposed",
            t=T_RECENT,
        ),
        Edge(
            id="e_company_runs_project",
            subject=STAHLWERK,
            predicate="runs_project",
            object=PROJ_EXPANSION,
            source="email#1",
            extractor="LLM",
            confidence=0.68,
            status="confirmed",
            t=T_RECENT,
        ),
        Edge(
            id="e_project_topic",
            subject=PROJ_EXPANSION,
            predicate="involves",
            object=TOPIC_RFQ,
            source="email#3",
            extractor="GLiNER2",
            confidence=0.55,
            status="proposed",
            t=T_RECENT,
        ),
        # The co-evolution pair: title corrected from "Procurement Manager" to
        # "Head of Procurement". Old edge retired, new corrected edge supersedes it.
        Edge(
            id="e_title_old",
            subject=ANDREAS,
            predicate="has_title",
            object="Procurement Manager",
            source="business_card",
            extractor="GLiNER2",
            confidence=0.72,
            status="retired",
            t=T_92_DAYS_AGO,
        ),
        Edge(
            id="e_title_corrected",
            subject=ANDREAS,
            predicate="has_title",
            object="Head of Procurement",
            source="user",
            extractor="human",
            confidence=1.0,
            status="corrected",
            supersedes="e_title_old",
            t=T_RECENT,
        ),
    ]

    # Noise works_at edges (all confirmed, plausible spread of confidence).
    noise = [
        ("e_noise_1", "n_noise_p1", "n_noise_c1", 0.9),
        ("e_noise_2", "n_noise_p2", "n_noise_c2", 0.88),
        ("e_noise_3", "n_noise_p3", "n_noise_c3", 0.85),
        ("e_noise_4", "n_noise_p4", "n_noise_c4", 0.91),
    ]
    for eid, pid, cid, conf in noise:
        edges.append(
            Edge(
                id=eid,
                subject=pid,
                predicate="works_at",
                object=cid,
                source="business_card",
                extractor="GLiNER2",
                confidence=conf,
                status="confirmed",
                t=T_RECENT,
            )
        )
    return edges


def load_into(graph: GraphCore) -> GraphCore:
    # propose/confirm/correct would overwrite t with now and break the fixed
    # demo timestamps + supersedes pair, so we install the known-good state via
    # the contract's bulk loader.
    graph.load_objects(build_nodes(), build_edges())
    return graph
