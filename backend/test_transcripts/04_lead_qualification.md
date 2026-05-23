# Test Transcript 04 — Lead Qualification Flow

**Scenario**: A customer expresses interest in booking. The agent detects booking intent,
transitions to Stage 2, asks exactly 2 scripted questions (one per turn), stores the answers
in `lead_data`, and then transitions back to FAQ with a booking call-to-action.

---

## Session Info
- **Session ID**: `test-lead-004`
- **Expected Stage Flow**: `faq` → `lead_qualification` → `faq`
- **Expected Escalation**: None
- **Lead Data Collected**: `interested_service`, `wants_consultation`

---

## Transcript

### Phase 1: FAQ Stage

**User:** Hello! I've been thinking about getting a textured cut. What kinds do you offer?

```json
{
  "response": "We offer Signature Textured Cuts starting from £75, which include styles like the Wavy Shag and Soft Wolf Cut. These specialty cuts focus on maximising volume and movement, tailored to your hair type. We also offer a free 15-minute Initial Styling Consultation to discuss your goals and review reference photos before your appointment.",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

> ℹ️ Stage: `faq`. Booking intent not yet detected. Normal FAQ response.

---

### Phase 2: Booking Intent Detected → Transition to Lead Qualification

**User:** That sounds great! I'd love to book an appointment or maybe a consultation.

```json
{
  "response": "Which of our services are you most interested in? (We offer Standard Cut & Style from £45, Signature Textured Cuts from £75, Texture Perm / Body Wave from £120, or a free Initial Styling Consultation.)",
  "current_stage": "lead_qualification",
  "is_escalated": false,
  "escalation_reason": null
}
```

> ✅ Keyword "book" + "consultation" detected → stage transitions to `lead_qualification`.
> Lead Question 1 is asked (`lead_question_idx` = 0).

---

### Phase 3: Lead Question 1 Answered → Lead Question 2 Asked

**User:** I'm most interested in the Signature Textured Cut — specifically the Wavy Shag.

```json
{
  "response": "Wonderful! Would you like to begin with our free 15-minute styling consultation to discuss your goals and review any reference photos you have?",
  "current_stage": "lead_qualification",
  "is_escalated": false,
  "escalation_reason": null
}
```

> ✅ Answer "Signature Textured Cut — specifically the Wavy Shag" saved to:
> `session.lead_data.interested_service`
> Lead Question 2 is now asked (`lead_question_idx` = 1).

---

### Phase 4: Lead Question 2 Answered → Sequence Complete → Return to FAQ

**User:** Yes, I'd definitely like to start with the free consultation first.

```json
{
  "response": "Thank you for those details! To confirm your appointment, you can book through our website portal or send us a message via WhatsApp. We look forward to seeing you at Lumina Hair Studio! 💇",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

> ✅ Answer "Yes, I'd definitely like to start with the free consultation first" saved to:
> `session.lead_data.wants_consultation`
> `lead_question_idx` advances to 2 (sequence complete).
> Stage transitions back to `faq`.
> Booking CTA delivered as per SOP (`how_to_book` field).

---

### Phase 5: Post-Lead FAQ (Session is Warm)

**User:** How do I actually get the WhatsApp number?

```json
{
  "response": "I'm sorry, I don't have that information available. Let me connect you with a member of our team who can help further.",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

> ℹ️ The SOP only states "WhatsApp" as a contact method but doesn't include a number.
> The agent correctly declines to invent a phone number.

---

## Session State After Conversation (GET /session/test-lead-004)

```json
{
  "session_id": "test-lead-004",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null,
  "lead_data": {
    "interested_service": "Signature Textured Cut — specifically the Wavy Shag",
    "wants_consultation": "Yes, I'd definitely like to start with the free consultation first."
  },
  "lead_question_idx": 2,
  "unanswered_count": 1
}
```

---

## Verification Checklist

- [x] Stage transitioned from `faq` → `lead_qualification` on booking intent keyword
- [x] Question 1 asked on first turn after transition (not answered + asked simultaneously)
- [x] Question 2 asked on second turn, after saving Q1 answer
- [x] Both answers stored verbatim in `lead_data`
- [x] Stage returned to `faq` after both answers collected
- [x] Booking CTA references SOP booking methods (portal + WhatsApp) exactly
- [x] No WhatsApp number invented when customer asked for it
- [x] `is_escalated` remained `false` throughout
