# prompt_design.md
# Prompt Engineering Design Document — Lumina Hair Studio AI Agent

---

## 1. Overview

This document explains the rationale behind every prompt design decision in `agent/prompts.py`.
It covers hallucination prevention, stage transition logic, escalation classifier design, and
the structured output contracts used in Stages 3 and 4.

---

## 2. Core Philosophy: Grounding Over Generation

### The Problem
LLMs are creative by default. Left unconstrained, a model asked "What are your prices?"
will confidently invent plausible-sounding but completely fabricated prices. For a customer-facing
salon chatbot, a single hallucinated price causes real financial and reputational harm.

### The Solution: Document Grounding with Negative Constraints

Every conversational system prompt embeds the **full SOP JSON** directly in the prompt body:

```
=== SOP DOCUMENT (your single source of truth) ===
{ ...full JSON... }
=== END OF SOP DOCUMENT ===
```

This approach — sometimes called **in-context RAG** or **document grounding** — forces the model
to treat the embedded JSON as the authoritative knowledge base. Crucially, we pair positive
instructions ("answer from the SOP") with **explicit negative constraints**:

```
RULES YOU MUST OBEY (violation = failure):
1. If a user asks something NOT covered by the SOP, say exactly:
   "I'm sorry, I don't have that information available..."
2. NEVER quote a price, service, hour, or policy that is not in the SOP above.
3. NEVER provide medical advice or diagnose hair/scalp conditions.
```

Research in prompt engineering consistently shows that negative instructions ("never do X")
reduce hallucination rates more reliably than purely positive instructions ("only do Y").

---

## 3. Stage 1 — FAQ Answering

### Design Goals
- Accurate, concise answers strictly from the SOP.
- Warm, professional salon tone (not robotic).
- Length bounded to 3 sentences to avoid verbosity.

### Key Prompt Decisions

**Length cap**: `Keep answers concise (≤ 3 sentences per reply unless a list is genuinely needed)`
— prevents the model from padding with invented context.

**Role consistency**: `Do NOT break character or reveal that you are an AI unless directly asked`
— maintains the customer experience without being deceptive (we answer truthfully if directly asked).

**Temperature = 0.3**: Low but not zero. Zero temperature on a conversational task produces robotic,
repetitive phrasing. 0.3 gives natural variation while keeping factual claims stable.

---

## 4. Stage 2 — Lead Qualification

### Design Goals
- Ask exactly 2 scripted questions, one per turn.
- Store the user's raw answers without LLM interpretation (no extraction hallucination).
- Transition back to FAQ naturally once both answers are collected.

### Implementation: Scripted State Machine, Not LLM-Driven

Lead qualification does **not** use an LLM prompt for question generation. Instead,
`orchestrator.py` implements a deterministic state machine (`lead_question_idx` counter)
that serves pre-written questions from the `_LEAD_QUESTIONS` list.

**Why not use the LLM?**
Using the LLM to "decide what to ask next" introduces non-determinism — it might skip a question,
rephrase it incorrectly, or invent a third question. For a structured lead-capture flow, a
deterministic state machine is strictly more reliable.

The LLM IS still running concurrently (for the escalation check) and is used as a fallback
once the lead-qual sequence is complete.

### Lead Data Storage
User answers are stored verbatim in `session["lead_data"]`. This is intentional:
- No LLM interpretation → no hallucination of lead details.
- The summary stage (Stage 4) does the interpretation from the full transcript.

---

## 5. Stage 3 — Escalation Detection

### Design Goals
- Run concurrently with the conversational reply to avoid latency penalty.
- Classify 4 distinct trigger types: complaint, medical, pricing_negotiation, out_of_scope.
- Emit a structured JSON result with a confidence score for auditability.
- Default to **no escalation** on classifier failure (fail-open for UX; fail-secure would
  lock legitimate users out of support).

### Prompt Design

