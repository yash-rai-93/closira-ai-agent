---
title: Closira AI Agent
emoji: 💇
colorFrom: purple
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Closira — Lumina Hair Studio Full-Stack AI Orchestrator

Closira is an asynchronous, multi-stage conversational AI customer communication platform engineered for small and medium businesses (SMBs). This repository houses a production-ready implementation configured for **Lumina Hair Studio** — a premium modern salon specializing in contemporary aesthetics, high-volume styling, and custom textured cuts (such as Wavy Shags and Soft Wolf Cuts).

The architecture features a high-performance **FastAPI asynchronous backend** powered by the **Groq Inference Engine** (leveraging `llama-3.3-70b-versatile`) coupled to a low-latency, responsive orchestration console styled natively on advanced dark-mode design specifications.

---

## 🚀 Key Features & Capabilities

* **Deterministic Stage Orchestration**: Moves fluidly between FAQ Q&A, structured multi-turn Lead Capture, and Automated Human Handoff without non-deterministic conversational drift.
* **Ultra-Low Latency Concurrency Model**: Processes conversational generation and Stage 3 escalation evaluation completely in parallel using Python thread-pooling mechanisms to avoid adding a latency penalty to the user.
* **Strict Grounding & Hallucination Prevention**: Embeds the canonical salon Standard Operating Procedure (SOP) directly into system prompt buffers with robust negative constraints, shutting down model fantasies regarding non-SOP prices or operating hours.
* **Automated Verification Engine**: Integrates a complete testing suite (`test_runner.py`) that executes end-to-end conversation trees across 5 diverse mock-transcript scenarios and asserts backend state machine transitions with total structural precision.
* **Hugging Face Spaces & Monorepo Dockerized Support**: Designed to stand up instantly within multi-stage isolated containers across local dev boxes, cloud native runtimes, or Hugging Face Spaces.

---

## 🛠️ System Architecture & Agent State-Machine

The agent tracks customer conversations statefully via a unique `session_id` mapping to an isolated in-memory transaction layer, executing state routing through 4 explicit stages:

```
[ Customer Inbound Input ]
│
▼
┌──────────────────────────────┐
│  STAGE 3: ESCALATION ENGINE  │ ──(Trigger Fired)──► [ Lock Session State ]
│ (Concurrent Classifier Thread)│                      [ Serve Handoff Message ]
└──────────────┬───────────────┘                                 │
│ (No Triggers)                                   ▼
▼                                       [ Generate CRM Summary ]
Current Stage State?
├── "faq" ──────────► [ Booking Intent Scan ]
│                           ├── (Detected) ──► Transition to "lead_qualification"
│                           └── (None) ──────► Run Grounded FAQ Prompt
▼
"lead_qualification" ────► [ Two-Question Scripted Pipeline ]
├── Question 1: Extract Interested Service
└── Question 2: Extract Consultation Opt-In
│
(Sequence Complete)
│
▼
Transition Back to "faq" Stage
```

### The 4 Operational Stages Explained

1. **Stage 1: FAQ Answering (Default)**: Leverages the tokenized `sop_data.json` source. If an inquiry sits outside this structure, the model intercepts with a standardized scope-refusal string and flags the turn for tracking.
2. **Stage 2: Lead Qualification**: Triggered automatically upon detecting booking, consultation, or availability intent. The engine drops conversational generation and processes a strict, pre-scripted 2-turn sequence to gather clear data payload points, resetting seamlessly to the FAQ layer upon closing out.
3. **Stage 3: Escalation Detection (Concurrent)**: Evaluates every single user message inside a parallel thread block. It screens for **Complaints/Anger, Medical/Scalp conditions, Pricing Haggle/Negotiation, or Scope Gaps**. If a trigger hits, it alters `is_escalated` to `true`, commits a specific audit log, renders a comforting human-handoff statement, and flags the session as locked.
4. **Stage 4: Conversation Summary**: Invoked at explicit session termination or on human-handoff interception. It maps the comprehensive dialogue string into a tightly formatted CRM JSON matrix extracting intent, captured service markers, logged gaps, and recommended actions.

---

## 📂 Repository Layout

```text
closira/
├── backend/                    # Core FastAPI Application Directory
│   ├── main.py                 # REST API Router, Pydantic schemas, and CORS mapping
│   ├── Dockerfile              # Multi-stage production runtime container configuration
│   ├── docker-compose.yml      # Local dev/prod container containerization orchestration
│   ├── requirements.txt        # Production dependency locks
│   ├── test_runner.py          # Automated verification engine and validation runtime
│   │
│   ├── agent/                  # AI Intelligence Layer Engine
│   │   ├── __init__.py         # Package initialization
│   │   ├── groq_client.py      # Resilient SDK wrapper implementing back-off retry lines
│   │   ├── orchestrator.py     # Central pipeline routing brain and concurrent executor
│   │   ├── prompts.py          # Rigidly engineered system prompt configurations
│   │   └── state.py            # Local thread-safe in-memory session manager
│   │
│   ├── data/                   # Grounding SOP Reference Layouts
│   │   └── sop_data.json       # Canonical Salon SOP (Single source of truth)
│   │
│   └── test_transcripts/       # Verified Assertion Transcript Profiles
│       ├── 01_in_scope_faq.md       # Valid In-SOP Q&A interaction verification
│       ├── 02_out_of_scope.md       # Threshold routing for out-of-scope gaps
│       ├── 03_escalation_trigger.md # Pure sentiment and safe taxonomy checks
│       ├── 04_lead_qualification.md # Two-turn registration pipeline validations
│       └── 05_conversation_summary.md # Complete end-to-end conversation trace
│
├── frontend/                   # UI Workstation Console Components
│   ├── index.html              # Core structural layout interface
│   ├── style.css               # Premium minimalist dark styling metrics
│   └── app.js                  # Async state sync and endpoint consumer hooks
│
├── prompt_design.md            # Thorough engineering rationale documentation
└── README.md                   # System configuration, startup, and contract guide
```

