from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime
from src.schemas import InboundMessage, TriageDecision
from src.prompts import SYSTEM_PROMPT

from dotenv import load_dotenv

load_dotenv()

def format_message(message: InboundMessage) -> str:
    """Format an InboundMessage as plain text for the model."""
    dt = datetime.fromisoformat(message.received_at)
    day_name = dt.strftime("%A")  
    time_str = dt.strftime("%H:%M")

    is_weekend = dt.weekday() >= 5
    is_late = dt.hour < 7 or dt.hour >= 18
    out_of_hours = is_weekend or is_late 
    
    parts = [
        f"Message ID: {message.id}",
        f"Channel: {message.channel}",
        f"Received at: {message.received_at} ({day_name} {time_str} Sydney time)",
        f"Out-of-hours: {'YES — apply SOP Section 7' if out_of_hours else 'No (within business hours)'}",
        f"Sender name: {message.sender_name}",
        f"Sender address: {message.sender_address}",
    ]
    if message.subject:
        parts.append(f"Subject: {message.subject}")
    parts.append(f"\nBody:\n{message.body}")
    return "\n".join(parts)


model = ChatAnthropic(model="claude-sonnet-4-5")
chain = model.with_structured_output(TriageDecision, include_raw=True)

def triage(message: InboundMessage) -> TriageDecision:
    result = chain.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=format_message(message)),
    ])
    return result["parsed"]


if __name__ == "__main__":
    # test_message = InboundMessage(
    #     id="MSG-001",
    #     channel="email",
    #     received_at="2024-06-14T19:00:00+10:00",
    #     sender_name="Sarah Patel",
    #     sender_address="spatel.home@gmail.com",
    #     subject="Dripping tap in ensuite",
    #     body="Hi there, the cold tap in our upstairs ensuite has been dripping for about a week and it's getting worse. Nothing dramatic, just annoying and probably wasting water. Can you book someone to come and have a look? We're in Mosman. Thanks, Sarah",
    # )
    test_message = InboundMessage(
        id="MSG-004",
        channel="email",
        received_at="2024-06-12T14:33:00+10:00",
        sender_name="Daniel O'Brien",
        sender_address="dan.obrien1978@bigpond.com",
        subject="Unhappy with last week's job — invoice INV-44821",
        body="I had an electrician out last Tuesday to install three power points in our home office. The work itself was fine, but the invoice came through at $720 — which is more than the $570 your sales team quoted me on the phone. Nobody mentioned an upper-floor surcharge until the invoice landed. I'd like this resolved. I'm not paying the extra $150 unless someone can explain it properly. Frankly I'm considering leaving a review about this if it isn't sorted.",
    )

    parsed = triage(test_message)
    print(parsed.model_dump_json(indent=2))
