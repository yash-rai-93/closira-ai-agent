"""
cli.py
======
Command-line interface for locally simulating a conversation with the
Lumina Hair Studio AI agent WITHOUT running the FastAPI server.

The CLI calls the orchestrator and state modules directly — no HTTP layer —
making it ideal for rapid development, prompt tuning, and manual QA.

Usage
-----
    python cli.py

Controls
--------
  Type any message and press Enter to send.
  Type "quit" (case-insensitive) to manually end the session and trigger a summary.
  The session automatically ends (and summary is printed) when escalation fires.

Output
------
  Each turn prints:
    [STAGE: <current_stage>]  — so you can watch stage transitions live
    Agent: <reply>

  On escalation or quit:
    ❌ ESCALATED: <reason>   (if escalated)
    ─── SESSION SUMMARY ─────────────────
    <pretty-printed JSON>
"""

from __future__ import annotations

import json
import sys
import uuid
import os

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so `agent.*` imports resolve
# whether the CLI is launched from the repo root or elsewhere.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import orchestrator, state


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _print_banner() -> None:
    print("\n" + "═" * 60)
    print("  💇  Lumina Hair Studio — AI Receptionist (CLI Demo)")
    print("═" * 60)
    print("  Type your message and press Enter.")
    print("  Type 'quit' to end the session and view a summary.")
    print("─" * 60 + "\n")


def _print_summary(session_id: str) -> None:
    """Call the orchestrator summary function and pretty-print the result."""
    print("\n" + "─" * 60)
    print("  📋  SESSION SUMMARY")
    print("─" * 60)
    try:
        summary = orchestrator.generate_summary(session_id)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(f"[ERROR generating summary: {exc}]")
    print("─" * 60 + "\n")


# ---------------------------------------------------------------------------
# Main REPL loop
# ---------------------------------------------------------------------------

def run_cli() -> None:
    """
    Main entry point for the CLI.

    Initialises a unique session, then enters an interactive loop that:
      1. Accepts user input.
      2. Calls orchestrator.process_message().
      3. Prints the agent's reply and current stage.
      4. On escalation: prints the escalation reason, triggers summary, exits.
      5. On "quit": triggers summary, exits.
    """
    _print_banner()

    # Generate a fresh session_id for this CLI run
    session_id = f"cli-{uuid.uuid4().hex[:8]}"
    state.create_session(session_id)
    print(f"  Session ID: {session_id}\n")

    while True:
        # ── Get user input ────────────────────────────────────────────────
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            # Handle Ctrl-C / piped input end gracefully
            print("\n[Interrupted — generating summary before exit...]")
            _print_summary(session_id)
            sys.exit(0)

        if not user_input:
            continue  # Ignore blank lines

        # ── Quit command ──────────────────────────────────────────────────
        if user_input.lower() == "quit":
            print("\n[Session ended by user]")
            _print_summary(session_id)
            sys.exit(0)

        # ── Process message through agent pipeline ────────────────────────
        try:
            result = orchestrator.process_message(
                session_id=session_id,
                user_message=user_input,
            )
        except RuntimeError as exc:
            # Groq API failure (e.g. missing API key, network error)
            print(f"\n[API ERROR: {exc}]")
            print("Tip: ensure GROQ_API_KEY is exported in your shell.\n")
            continue
        except Exception as exc:
            print(f"\n[UNEXPECTED ERROR: {exc}]\n")
            continue

        # ── Print stage indicator and agent response ──────────────────────
        stage_label = result["current_stage"].upper().replace("_", " ")
        print(f"\n  [STAGE: {stage_label}]")
        print(f"Agent: {result['response']}\n")

        # ── Handle escalation ─────────────────────────────────────────────
        if result["is_escalated"]:
            reason = result.get("escalation_reason") or "Unknown trigger"
            print(f"❌  ESCALATED  —  {reason}")
            _print_summary(session_id)
            sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_cli()
