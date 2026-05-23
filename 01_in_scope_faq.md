# Test Transcript 01 — In-Scope FAQ Answering

**Scenario**: A customer asks several questions that are fully answerable from the SOP.
The agent should respond accurately, stay in Stage 1 (FAQ), and never invent details.

---

## Session Info
- **Session ID**: `test-faq-001`
- **Expected Stage Throughout**: `faq`
- **Expected Escalation**: None
- **SOP Coverage**: Full — all questions are addressed in `sop_data.json`

---

## Transcript

**User:** Hi, what kind of salon is Lumina Hair Studio?

```json
{
  "response": "Lumina Hair Studio is a modern hair salon specialising in contemporary aesthetics, high-volume styling, and custom textured cuts. We offer a range of services from standard cuts to signature textured styles and chemical treatments.",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

---

**User:** What are your opening hours?

```json
{
  "response": "We are open Monday to Saturday from 9:00 AM to 7:00 PM. We are closed on Sundays.",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

---

**User:** How much does a standard haircut cost?

```json
{
  "response": "Our Standard Cut & Style starts from £45, which includes a wash, cut, and blow-dry.",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

---

**User:** What is the Signature Textured Cut and how much does it cost?

```json
{
  "response": "Our Signature Textured Cuts — including the Wavy Shag and Soft Wolf Cut — start from £75. These specialty cuts focus on maximising volume and movement, tailored to your individual hair type.",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

---

**User:** Do you have a cancellation policy?

```json
{
  "response": "Yes — we require a minimum of 24 hours' notice for any cancellations. Please be aware that late cancellations may incur a fee.",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

---

**User:** How do I get in touch to book?

```json
{
  "response": "You can book an appointment through our website portal or by sending us a message via WhatsApp.",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

---

**User:** Is the consultation free?

```json
{
  "response": "Yes! Our Initial Styling Consultation is completely free — it's a 15-minute session where we discuss your hair goals, assess your hair type, and review any model reference photos you bring along.",
  "current_stage": "faq",
  "is_escalated": false,
  "escalation_reason": null
}
```

---

## Verification Checklist

- [x] All responses derived solely from `sop_data.json`
- [x] No invented prices, services, or contact details
- [x] Stage remained `faq` throughout — no incorrect transitions
- [x] `is_escalated` remained `false` throughout
- [x] Tone is warm and professional
- [x] Answers are concise (≤ 3 sentences each)
