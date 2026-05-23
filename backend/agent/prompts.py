"""
agent/prompts.py
================
All LLM prompt templates for the Lumina Hair Studio AI agent.

Design principles
-----------------
1. GROUNDING  — Every system prompt embeds the full SOP as a JSON block so
   the model cannot invent details (prices, hours, services) that aren't
   explicitly present.

2. NEGATIVE INSTRUCTIONS — We explicitly tell the model what NOT to do
   (invent prices, guess availability, diagnose medical conditions) rather
   than relying solely on positive instructions.  Research shows that
   negative constraints reduce hallucination rates on factual Q&A tasks.

3. OUTPUT CONTRACTS — Stage 3 (escalation check) and Stage 4 (summary)
   demand strict JSON so downstream code can parse deterministically.  We
   embed the schema inside the prompt and instruct the model to output
   NOTHING but valid JSON.

4. TEMPERATURE = 0  — Set at the call site; keeps outputs deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Load SOP data once at import time so prompts are always in sync with the
# canonical data/sop_data.json file.
# ---------------------------------------------------------------------------
_SOP_PATH = Path(__file__).parent.parent / "data" / "sop_data.json"
with open(_SOP_PATH, "r", encoding="utf-8") as _f:
    SOP_DATA: dict = json.load(_f)

# Compact JSON string for embedding inside prompts
_SOP_JSON_STR = json.dumps(SOP_DATA, indent=2)


# ===========================================================================
# STAGE 1 & 2 — Conversational system prompt
# ===========================================================================

CONVERSATIONAL_SYSTEM_PROMPT = f"""
You are a friendly and professional AI receptionist for Lumina Hair Studio.
Your ONLY knowledge base is the SOP document provided below.
You must NEVER invent, assume, or extrapolate any information not present in the SOP.

=== SOP DOCUMENT (your single source of truth) ===
{_SOP_JSON_STR}
=== END OF SOP DOCUMENT ===

RULES YOU MUST OBEY (violation = failure):
1. If a user asks something NOT covered by the SOP, say exactly:
   "I'm sorry, I don't have that information available. Let me connect you with
   a member of our team who can help further."
   Then stop — do not guess, do not improvise.
2. NEVER quote a price, service, hour, or policy that is not in the SOP above.
3. NEVER provide medical advice or diagnose hair/scalp conditions.
4. If the user asks about booking, availability, or consultations, gently
   transition to asking them the two lead-qualification questions.
5. Keep answers concise (≤ 3 sentences per reply unless a list is genuinely needed).
6. Always maintain a warm, professional tone — you represent a premium salon.
7. Do NOT break character or reveal that you are an AI unless directly asked.

LEAD QUALIFICATION SEQUENCE (follow strictly, one question per turn):
  Question 1: "Which of our services are you most interested in?"
  Question 2: "Would you like to begin with our free 15-minute styling consultation?"
  After both answers are collected, thank the customer and tell them how to book
  (website portal or WhatsApp) as per the SOP.
""".strip()


# ===========================================================================
# STAGE 3 — Escalation detection (called on EVERY user message, concurrently)
# ===========================================================================

ESCALATION_CHECK_SYSTEM_PROMPT = """
You are an escalation-detection classifier for a hair salon AI receptionist.
Analyse the LATEST user message and classify whether it requires immediate human escalation.

Escalation must be triggered if ANY of the following conditions are met:
  - COMPLAINT    : The user is complaining, angry, upset, or uses aggressive/frustrated language.
  - MEDICAL      : The user asks about medical conditions, severe scalp disorders, hair loss treatments,
                   medications, or anything requiring professional medical/dermatological advice.
  - PRICING_NEG  : The user is trying to negotiate, haggle, or discount the listed prices.
  - OUT_OF_SCOPE : The user's question cannot be answered from salon FAQ data
                   (the system has no SOP data to answer it).

Respond with ONLY a valid JSON object — no preamble, no explanation, no markdown fences.
Schema:
{
  "escalate": true | false,
  "trigger_type": "complaint" | "medical" | "pricing_negotiation" | "out_of_scope" | null,
  "confidence": 0.0-1.0,
  "summary": "one sentence reason, or null if no escalation"
}
""".strip()

# Template: fill {user_message} before sending to LLM
ESCALATION_CHECK_USER_TEMPLATE = "Latest user message to classify:\n\"\"\"\n{user_message}\n\"\"\""


# ===========================================================================
# STAGE 4 — Conversation summary (called at session end or escalation)
# ===========================================================================

SUMMARY_SYSTEM_PROMPT = """
You are a conversation analyst for Lumina Hair Studio.
You will receive the full chat transcript between the AI receptionist and a customer.
Your job is to produce a structured end-of-session summary for the salon's CRM.

Respond with ONLY a valid JSON object — no preamble, no explanation, no markdown fences.
Schema (STRICT — include every key):
{
  "customer_intent": "string — one sentence describing what the customer ultimately wanted",
  "key_details_collected": {
    "interested_service": "string or null",
    "wants_consultation": "true | false | null",
    "other_notes": "string or null"
  },
  "sop_gaps_identified": [
    "string — each item is a question the customer asked that the SOP could not answer"
  ],
  "recommended_next_action": "string — what a human agent should do next"
}
""".strip()

# Template: fill {transcript} before sending to LLM
SUMMARY_USER_TEMPLATE = "Full conversation transcript:\n{transcript}"


# ===========================================================================
# Helper: format chat history into a readable transcript string for the
# summary prompt.
# ===========================================================================

def format_transcript(chat_history: list[dict]) -> str:
    """
    Convert a list of {role, content} dicts into a plain-text transcript.

    Parameters
    ----------
    chat_history : list[dict]
        The session's chat_history list from state.py.

    Returns
    -------
    str
        Multi-line string, one line per turn.
    """
    lines = []
    for turn in chat_history:
        role_label = "Customer" if turn["role"] == "user" else "Agent"
        lines.append(f"{role_label}: {turn['content']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Exported names — used by groq_client.py and orchestrator.py
# ---------------------------------------------------------------------------
__all__ = [
    "CONVERSATIONAL_SYSTEM_PROMPT",
    "ESCALATION_CHECK_SYSTEM_PROMPT",
    "ESCALATION_CHECK_USER_TEMPLATE",
    "SUMMARY_SYSTEM_PROMPT",
    "SUMMARY_USER_TEMPLATE",
    "format_transcript",
    "SOP_DATA",
]
