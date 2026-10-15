import os
from openai import OpenAI

# Model is configurable so it can be upgraded without code changes.
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")

# Priorities that are held for a human to confirm before assignment.
REVIEW_PRIORITIES = ("P1", "P2")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

PROMPT_TEMPLATE = """You are an expert ITSM triage agent. Analyze this IT incident and respond ONLY in this exact format:

CATEGORY: [one of: Infrastructure, Access Management, Network, Collaboration Tools, Application Support, General IT]
PRIORITY: [one of: P1 - Critical, P2 - High, P3 - Medium, P4 - Low]
SLA: [one of: 1 hour, 4 hours, 8 hours, 24 hours]
ASSIGNMENT GROUP: [one of: Infrastructure Team, Security & IAM Team, Network Operations Team, End User Computing Team, Application Support Team, Service Desk]
REASON: [one sentence explaining why you chose this priority]

Incident Title: {title}
Incident Description: {description}"""


def ai_triage(title, description):
    """Send an incident to the LLM and return its raw triage text."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(title=title, description=description)}],
        max_completion_tokens=2000,
    )
    return response.choices[0].message.content


def parse_triage(text):
    """Turn the 'KEY: value' triage text into a dict."""
    fields = {}
    for line in (text or "").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip().upper()] = value.strip()
    return fields


def needs_review(fields):
    """High-priority incidents are routed to a human before assignment."""
    return fields.get("PRIORITY", "").upper().startswith(REVIEW_PRIORITIES)


def run_triage():
    print("\n========== AI-Powered ITSM Incident Triage Agent ==========")
    print(f"Model: {MODEL}")
    title = input("Enter incident title: ")
    description = input("Enter incident description: ")

    print("\nAnalyzing incident with AI...\n")
    result = ai_triage(title, description)

    print("--- AI Triage Result ---")
    print(result)
    if needs_review(parse_triage(result)):
        print("\nSTATUS: Pending human review (high priority)")
    else:
        print("\nSTATUS: Auto-assigned")
    print("============================================================\n")


if __name__ == "__main__":
    run_triage()
