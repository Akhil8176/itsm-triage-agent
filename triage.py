"""LLM incident triage with self-consistency confidence.

The model is asked the same question several times. If every answer agrees,
the triage is treated as confident. If the answers disagree, the incident is
routed to a human instead of being auto-assigned.
"""
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
SAMPLES = int(os.environ.get("TRIAGE_SAMPLES", "3"))

# Priorities that always go to a human, however confident the model is.
REVIEW_PRIORITIES = ("P1", "P2")

# Used when no ServiceNow instance is connected.
DEFAULT_TAXONOMY = {
    "CATEGORY": ["Inquiry / Help", "Software", "Hardware", "Network", "Database"],
    "PRIORITY": ["P1 - Critical", "P2 - High", "P3 - Moderate", "P4 - Low"],
    "ASSIGNMENT GROUP": ["Service Desk", "Network", "Hardware", "Software", "Database"],
}

# The fields whose agreement decides confidence.
DECISION_FIELDS = ("CATEGORY", "PRIORITY", "ASSIGNMENT GROUP")

_client = None


def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


def build_prompt(title, description, taxonomy):
    lines = [
        "You are an expert ITSM triage agent. Analyze this IT incident and respond ONLY in this exact format,",
        "choosing each value exactly as written from its list:",
        "",
    ]
    for field, options in taxonomy.items():
        lines.append(f"{field}: [one of: {', '.join(options)}]")
    lines.append("REASON: [one sentence explaining your choice of priority and group]")
    lines += ["", f"Incident Title: {title}", f"Incident Description: {description}"]
    return "\n".join(lines)


def ai_triage(title, description, taxonomy=DEFAULT_TAXONOMY):
    """One model call. Returns (raw_text, total_tokens)."""
    response = client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": build_prompt(title, description, taxonomy)}],
        max_completion_tokens=2000,
    )
    usage = getattr(response, "usage", None)
    return response.choices[0].message.content, getattr(usage, "total_tokens", 0) or 0


def parse_triage(text):
    """Turn 'KEY: value' lines into a dict."""
    fields = {}
    for line in (text or "").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip().upper()] = value.strip().strip("[]").strip()
    return fields


def _normalise(value, options):
    """Map a model answer onto the closest allowed option (case-insensitive)."""
    v = (value or "").strip().lower()
    for option in options:
        if v == option.lower():
            return option
    for option in options:
        if v and (v in option.lower() or option.lower() in v):
            return option
    return value or ""


def triage_with_confidence(title, description, taxonomy=DEFAULT_TAXONOMY, samples=None):
    """Ask the model `samples` times and vote.

    Returns a dict with the majority answer per field, the agreement score,
    whether it is confident, every raw sample, and tokens used.
    """
    samples = samples or SAMPLES
    with ThreadPoolExecutor(max_workers=samples) as pool:
        results = list(pool.map(lambda _: ai_triage(title, description, taxonomy), range(samples)))

    parsed = []
    for text, _ in results:
        f = parse_triage(text)
        for field, options in taxonomy.items():
            f[field] = _normalise(f.get(field), options)
        parsed.append(f)

    decision = {}
    agreement = {}
    for field in taxonomy:
        votes = Counter(p.get(field, "") for p in parsed)
        value, count = votes.most_common(1)[0]
        decision[field] = value
        agreement[field] = count / samples

    # Reason from a sample that matches the majority decision.
    for p in parsed:
        if all(p.get(f) == decision[f] for f in taxonomy):
            decision["REASON"] = p.get("REASON", "")
            break
    else:
        decision["REASON"] = parsed[0].get("REASON", "")

    decision_fields = [f for f in DECISION_FIELDS if f in taxonomy] or list(taxonomy)
    score = min(agreement[f] for f in decision_fields)
    return {
        "decision": decision,
        "agreement": agreement,
        "confidence": score,
        "confident": score == 1.0,
        "samples": [text for text, _ in results],
        "tokens": sum(t for _, t in results),
    }


def route(result):
    """Return (status, why) for a triage result."""
    priority = result["decision"].get("PRIORITY", "").upper()
    if priority.startswith(REVIEW_PRIORITIES):
        return "pending_review", "high priority"
    if not result["confident"]:
        return "pending_review", f"model disagreed with itself ({result['confidence']:.0%} agreement)"
    return "auto_assigned", "confident, low priority"


def format_result(result):
    d = result["decision"]
    lines = [f"{field}: {d.get(field, '')}" for field in d if field != "REASON"]
    lines.append(f"REASON: {d.get('REASON', '')}")
    lines.append(f"CONFIDENCE: {result['confidence']:.0%} agreement across {len(result['samples'])} samples")
    return "\n".join(lines)


def run_triage():
    print("\n========== AI-Powered ITSM Incident Triage Agent ==========")
    print(f"Model: {MODEL} | Samples per incident: {SAMPLES}")
    title = input("Enter incident title: ")
    description = input("Enter incident description: ")

    print("\nAnalyzing incident with AI...\n")
    result = triage_with_confidence(title, description)
    status, why = route(result)

    print("--- AI Triage Result ---")
    print(format_result(result))
    label = "Pending human review" if status == "pending_review" else "Auto-assigned"
    print(f"\nSTATUS: {label} ({why})")
    print("============================================================\n")


if __name__ == "__main__":
    run_triage()
