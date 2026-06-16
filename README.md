# ITSM Incident Triage Agent

An AI-powered command-line tool that automatically classifies IT incidents by priority, category, and assignment group — mimicking real-world ServiceNow ITSM triage logic.

## Problem It Solves

In enterprise IT, incidents are manually triaged by service desk agents — a slow, inconsistent process. This tool automates that classification instantly based on incident title and description.

## How It Works

1. User inputs an incident title and description
2. The engine scans for keywords across 5 categories
3. Priority is assigned based on business impact signals
4. The correct assignment group is determined automatically

## Classification Logic

| Category | Examples |
|---|---|
| Infrastructure | Server down, database crash, disk full |
| Access Management | Login failure, locked account, permissions |
| Network | VPN issues, WiFi down, connectivity loss |
| Collaboration Tools | Outlook, Teams, calendar issues |
| Application Support | App crash, software install, errors |

## Priority Matrix

| Priority | Trigger Keywords | SLA |
|---|---|---|
| P1 - Critical | outage, down, production, all users | 1 hour |
| P2 - High | slow, degraded, some users | 4 hours |
| P3 - Medium | single user, my, I cannot | 8 hours |
| P4 - Low | everything else | 24 hours |

## How To Run

python3 triage.py

## Sample Output

========== ITSM Incident Triage Agent ==========
Enter incident title: Production database server is down
Enter incident description: Critical outage affecting all users

--- Triage Result ---
Category       : Infrastructure
Priority       : P1 - Critical
SLA Target     : 1 hour
Assign To      : Infrastructure Team

## Tech Stack
- Python 3.12
- No external dependencies

## Author
Akhil Yadati — ServiceNow Developer | ITSM Specialist