---
title: Closira AI Agent
emoji: 💇
colorFrom: purple
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Closira — Lumina Hair Studio AI Agent Backend

Containerised REST API backend for the Lumina Hair Studio AI agent.
Built with FastAPI + Groq (llama3-70b). Ready to connect to any frontend.

---

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd closira

# 2. Create your .env from the template
cp .env.example .env
# → Open .env and add your GROQ_API_KEY

# 3. Build and run (production)
docker compose up --build

# 4. API is now live at http://localhost:8000
# 5. Swagger UI: http://localhost:8000/docs
```

**Dev mode** (hot-reload, no rebuild needed on code changes):
```bash
docker compose --profile dev up
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ | — | From [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Use `llama-3.1-8b-instant` for dev |
| `HOST_PORT` | No | `8000` | Host port mapping |
| `ALLOWED_ORIGINS` | No | `*` | Comma-separated CORS origins |

Set `ALLOWED_ORIGINS=https://yourfrontend.com` before deploying to production.

---

## API Reference

### `POST /chat`
Send a user message. Creates the session automatically on first call.

**Request**
```json
{
  "session_id": "user-abc-123",
  "message": "What services do you offer?"
}
```
Omit `session_id` on the very first request — a UUID will be generated and returned.
**Persist the returned `session_id` in your frontend** for all subsequent turns.

**Response**
```json
{
  "session_id": "user-abc-123",
  "response": "We offer Standard Cut & Style from £45, Signature Textured Cuts from £75...",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

`current_stage` values: `"faq"` | `"lead_qualification"` | `"escalation"` | `"summary"`

Once `is_escalated` is `true`, the session is locked. Show the user a "human agent incoming" UI state.

---

### `POST /summary`
Generate a structured end-of-session summary. Call when the user closes the chat or when `is_escalated` becomes `true`.

**Request**
```json
{ "session_id": "user-abc-123" }
```

**Response**
```json
{
  "customer_intent": "Customer wants to book a Soft Wolf Cut and start with a free consultation.",
  "key_details_collected": {
    "interested_service": "Signature Textured Cut — Soft Wolf Cut",
    "wants_consultation": "Yes",
    "other_notes": null
  },
  "sop_gaps_identified": [],
  "recommended_next_action": "Send booking portal link and confirm consultation appointment."
}
```

---

### `GET /session/{session_id}`
Fetch current session state. Use to re-hydrate the UI after a page refresh.

**Response**
```json
{
  "session_id": "user-abc-123",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null,
  "lead_data": {
    "interested_service": null,
    "wants_consultation": null
  },
  "message_count": 4
}
```

---

### `DELETE /session/{session_id}`
Delete a session (e.g. on user logout or conversation reset).

---

### `GET /health`
Liveness probe. Returns `200 OK`. Use for Docker/k8s health checks.

---

## Frontend Integration Notes

```
Frontend                           Backend (this repo)
────────────────────────────────────────────────────────
1. First message  →  POST /chat (no session_id)
                  ←  { session_id: "abc", response: "..." }

2. Store session_id in localStorage / state

3. Every message  →  POST /chat { session_id: "abc", message: "..." }
                  ←  { response, current_stage, is_escalated }

4. If is_escalated → show "connecting to agent" UI + POST /summary

5. On chat close  →  POST /summary  (optional, for CRM)
                  →  DELETE /session/{id}  (cleanup)
```

---

## File Structure

```
closira/
├── main.py                 # FastAPI app — all endpoints
├── Dockerfile              # Multi-stage production image
├── docker-compose.yml      # Prod + dev profiles
├── .env.example            # Copy to .env, fill GROQ_API_KEY
├── .dockerignore
├── requirements.txt
│
├── agent/
│   ├── __init__.py
│   ├── state.py            # In-memory session store (swap for Redis in prod)
│   ├── prompts.py          # LLM system prompts, SOP grounding
│   ├── groq_client.py      # Groq API wrapper with retry logic
│   └── orchestrator.py     # Stage routing + pipeline logic
│
└── data/
    └── sop_data.json       # Canonical SOP — single source of truth
```

---

## Deployment

### Docker (any host)
```bash
docker compose up --build -d
```

### Fly.io
```bash
fly launch --dockerfile Dockerfile
fly secrets set GROQ_API_KEY=gsk_...
fly deploy
```

### Railway / Render
Point to the repo, set `GROQ_API_KEY` as an environment variable. Both platforms auto-detect the Dockerfile.

---

## Production Checklist

- [ ] Set `ALLOWED_ORIGINS` to your real frontend domain
- [ ] Set `GROQ_API_KEY` as a secret (not in the image)
- [ ] Replace `state.py`'s in-memory dict with Redis for multi-instance deployments
- [ ] Add auth middleware (API key or JWT) to `/chat` and `/summary`
- [ ] Enable HTTPS via a reverse proxy (Nginx, Traefik, or your cloud's LB)
- [ ] Set `GROQ_MODEL=llama-3.3-70b-versatile` in production (not the 8b dev model)