The escalation prompt is intentionally **separate** from the conversational system prompt.
This separation provides:
1. **Focused context** — the classifier sees only the trigger taxonomy, not the full SOP.
2. **Faster inference** — shorter prompt = lower latency = the concurrent check finishes sooner.
3. **Independent tuning** — we can update trigger definitions without touching FAQ prompts.

```
Escalation must be triggered if ANY of the following conditions are met:
  - COMPLAINT    : angry, upset, aggressive/frustrated language
  - MEDICAL      : scalp disorders, hair loss, medications, dermatological advice
  - PRICING_NEG  : negotiating, haggling, discounting
  - OUT_OF_SCOPE : question cannot be answered from salon FAQ data
```

### Temperature = 0.0
Classification is a deterministic task. We want the same message to always produce the same
escalation decision. Temperature 0 maximises this reproducibility.

### JSON Mode (`response_format={"type": "json_object"}`)
Groq's JSON mode constrains the model's token sampling to produce valid JSON, dramatically
reducing parse failures compared to asking for JSON in free-text mode.

### Confidence Score
The `confidence` field (0.0–1.0) is not currently used for routing but is stored for:
- Audit logs and model performance tracking.
- Future threshold-based soft-escalation (e.g., confidence > 0.7 required to trigger).

### Repeated Unanswered Questions — Hybrid Heuristic
The SOP specifies auto-escalation after "2 or more unanswered questions". We implement this
as a **hybrid heuristic** in the orchestrator rather than purely as an LLM classification:

1. When the conversational LLM includes our specific "I don't have that information" phrase,
   we increment `session["unanswered_count"]`.
2. At count ≥ 2, we escalate with a specific reason string.

This is more reliable than asking the escalation classifier to count across turns, because
the classifier only sees the latest message.

---

## 6. Stage 4 — Conversation Summary

### Design Goals
- Produce a machine-parseable JSON object suitable for CRM ingestion.
- Extract customer intent, collected lead data, SOP gaps, and next action.
- Be idempotent — calling the summary endpoint twice produces consistent results.

### Prompt Design

The summary prompt receives the **full conversation transcript** formatted as:
```
Customer: <message>
Agent: <message>
...
```

It demands a strict JSON schema with four keys. The schema is embedded directly in the
system prompt — not just described, but shown as a literal JSON template with type annotations.
This significantly improves schema adherence compared to describing the schema in prose.

### Temperature = 0.0
Summary generation is a fact-extraction task, not a creative task. We want the model to
report what actually happened in the transcript, not embellish or hypothesise.

---

## 7. Failure Modes and Mitigations

| Failure Mode | Mitigation |
|---|---|
| Model invents a service price | SOP JSON embedded in prompt; negative constraint rule #2 |
| Model gives medical advice | Explicit negative constraint rule #3; medical trigger in escalation classifier |
| JSON output parse failure | Markdown fence stripping + `json.loads` fallback; `response_format=json_object` |
| Groq API timeout/rate-limit | `MAX_RETRIES=3` with exponential back-off in `groq_client.py` |
| Escalation classifier fails | Defaults to `escalate=False` (fail-open) with error logged |
| User bypasses lead-qual | State machine is deterministic — user input cannot skip `lead_question_idx` |
| Concurrent write corruption | `_STORE_LOCK` threading.Lock in `state.py` |

---

## 8. Future Improvements

1. **Vector-based SOP retrieval** — When the SOP grows beyond ~2,000 tokens, embedding-based
   retrieval (RAG) will be more efficient than full-document injection.

2. **Streaming responses** — Groq supports SSE streaming; adding it to the `/chat` endpoint
   would reduce perceived latency for long replies.

3. **Fine-tuned escalation model** — Replace the zero-shot classifier with a small fine-tuned
   classifier trained on labelled salon support transcripts for higher precision.

4. **Persistent session store** — Replace the in-memory dict with Redis for multi-worker
   deployments and session persistence across server restarts.

5. **Confidence threshold routing** — Use the escalation `confidence` score to implement
   a "soft escalation" lane that warns rather than immediately locking the session.
