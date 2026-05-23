"""
agent/orchestrator.py
=====================
The central routing brain of the Lumina Hair Studio AI agent.

This module implements the four-stage pipeline described in the SOP:

  Stage 1 — FAQ Answering       (default stage)
  Stage 2 — Lead Qualification  (triggered by booking/consultation intent)
  Stage 3 — Escalation Check    (runs CONCURRENTLY on every user message)
  Stage 4 — Summary Generation  (triggered at session end or escalation)

Concurrency model
-----------------
Stages 1/2 and Stage 3 run concurrently via ThreadPoolExecutor so the
escalation check never adds latency to the conversational response path.
The escalation check result is applied BEFORE the user sees the reply —
if escalation fires, the handoff message replaces the conversational reply.

Routing rules
-------------
FAQ → Lead       : User message contains booking / availability / consultation intent.
Lead → FAQ       : Once both lead-qual questions are answered (auto-transitions back).
Any → Escalation : Concurrent Stage 3 check fires.
Escalation       : Session is locked; only the handoff message is returned.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from agent import groq_client, state
from agent.prompts import (
    CONVERSATIONAL_SYSTEM_PROMPT,
    ESCALATION_CHECK_SYSTEM_PROMPT,
    ESCALATION_CHECK_USER_TEMPLATE,
    SUMMARY_SYSTEM_PROMPT,
    SUMMARY_USER_TEMPLATE,
    format_transcript,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Human handoff message — shown when escalation fires
# ---------------------------------------------------------------------------
ESCALATION_HANDOFF_MESSAGE = (
    "I sincerely apologise for any inconvenience. "
    "I'm going to connect you directly with a member of our team who will "
    "be better placed to help you with this. "
    "Please hold on — someone will be with you shortly."
)

# ---------------------------------------------------------------------------
# Booking-intent keywords that trigger Stage 2 transition
# ---------------------------------------------------------------------------
_BOOKING_KEYWORDS = {
    "book", "booking", "appointment", "schedule", "available",
    "availability", "consultation", "reserve", "slot", "when can",
}


def _contains_booking_intent(message: str) -> bool:
    """
    Simple keyword-scan to detect booking/availability intent.
    Intentionally conservative — false negatives are safer than false positives
    (we'd rather answer one more FAQ turn than interrupt a service question).
    """
    lower = message.lower()
    return any(kw in lower for kw in _BOOKING_KEYWORDS)


# ===========================================================================
# Stage 3 — Escalation check (isolated function for executor)
# ===========================================================================

def _run_escalation_check(user_message: str) -> dict:
    """
    Call the LLM classifier to decide whether this message requires escalation.
    Runs in a separate thread so it does not block the main response path.

    Returns a dict matching the escalation JSON schema defined in prompts.py.
    On any failure, returns a safe default (escalate=False) with a logged error.
    """
    try:
        prompt = ESCALATION_CHECK_USER_TEMPLATE.format(user_message=user_message)
        result = groq_client.json_completion(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=ESCALATION_CHECK_SYSTEM_PROMPT,
            temperature=0.0,  # Maximum determinism for a safety classifier
            max_tokens=256,
        )
        logger.debug("Escalation check result: %s", result)
        return result
    except Exception as exc:
        # Do NOT propagate — a failed safety check defaults to no-escalation
        # to preserve user experience, but we log loudly for monitoring.
        logger.error("Escalation check FAILED (defaulting to no-escalation): %s", exc)
        return {"escalate": False, "trigger_type": None, "confidence": 0.0, "summary": None}


# ===========================================================================
# Stage 2 — Lead Qualification helpers
# ===========================================================================

_LEAD_QUESTIONS = [
    "Which of our services are you most interested in? "
    "(We offer Standard Cut & Style from £45, Signature Textured Cuts from £75, "
    "Texture Perm / Body Wave from £120, or a free Initial Styling Consultation.)",

    "Wonderful! Would you like to begin with our free 15-minute styling consultation "
    "to discuss your goals and review any reference photos you have?",
]

_LEAD_FOLLOWTHROUGH_MESSAGE = (
    "Thank you for those details! To confirm your appointment, you can book through "
    "our website portal or send us a message via WhatsApp. "
    "We look forward to seeing you at Lumina Hair Studio! 💇"
)


def _handle_lead_qualification(session: dict, user_message: str) -> str:
    """
    Manage the two-question lead qualification sequence.

    State machine:
      lead_question_idx == 0  →  save service interest, ask Q2
      lead_question_idx == 1  →  save consultation preference, close out
      lead_question_idx >= 2  →  sequence complete, transition back to FAQ

    Extracts the user's raw message as the answer to each question
    (deliberately simple — no NLU extraction here; that's the LLM's job in
    the main chat flow; this layer just advances the state machine).
    """
    session_id = session["session_id"]
    idx = session["lead_question_idx"]

    if idx == 0:
        # User just answered Q1 — store service interest
        state.update_lead_data(session_id, "interested_service", user_message)
        # Advance pointer and ask Q2
        with state._STORE_LOCK:
            session["lead_question_idx"] = 1
        return _LEAD_QUESTIONS[1]

    elif idx == 1:
        # User just answered Q2 — store consultation preference
        state.update_lead_data(session_id, "wants_consultation", user_message)
        # Advance pointer past the sequence
        with state._STORE_LOCK:
            session["lead_question_idx"] = 2
        # Transition back to FAQ stage (session is warm now)
        state.set_stage(session_id, state.STAGE_FAQ)
        return _LEAD_FOLLOWTHROUGH_MESSAGE

    else:
        # Sequence already complete — fall through to FAQ answering
        state.set_stage(session_id, state.STAGE_FAQ)
        return ""  # Signal caller to use the main LLM path


# ===========================================================================
# Stage 1 / 2 — Main conversational LLM call
# ===========================================================================

def _run_conversational_reply(session: dict, user_message: str) -> str:
    """
    Generate a conversational reply using the full chat history.
    Used for both Stage 1 (FAQ) and as a fallback in Stage 2.
    """
    return groq_client.chat_completion(
        messages=session["chat_history"],
        system_prompt=CONVERSATIONAL_SYSTEM_PROMPT,
        temperature=0.3,
        max_tokens=512,
    )


# ===========================================================================
# Stage 4 — Summary generation
# ===========================================================================

def generate_summary(session_id: str) -> dict[str, Any]:
    """
    Generate a structured end-of-session summary.

    Called by:
      - POST /summary  (explicit API call)
      - CLI auto-trigger on escalation or "quit"

    Returns the parsed JSON summary object.
    Raises KeyError if the session does not exist.
    """
    session = state.get_session(session_id)
    if session is None:
        raise KeyError(f"Session '{session_id}' does not exist.")

    transcript = format_transcript(session["chat_history"])

    if not transcript.strip():
        # Edge case: empty session — return a sensible stub
        return {
            "customer_intent": "No conversation recorded.",
            "key_details_collected": {
                "interested_service": None,
                "wants_consultation": None,
                "other_notes": None,
            },
            "sop_gaps_identified": [],
            "recommended_next_action": "No action required.",
        }

    summary = groq_client.json_completion(
        messages=[{
            "role": "user",
            "content": SUMMARY_USER_TEMPLATE.format(transcript=transcript)
        }],
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=1024,
    )

    # Transition stage to "summary" for record-keeping
    state.set_stage(session_id, state.STAGE_SUMMARY)
    logger.info("Summary generated for session '%s'", session_id)
    return summary


# ===========================================================================
# Primary entry point — called by POST /chat
# ===========================================================================

def process_message(session_id: str, user_message: str) -> dict[str, Any]:
    """
    Process a single user message through the full agent pipeline.

    Pipeline order (per turn):
      1. Retrieve / create session.
      2. CONCURRENTLY: run escalation check & prepare conversational context.
      3. Apply escalation result first — if triggered, lock and return handoff.
      4. If not escalated, determine stage routing and generate reply.
      5. Persist assistant reply to history.
      6. Return structured response dict.

    Parameters
    ----------
    session_id   : str  Session identifier from the request.
    user_message : str  Raw user input text.

    Returns
    -------
    dict  Matching the POST /chat response schema:
        {
            "response"          : str,
            "current_stage"     : str,
            "is_escalated"      : bool,
            "escalation_reason" : str | None,
        }
    """
    # --- 1. Retrieve / create session ---
    session = state.get_or_create_session(session_id)

    # --- Guard: session already escalated (locked) ---
    if session["is_escalated"]:
        logger.info("Message received on locked session '%s' — rejecting.", session_id)
        return {
            "response": (
                "This conversation has been handed off to our team. "
                "A human agent will be in touch shortly — please do not send further messages here."
            ),
            "current_stage": state.STAGE_ESCALATION,
            "is_escalated": True,
            "escalation_reason": session["escalation_reason"],
        }

    # --- 2. Persist user message to history before LLM call ---
    state.append_message(session_id, "user", user_message)

    # --- 3. Concurrent execution: escalation check + (if needed) prep ---
    assistant_reply: str = ""
    escalation_result: dict = {}

    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit escalation check
        esc_future = executor.submit(_run_escalation_check, user_message)

        # Submit conversational reply concurrently
        # (We generate it speculatively; discard if escalation fires)
        conv_future = executor.submit(_run_conversational_reply, session, user_message)

        # Collect escalation result first (it's cheaper / faster)
        escalation_result = esc_future.result()

        # If NOT escalated, collect the conversational reply
        if not escalation_result.get("escalate", False):
            assistant_reply = conv_future.result()
        else:
            # Cancel is advisory in Python threads — the result is discarded
            conv_future.cancel()

    # --- 4a. Apply escalation if triggered ---
    if escalation_result.get("escalate", False):
        trigger = escalation_result.get("trigger_type", "unknown")
        reason_text = escalation_result.get("summary") or f"Triggered by: {trigger}"
        state.escalate_session(session_id, reason_text)
        logger.warning(
            "Session '%s' ESCALATED. Trigger: %s | Reason: %s",
            session_id, trigger, reason_text,
        )
        # Persist the handoff message to history for transcript completeness
        state.append_message(session_id, "assistant", ESCALATION_HANDOFF_MESSAGE)
        return {
            "response": ESCALATION_HANDOFF_MESSAGE,
            "current_stage": state.STAGE_ESCALATION,
            "is_escalated": True,
            "escalation_reason": reason_text,
        }

    # --- 4b. Stage routing for non-escalated messages ---
    current_stage = session["current_stage"]

    # ── Stage 2: Lead Qualification ──────────────────────────────────────────
    if current_stage == state.STAGE_LEAD:
        lead_reply = _handle_lead_qualification(session, user_message)
        if lead_reply:
            # Still in the lead-qual sequence — use the scripted question
            assistant_reply = lead_reply
        # else: sequence complete, assistant_reply already set from LLM call above

    # ── Stage 1 → 2 transition check ─────────────────────────────────────────
    elif current_stage == state.STAGE_FAQ and _contains_booking_intent(user_message):
        logger.info("Booking intent detected — transitioning session '%s' to LEAD stage.", session_id)
        state.set_stage(session_id, state.STAGE_LEAD)
        # Override the LLM reply with the first scripted lead-qual question
        assistant_reply = _LEAD_QUESTIONS[0]

    # ── Unanswered-question tracking (Stage 3 heuristic) ─────────────────────
    # If the LLM's own reply indicates it cannot answer (contains our "I don't have
    # that information" marker), increment the counter.
    if "i don't have that information" in assistant_reply.lower():
        count = state.increment_unanswered(session_id)
        logger.info("Unanswered count for session '%s': %d", session_id, count)
        if count >= 2:
            # Auto-escalate per SOP rule: repeated_unanswered_questions
            reason = "Customer asked 2 or more questions outside the scope of the SOP."
            state.escalate_session(session_id, reason)
            assistant_reply = ESCALATION_HANDOFF_MESSAGE
            state.append_message(session_id, "assistant", assistant_reply)
            return {
                "response": assistant_reply,
                "current_stage": state.STAGE_ESCALATION,
                "is_escalated": True,
                "escalation_reason": reason,
            }
    else:
        # Successfully answered — reset unanswered counter
        state.reset_unanswered(session_id)

    # --- 5. Persist assistant reply ---
    state.append_message(session_id, "assistant", assistant_reply)

    # --- 6. Return structured response ---
    return {
        "response": assistant_reply,
        "current_stage": session["current_stage"],
        "is_escalated": False,
        "escalation_reason": None,
    }
