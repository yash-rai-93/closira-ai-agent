# Closira — Lumina Hair Studio AI Agent

> Production-ready multi-stage conversational AI backend for a B2B SaaS customer support platform.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [Dependencies](#dependencies)
4. [Environment Variables](#environment-variables)
5. [Running the Server](#running-the-server)
6. [CLI Testing Tool](#cli-testing-tool)
7. [API Contract](#api-contract)
8. [File Structure](#file-structure)
9. [Pipeline Stages](#pipeline-stages)
10. [Known Limitations](#known-limitations)
11. [Deployment Notes](#deployment-notes)

---

## Architecture Overview

```
User (HTTP / CLI)
      │
      ▼
 POST /chat                      POST /summary
      │                                │
      ▼                                ▼
 orchestrator.py ──────── generate_summary()
   │         │
   │         └─── ThreadPoolExecutor ───► _run_escalation_check() [Stage 3]
   │
   ├─── Stage 1: FAQ Answering      ← groq_client.chat_completion()
   ├─── Stage 2: Lead Qualification ← deterministic state machine
   └─── Stage 4: Summary            ← groq_client.json_completion()
         │
         ▼
     state.py (in-memory SESSION_STORE)
```

---

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd closira

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your Groq API key
export GROQ_API_KEY=gsk_your_key_here

# 5a. Start the API server
uvicorn main:app --reload --port 8000

# 5b. OR run the CLI demo (no server needed)
python cli.py
```

---

## Dependencies

Create `requirements.txt` with:

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
groq>=0.9.0
pydantic>=2.7.0
python-dotenv>=1.0.0   # optional, for .env file support
```

Install with:
```bash
pip install -r requirements.txt
```

> **Groq Python SDK**: `pip install groq`
> Requires Python 3.10+.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | — | API key from [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | No | `llama3-70b-8192` | Override the Groq model. Use `llama3-8b-8192` for dev. |

You can also use a `.env` file:
```
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama3-8b-8192
```
Then add `from dotenv import load_dotenv; load_dotenv()` at the top of `main.py` or `cli.py`.

---

## Running the Server

```bash
# Development (auto-reload on file changes)
uvicorn main:app --reload --port 8000

# Production (multi-worker)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# With debug logging
uvicorn main:app --reload --port 8000 --log-level debug
```

Swagger UI is available at: **http://localhost:8000/docs**
ReDoc is available at: **http://localhost:8000/redoc**

---

## CLI Testing Tool

```bash
python cli.py
```

The CLI runs the full agent pipeline locally without an HTTP server:

```
══════════════════════════════════════════════════════════
  💇  Lumina Hair Studio — AI Receptionist (CLI Demo)
══════════════════════════════════════════════════════════
  Type your message and press Enter.
  Type 'quit' to end the session and view a summary.
──────────────────────────────────────────────────────────

  Session ID: cli-a3f92c1b

You: What's your cancellation policy?

  [STAGE: FAQ]
Agent: We require a minimum of 24 hours notice for cancellations. Late cancellations may incur a fee.
```

---

## API Contract

### `POST /chat`

Process a single user message.

**Request**
```json
{
  "session_id": "user-abc-123",
  "message": "What is your cancellation policy?"
}
```

**Response**
```json
{
  "response": "We require a minimum of 24 hours notice for any cancellations. Late cancellations may incur a fee.",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

**Stage values**: `"faq"` | `"lead_qualification"` | `"escalation"` | `"summary"`

---

### `POST /summary`

Generate a structured end-of-session summary.

**Request**
```json
{
  "session_id": "user-abc-123"
}
```

**Response**
```json
{
  "customer_intent": "The customer wanted to book a Signature Textured Cut and was interested in a free consultation.",
  "key_details_collected": {
    "interested_service": "Signature Textured Cut (Wavy Shag)",
    "wants_consultation": "Yes",
    "other_notes": null
  },
  "sop_gaps_identified": [],
  "recommended_next_action": "Send the customer the booking portal link and WhatsApp contact to confirm their consultation appointment."
}
```

---

### `GET /health`

Liveness probe. Returns `200 OK`.

```json
{ "status": "ok", "service": "closira-lumina-agent" }
```

---

### `GET /session/{session_id}` ⚠️ Debug only

Returns raw session state. **Disable in production.**

---

## File Structure

```
closira/
├── main.py                    # FastAPI app, endpoints, Pydantic schemas
├── cli.py                     # Interactive CLI demo / testing tool
├── requirements.txt           # Python dependencies
├── prompt_design.md           # Prompt engineering rationale
├── README.md                  # This file
│
├── agent/
│   ├── __init__.py
│   ├── state.py               # In-memory session management
│   ├── prompts.py             # All LLM prompt templates + schemas
│   ├── groq_client.py         # Groq API wrapper with retry logic
│   └── orchestrator.py        # Stage routing + pipeline logic
│
├── data/
│   └── sop_data.json          # Canonical SOP (single source of truth)
│
└── test_transcripts/
    ├── 01_in_scope_faq.md
    ├── 02_out_of_scope.md
    ├── 03_escalation_trigger.md
    ├── 04_lead_qualification.md
    └── 05_conversation_summary.md
```

---

## Pipeline Stages

| Stage | Name | Trigger | Behaviour |
|---|---|---|---|
| 1 | FAQ Answering | Default (all new sessions) | Answers from SOP JSON only |
| 2 | Lead Qualification | Booking/availability keyword detected | Asks 2 scripted questions sequentially |
| 3 | Escalation Detection | Runs on EVERY message (concurrent) | LLM classifier; locks session on trigger |
| 4 | Summary | POST /summary or CLI quit/escalation | Returns structured JSON for CRM |

### Stage Transition Diagram

```
         ┌─────────────┐
         │    START     │
         └──────┬──────┘
                │
                ▼
         ┌─────────────┐   booking intent    ┌──────────────────────┐
         │     FAQ      │──────────────────►  │  Lead Qualification  │
         │  (Stage 1)   │◄──────────────────  │     (Stage 2)        │
         └──────┬──────┘   both Qs answered   └──────────────────────┘
                │
                │  escalation trigger (concurrent, any stage)
                ▼
         ┌─────────────┐
         │  Escalation  │
         │  (Stage 3)   │
         └──────┬──────┘
                │
                │  POST /summary or CLI quit
                ▼
         ┌─────────────┐
         │   Summary    │
         │  (Stage 4)   │
         └─────────────┘
```

---

## Known Limitations

1. **In-memory sessions only** — All session data is lost on server restart. Replace
   `SESSION_STORE` dict in `state.py` with Redis for persistence.

2. **No authentication** — The `/chat` and `/summary` endpoints have no auth. Any client
   can read or write any session by guessing the `session_id`. Add API key middleware
   or OAuth before production deployment.

3. **Single-worker context window** — Chat history is appended indefinitely. For very
   long conversations (100+ turns), the history will eventually exceed the model's
   8,192-token context window. Implement history truncation or summarisation for production.

4. **Unanswered-question detection is heuristic** — The "2 unanswered questions →
   escalate" rule depends on the phrase "I don't have that information" appearing in the
   model's reply. A paraphrase of that phrase would not trigger the counter. A more robust
   implementation would use the escalation classifier with an `out_of_scope` signal.

5. **Thread-based concurrency** — `ThreadPoolExecutor` works for moderate traffic but
   will not scale to high concurrency. Migrate to `asyncio` + async Groq client for
   high-throughput deployments.

6. **No persistent lead storage** — Lead data collected in Stage 2 exists only in the
   in-memory session. Wire `lead_data` to your CRM via a webhook in `orchestrator.py`
   once the lead-qual sequence completes.

---

## Deployment Notes

### Docker (recommended for production)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

```bash
docker build -t closira-agent .
docker run -e GROQ_API_KEY=gsk_... -p 8000:8000 closira-agent
```

### Health Check for Load Balancers
```
GET /health → 200 OK { "status": "ok" }
```
Configure your ALB/Nginx upstream to probe this endpoint every 10 seconds.
