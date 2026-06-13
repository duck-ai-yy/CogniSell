# Second Brain CRM

An audit-friendly "second brain" for long-cycle industrial sales. Customer
relationships are stored as a human-readable knowledge graph where every edge
carries a **cognitive state** (`proposed` / `confirmed` / `corrected` /
`retired`), so you can always see who believed what, with what confidence, and
how the picture evolved.

## Run locally

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Then open http://127.0.0.1:8000

On first launch the app seeds a demo graph (the Andreas Vogel / Stahlwerk Nord
storyline) into `graph_store.json`. Delete that file to reset to the seed.

## API

- `GET /api/health` — liveness check.
- `GET /api/graph` — full graph snapshot (nodes + edges).
- `GET /api/inbox` — decision inbox (stub, lands in M1).
- `POST /api/voice` — voice command (stub, lands in M1).
