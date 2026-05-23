# Test Transcript 02 — Out-of-Scope Questions

**Scenario**: A customer asks questions that are NOT covered by the SOP (e.g. parking, product
brands, stylist bios). The agent must refuse to invent answers and use the exact "I don't have
that information" phrase. After two such questions, it should auto-escalate.

---

## Session Info
- **Session ID**: `test-oos-002`
- **Expected Stage**: `faq` → `escalation` (after 2nd unanswered question)
- **Expected Escalation**: Yes — `repeated_unanswered_questions`
- **SOP Coverage**: None — questions are not in `sop_data.json`

---

## Transcript

**User:** Do you have parking near the salon?

```json
{
  "response": "I'm sorry, I don't have that information available. Let me connect you with a member of our team who can help further.",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

> ℹ️ `unanswered_count` increments to 1. No escalation yet — SOP requires 2.

---

**User:** Which hair product brands do you use?

```json
{
  "response": "I'm sorry, I don't have that information available. Let me connect you with a member of our team who can help further.",
  "current_stage": "escalation",
  "is_escalated": true,
  "escalation_reason": "Customer asked 2 or more questions outside the scope of the SOP."
}
```

> ℹ️ `unanswered_count` reaches 2. Auto-escalation fires per SOP rule:
> `repeated_unanswered_questions`. Session is now locked.

**Agent (handoff message):**
> "I sincerely apologise for any inconvenience. I'm going to connect you directly with a member
> of our team who will be better placed to help you with this. Please hold on — someone will
> be with you shortly."

---

**User:** [Attempts to continue] What about gift vouchers?

```json
{
  "response": "This conversation has been handed off to our team. A human agent will be in touch shortly — please do not send further messages here.",
  "current_stage": "escalation",
  "is_escalated": true,
  "escalation_reason": "Customer asked 2 or more questions outside the scope of the SOP."
}
```

> ℹ️ Session is locked. All subsequent messages receive the static lock message.

---

## Auto-Generated Summary (POST /summary)

```json
{
  "customer_intent": "The customer was seeking operational information about the salon (parking, product brands) that is not covered in the SOP.",
  "key_details_collected": {
    "interested_service": null,
    "wants_consultation": null,
    "other_notes": "Customer asked about parking and product brands — both outside SOP scope."
  },
  "sop_gaps_identified": [
    "Parking availability near the salon",
    "Hair product brands used by the salon"
  ],
  "recommended_next_action": "A human agent should contact the customer to answer their operational questions and update the SOP to include parking and product information."
}
```

---

## Verification Checklist

- [x] First OOS question: correct refusal phrase, `is_escalated = false`
- [x] Second OOS question: auto-escalation fires, `is_escalated = true`
- [x] Escalation reason: `repeated_unanswered_questions`
- [x] Post-escalation message attempt: static lock response returned
- [x] Summary correctly identifies `sop_gaps_identified`
- [x] Agent never invented parking info or product brands
