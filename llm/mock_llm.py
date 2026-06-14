"""The single LLM seam.

Every LLM-generated *wording* in the product flows through one of these
functions. They return canned, deterministic strings so the demo runs offline
(constitution #5). To wire a real model later, replace ONLY this file: keep the
function signatures, swap the bodies for an API call. Nothing else imports a
model client, so the blast radius of going live is exactly this seam.

Note: only the *prose* is faked here. The graph's cognitive-state changes
(propose/confirm/correct/retire) are always real GraphCore calls — that is the
product's soul and must not be mocked.
"""

from __future__ import annotations

from typing import Any


def debate_arguments(ctx: dict[str, Any]) -> dict[str, Any]:
    """Three sub-roles argue, then converge into a strategy card.

    ctx carries facts already read from the graph (name, company, project,
    open topics) so the canned text can reference them — proving the strategy is
    grounded in graph state, even though the phrasing is fixed.
    """
    name = ctx.get("name", "the contact")
    company = ctx.get("company", "their company")
    project = ctx.get("project")
    topic = ctx.get("topic")

    project_clause = f"the {project}" if project else "their current initiative"
    topic_clause = topic or "the open RFQ"

    return {
        "roles": [
            {
                "role": "Champion",
                "stance": "Lead with the relationship and the live opportunity.",
                "argument": (
                    f"{name} already engaged us on {project_clause}. We have warm "
                    f"context at {company} — open with the value we can add to "
                    f"{topic_clause}, not a cold pitch."
                ),
            },
            {
                "role": "Skeptic",
                "stance": "Pressure-test the assumptions before we commit tone.",
                "argument": (
                    f"We last spoke months ago. {name}'s priorities at {company} may "
                    f"have shifted; if we assume {topic_clause} is still hot and it "
                    "isn't, we look out of touch. Acknowledge the gap."
                ),
            },
            {
                "role": "Closer",
                "stance": "Drive to a concrete, low-friction next step.",
                "argument": (
                    f"Don't over-explain. Offer {name} one specific, easy yes — a "
                    "15-minute call to align on requirements — and make declining "
                    "feel like the costlier option."
                ),
            },
        ],
        "strategy_card": {
            "approach_angle": (
                f"Re-open warmly around {project_clause}; lead with relevance, "
                "acknowledge the time gap, avoid a hard pitch."
            ),
            "opening_hook": (
                f"Saw movement on {project_clause} at {company} — wanted to make "
                f"sure {topic_clause} is still on your radar."
            ),
            "risk": (
                "Priorities may have shifted since last contact; don't presume the "
                "opportunity is unchanged."
            ),
            "next_step": "Propose a 15-minute alignment call this week.",
        },
    }


def compose_cold_mail(ctx: dict[str, Any]) -> str:
    """Draft a cold/re-engagement email using the real Sales Agent from module_b."""
    try:
        import os
        import sys
        from module_b.email_agent import write_cold_email
    except ImportError:
        import os
        import sys
        _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.append(os.path.dirname(_ROOT))
        from module_b.email_agent import write_cold_email

    name = ctx.get("name", "there")
    company = ctx.get("company", "your team")
    project = ctx.get("project", "your current initiative")
    angle = ctx.get("angle") or "warm re-open around the live opportunity"
    tone = ctx.get("tone", "professional")

    # Read the product doc
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    product_doc_path = os.path.join(os.path.dirname(_ROOT), "module_b", "our_product_doc.md")
    
    product_info = "Product documentation not available."
    if os.path.exists(product_doc_path):
        with open(product_doc_path, "r", encoding="utf-8") as f:
            product_info = f.read()
            
    # Prepare prompt for the real agent
    prompt = (
        f"Recipient Name: {name}\n"
        f"Recipient Company: {company}\n"
        f"Context/Project: {project}\n"
        f"Strategy/Angle: {angle}\n"
        f"Tone: {tone}\n"
        f"Please write a cold email based on the above information and our product capabilities."
    )
    
    try:
        # Pass the product info and prompt
        email_content = write_cold_email(product_info, prompt)
        return email_content
    except Exception as e:
        return f"[Error generating email: {str(e)}]\n\nFallback drafting:\nHi {name.split()[0]},\n..."


def catchup_suggestion(ctx: dict[str, Any]) -> dict[str, Any]:
    """A re-engagement nudge derived from CURRENT graph state.

    ctx is assembled fresh from the graph each time, so when an edge is
    corrected the recomputed suggestion changes — that is the M3 payoff.
    """
    name = ctx.get("name", "this contact")
    days = ctx.get("days_since_contact")
    title = ctx.get("title")
    topic = ctx.get("topic")
    project = ctx.get("project")

    days_clause = (
        f"It has been about {days} days since your last contact with {name}."
        if days is not None
        else f"It has been a while since your last contact with {name}."
    )
    title_clause = f" (now {title})" if title else ""
    hook = topic or project or "your last open thread"

    return {
        "headline": f"Reconnect with {name}{title_clause}",
        "why": (
            f"{days_clause} The last open thread was {hook}; a light check-in keeps "
            "the relationship warm before it goes cold."
        ),
        "suggested_message": (
            f"Hi {name.split()[0] if name else 'there'}, it's been a while — "
            f"wanted to check in on {hook} and see how things are progressing on "
            "your side. Happy to help if useful."
        ),
    }