---

## ⚡ Quick Start (Docker Setup)

The quickest method to boot the complete ecosystem is utilizing the native Docker Compose profiles.

### 1. Configure the Environment

Clone your repository and initialize your secure local settings:

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and inject your Groq developer credentials:

```env
GROQ_API_KEY=gsk_your_actual_key_here
```

### 2. Run the Full Stack

Launch the multi-container configuration from your terminal:

```bash
docker compose -f backend/docker-compose.yml up --build
```

This single command builds and coordinates two interconnected isolated containers:

* **Frontend Application Console**: Live at `http://localhost:3000`
* **FastAPI Orchestration API Engine**: Live at `http://localhost:8000` with automated swagger interactive endpoints hosted at `http://localhost:8000/docs`.

---

## 🐍 Manual Installation (Local VirtualEnv)

If you prefer operating outside container virtualizations, configure your Python system space directly:

### 1. Build and Source Virtual Space

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Initialize Keys and Launch API

Ensure your terminal contains your secure credential token:

```bash
export GROQ_API_KEY="gsk_..."
uvicorn main:app --reload --port 8000
```

To run the static frontend UI alongside it, simply point any browser utility to the exposed port structure or navigate directly to `http://localhost:8000/` since the backend dynamically hosts the static root files.

---

## 🧪 Testing & Validation Suite

The system includes an advanced regression testing pipeline via `test_runner.py`. This verification component reads raw markdown conversation transcripts from `test_transcripts/`, breaks them into step-by-step turns, parses expected JSON behaviors, handles state assertions, and executes calls against live API components to guarantee model output safety.

### The 5 Golden Evaluation Scenarios Covered:

1. **`01_in_scope_faq.md`**: Asserts correct, precise extractions for operating schedules, starting costs, and styling options, confirming the session remains locked to the `faq` stage without straying.
2. **`02_out_of_scope.md`**: Validates structural scope tracking. Asserts the system yields the exact refusal quote on an unmapped inquiry (e.g., parking) and correctly steps the transaction into an auto-escalation human link on the exact 2nd consecutive gap strike.
3. **`03_escalation_trigger.md`**: Separates checks into distinct taxonomy testing paths (Sub-Scenario A: Complaints, Sub-Scenario B: Dermatological/Medical, Sub-Scenario C: Handoff and negotiation), forcing immediate session locking with detailed logic trails.
4. **`04_lead_qualification.md`**: Asserts state tracking over 4 sequential turns, assessing how user inputs map step-by-step into localized storage structures and check back to baseline FAQ loops with accurate booking calls-to-action.
5. **`05_conversation_summary.md`**: Chains all variations into a long multi-turn call path, executing a complete data payload audit and verifying semantic extraction properties of CRM-ready output blocks.

### Running the Tests

To initiate the full validation sweep and view colorized pass/fail reports, run:

```bash
python test_runner.py
```

---

## 📡 Core API Reference Contract

All communication routes run over asynchronous JSON contracts.

### 1. Chat Processing Endpoint (`POST /chat`)

Submits a line of text within an active session timeline.

* **Payload Request Model**:
```json
{
  "session_id": "client-uuid-string-here",
  "message": "I want to book an appointment for a soft wolf cut tomorrow."
}
```


* **Payload Response Model**:
```json
{
  "session_id": "client-uuid-string-here",
  "response": "Which of our services are you most interested in? (We offer Standard Cut & Style from £45, Signature Textured Cuts from £75...)",
  "current_stage": "lead_qualification",
  "is_escalated": false,
  "escalation_reason": null
}
```



### 2. CRM Analytics Generator (`POST /summary`)

Extracts conversation details into structured data attributes.

* **Payload Request Model**:
```json
{ "session_id": "client-uuid-string-here" }
```


* **Payload Response Model**:
```json
{
  "customer_intent": "Customer wants to book a Signature Textured Cut (Soft Wolf Cut) and start with a free consultation.",
  "key_details_collected": {
    "interested_service": "Signature Textured Cut — Soft Wolf Cut",
    "wants_consultation": "Yes, please.",
    "other_notes": "Customer asked about eyebrow tinting which is not supported in the current SOP."
  },
  "sop_gaps_identified": [
    "Eyebrow tinting service availability"
  ],
  "recommended_next_action": "Reach out via WhatsApp to finalize scheduling for the free 15-minute Initial Styling Consultation and update SOP metadata regarding beauty extensions."
}
```



---

## ⚖️ Engineering Trade-offs & Limitations

* **State Persistence Architecture**: To maintain performance within tight development intervals, the engine runs a thread-safe, localized module dictionary cache (`SESSION_STORE`). Because memory buffers are tied to the active worker layer, scaling up multiple server threads or scaling out via horizontal container groups will decouple session lookups. Production setups should replace `state.py` methods with an external caching instance like Redis.
* **Scripted Lead Pipeline Routing**: Lead validation questions rely on hardcoded script arrays managed inside state machines rather than dynamic LLM inference paths. While this eliminates structural hallucinations during information capture, it reduces linguistic flexibility if a customer attempts to answer multiple qualification parameters inside a single message string.
* **Grounded Text Scoping Constraints**: The keyword detection matrix (`_contains_booking_intent`) balances false matches conservatively. If a customer queries policies (e.g., pricing or cancellations), the script purposefully prevents switching into phase 2 registration paths unless an operational scheduling verb is explicitly present.
