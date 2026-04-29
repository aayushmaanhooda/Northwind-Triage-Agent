# Inbound Enquiry Triage — Standard Operating Procedure

Northwind Home Services Pty Ltd • Document v3.2 • Last updated: March 2024 • Owner: Operations

## 1. Purpose

This document describes how the Operations team handles inbound customer enquiries received via email, web form, or shared inbox. It is the source of truth for routing, prioritisation, and first-response drafting. All new starters in the dispatch team must follow this SOP.

## 2. Categories

Every inbound message must be classified into exactly one of the following:

| Code | Use when… |
|---|---|
| **BOOKING** | Customer wants to schedule a service they have already agreed to, or is asking about availability for a known service. |
| **QUOTE** | Customer is asking for a price, estimate, or 'how much would it cost' for work not yet agreed. |
| **COMPLAINT** | Customer is unhappy with completed work, a tradesperson's conduct, billing accuracy, or any aspect of service delivery. |
| **EMERGENCY** | Customer has an active risk to property or safety: water leak in progress, no hot water in winter, electrical sparking, gas smell, etc. |
| **BILLING** | Customer is asking about an invoice, payment, refund, or account statement. |
| **OUT_OF_SCOPE** | The request is for something we don't offer, or is not actionable (spam, wrong number, etc.). |

### Notes on classification:

- If a message contains both a complaint and a new request, classify as **COMPLAINT** and note the secondary request in the reasoning.
- A request to *reschedule* an existing booking is a **BOOKING**, not a complaint, unless the customer explicitly expresses dissatisfaction.
- If unsure between QUOTE and BOOKING, default to QUOTE — it's safer to confirm scope before dispatching a tradesperson.

## 3. Priority levels

| Priority | Definition | First response SLA |
|---|---|---|
| **P1** | Active safety or property risk. Customer needs same-day attention. | Within 1 hour, 24/7 |
| **P2** | Loss of essential function (heating, hot water, working toilet) but no immediate damage. Or any complaint involving a charge over $1,000. | Within 4 business hours |
| **P3** | Standard enquiry, quote request, or non-urgent booking. | Within 1 business day |

EMERGENCY messages are always P1. Do not downgrade them, even if the customer's tone is calm.

## 4. Routing

Northwind has four operational teams. Route based on category and trade:

| Team | Handles |
|---|---|
| **Dispatch** | All BOOKING and EMERGENCY messages. They allocate the right tradesperson and call the customer back. |
| **Sales** | All QUOTE messages. They send written estimates and follow up. |
| **Accounts** | All BILLING messages. They handle invoices, payments, and refunds. |
| **Customer Care** | All COMPLAINT messages. They are also the fallback for anything that doesn't fit cleanly elsewhere. |

### Special routing rules:

- OUT_OF_SCOPE messages route to Customer Care, who send a polite decline.
- If a COMPLAINT involves a billing dispute over $500, it goes to Accounts and Customer Care (cc both).
- Emergency plumbing and emergency electrical both go to Dispatch — we have on-call tradies for both.
- We do not have on-call HVAC. After-hours HVAC issues are P2 and route to Dispatch for next-business-day allocation.

## 5. First-response drafting

Every inbound message gets a first response drafted at triage time, even if a human will edit it before sending. The draft must:

- Acknowledge the customer's specific situation in the first sentence.
- State what happens next and roughly when (use the SLA, don't promise a specific time).
- Match the tone defined in the Tone & Style Guide.
- Never quote a price unless the catalogue lists a fixed price for that exact service.
- Never commit to a specific tradesperson by name.

## 6. When to flag for human review

Mark `needs_human_review = true` if any of the following apply:

- The customer is angry, distressed, or threatens legal action / online review.
- The request involves a quote over $5,000 or a refund over $500.
- The message is in a language other than English, or appears garbled.
- You cannot confidently classify the message after re-reading it.
- The customer mentions a previous complaint or escalation.
- The request is for a service that is borderline outside our catalogue.

Flagging is cheap. Missing an escalation is expensive. When in doubt, flag.

## 7. Out-of-hours handling

Outside 7:00–18:00 weekdays, only P1 EMERGENCY messages are actioned live. P2 and P3 are queued for the next business morning. The first-response draft for queued messages should acknowledge the wait time ("we'll be in touch first thing tomorrow") rather than promising same-day action.