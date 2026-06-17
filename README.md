# ITSM Incident Triage Agent

An AI-powered, fully autonomous ITSM agent that detects system issues, generates incidents, and triages them — without any human input. Built to demonstrate how LLM-based reasoning can fill a real gap in enterprise ITSM tooling.

## The Problem

ServiceNow's built-in AI (Predictive Intelligence) requires historical incident data to triage effectively. New ServiceNow implementations have zero historical tickets, so the AI doesn't work well on day one — it needs months of accumulated data first.

This project explores an alternative: using a pre-trained LLM that requires zero training data and works immediately, combined with zero human intervention — the agent detects problems on its own and triages them in real time.

## How It Works

The system has two layers:

1. Autonomous Detection (monitor.py)
Continuously watches real system health metrics (CPU, memory, disk) on the host machine. When a threshold is breached, it automatically generates an incident — no human files a ticket.

2. AI Triage (triage.py / shared logic)
Uses OpenAI's GPT-3.5-turbo to analyze the incident and reason through:
- Category (Infrastructure, Access Management, Network, Collaboration Tools, Application Support, General IT)
- Priority (P1–P4)
- SLA target
- Assignment group
- A plain-English reason for its decision

Every detected incident is logged to incidents_log.json for an auditable history.

## Why Real System Metrics, Not Simulated Logs

I considered using my ServiceNow PDI for incident data, but PDIs only contain sample/demo data, not real operational signals. Instead, I used my own machine's live CPU, memory, and disk metrics via Python's psutil library — real, changing data, not a script printing fake pretend logs. In production, this same architecture would point at a real server's metrics instead of a personal laptop.

## How To Run

Manual triage (human-reported incident):
python3 triage.py

Autonomous monitoring (zero human input):
export OPENAI_API_KEY="your-key-here"
python3 monitor.py

To trigger a live demo anomaly:
python3 stress.py

## Sample Autonomous Output

[15:30:23] CPU: 99.9% | Memory: 76.5% | Disk: 20.7%

ANOMALY DETECTED: High CPU usage detected: 99.9%
Auto-generating incident and triaging with AI...

--- AI Triage Result ---
CATEGORY: Infrastructure
PRIORITY: P1 - Critical
SLA: 1 hour
ASSIGNMENT GROUP: Infrastructure Team
REASON: High CPU usage at 99.9% indicates a critical system performance issue that requires immediate attention to prevent system failure or downtime.

Incident logged to incidents_log.json

## Tech Stack
- Python 3.12
- OpenAI GPT-3.5-turbo API
- psutil (system metrics)

## Architecture Note
API keys are loaded via environment variables, never hardcoded — matching standard secrets-management practice in production systems.

## Author
Akhil Yadati — ServiceNow Developer | ITSM Specialist