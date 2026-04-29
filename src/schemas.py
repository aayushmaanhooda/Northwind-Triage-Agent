"""
Pydantic schemas for the Northwind triage agent.

Defines:
- InboundMessage: input shape (one customer message)
- TriageDecision: output shape (the agent's structured decision)
- Supporting enums and reasoning sub-structure
"""

from typing import Literal
from pydantic import BaseModel, Field

# --- Enums (strict literals — model cannot deviate) ---
Category = Literal[
    "BOOKING",
    "QUOTE",
    "COMPLAINT",
    "EMERGENCY",
    "BILLING",
    "OUT_OF_SCOPE",
]
Priority = Literal["P1", "P2", "P3"]
Team = Literal["Dispatch", "Sales", "Accounts", "Customer Care"]
Channel = Literal["email", "sms", "webform"]


# --- Input: one inbound customer message ---
class InboundMessage(BaseModel):
    """One customer enquiry, as received by Northwind."""

    id: str = Field(description="Message ID, e.g. 'MSG-001'.")
    channel: Channel = Field(description="How the message arrived.")
    received_at: str = Field(description="ISO-8601 timestamp with timezone.")
    sender_name: str = Field(description="Display name of the sender.")
    sender_address: str = Field(
        description="Email address or phone number of the sender."
    )
    subject: str | None = Field(
        default=None,
        description="Email subject line. None for SMS.",
    )
    body: str = Field(description="The actual message content.")


# --- Reasoning sub-structure: separates rule-following from judgement ---
class Reasoning(BaseModel):
    """
    Structured reasoning for a triage decision.

    Separates deterministic rule-application (SOP/catalogue lookups) from
    judgement calls (where rules conflict, are ambiguous, or run out).
    Designed so a human reviewer can audit the agent's logic at a glance.
    """

    rules_applied: list[str] = Field(
        description=(
            "Specific SOP or catalogue rules the agent applied. "
            "Each item should reference the rule briefly, e.g. "
            "'SOP §3: no hot water in winter is P1 EMERGENCY' or "
            "'Catalogue: gutter cleaning explicitly excluded'."
        )
    )
    judgement_calls: list[str] = Field(
        default_factory=list,
        description=(
            "Where the agent had to make a judgement call because rules "
            "didn't fully resolve the case. Empty list if pure rule-application. "
            "Each item should explain the ambiguity and the call made, e.g. "
            "'Strata block: catalogue says <200m² per premises — each unit "
            "qualifies but aggregate exceeds. Going QUOTE + flag.'"
        ),
    )
    summary: str = Field(
        description=(
            "1-3 sentence plain-English summary of why these decisions were "
            "made. This is what a human triager would write in their notes."
        )
    )


# --- Output: the triage decision ---
class TriageDecision(BaseModel):
    """
    Structured triage decision for inbound messages.
    Produced by the agent.
    """

    category: Category = Field(
        description="The single category that best fits the message."
    )
    priority: Priority = Field(
        description=(
            "P1 (same-day), P2 (within 48h / 4 business hours), "
            "P3 (within 5 business days / 1 business day)."
        )
    )
    route_to: list[Team] = Field(
        description=(
            "Which team(s) handle this. Usually one team. Multiple teams "
            "only when the SOP requires it (e.g. billing dispute >$500 "
            "routes to both Customer Care and Accounts)."
        ),
        min_length=1,
    )
    draft_reply: str = Field(
        description=(
            "Customer-facing first-response reply. 2-4 sentences, "
            "tone-guide compliant. For garbled or spam messages, a brief "
            "placeholder is acceptable."
        )
    )
    needs_human_review: bool = Field(
        description=(
            "True if the case requires human review per SOP §6 "
            "(angry customer, large quote/refund, non-English, garbled, "
            "borderline scope, etc.)."
        )
    )
    reasoning: Reasoning = Field(
        description=(
            "Structured reasoning separating rule-application from judgement."
        )
    )



# EVALUTOR SCHEMAS
class MustIncludeCheck(BaseModel):
    item: str
    covered: Literal["yes", "partial", "no"]
    evidence: str

class MustNotIncludeCheck(BaseModel):
    item: str
    violated: Literal["yes", "no"]
    evidence: str

class JudgeVerdict(BaseModel):
    must_include_checks: list[MustIncludeCheck] = Field(default_factory=list)
    must_not_include_checks: list[MustNotIncludeCheck] = Field(default_factory=list)
    tone: Literal["matches", "drifts", "off"] = "off"
    tone_notes: str = "Judge response omitted tone assessment."
    reasoning_assessment: Literal["sound", "shaky", "bluffing"] = "shaky"
    reasoning_notes: str = "Judge response omitted reasoning assessment."
    overall_verdict: str = "Judge response was incomplete; review the raw case manually."
