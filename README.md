# ITSM Incident Triage Agent

An agent that detects system problems, opens incidents in ServiceNow, and triages them with an LLM. Critical or uncertain calls are held for a human. The project also tests how far that triage can be trusted, and found that the benchmark was the weak link, not the model.

![Demo: a CPU spike is detected, triaged as P2, and held for human review](demo.gif)

*Live run: `stress.py` pushes CPU to 100%, the agent opens one incident, the model triages it, and the high-priority result is held for human review.*

## Key findings

### 1. The benchmark was broken, not the model

On 300 labeled IT tickets, the model looked worse than guessing on priority (38% vs. a 47% majority-class baseline). Two people then labeled the tickets blind, without seeing the dataset's label or the model's answer: me (39 tickets) and a second rater (20 of the same tickets).

On the 20 tickets both of us labeled:

| Field | Rater 1 vs rater 2 | Raters vs dataset | Raters vs model |
|---|---|---|---|
| Type | 90% (kappa 0.73) | 60-70% | **95%** |
| Priority | 85% (kappa 0.75) | 45% | **80-95%** |
| Assignment group | 95% (kappa 0.92) | **25%** (chance) | 50-55% |

The two raters agreed strongly with each other and disagreed with the dataset, so the labels are the weak link. On type and priority, the model agrees with each rater about as often as the raters agree with each other, which is human-level on this data.

**Lesson:** before trusting an AI triage score, check the labels it is scored against.

### 2. Assignment group is the real gap, and part of it is missing context

On group, the raters agreed 95% but the model only about 50%. The raters had a one-line definition of each team; the model only had the team names. Giving the model the same definitions:

| Field | Rater 1: before -> after | Rater 2: before -> after |
|---|---|---|
| Assignment group | 54% -> **67%** | 55% -> **75%** |
| Priority | 85% -> 92% | 95% -> 90% |
| Type | 85% -> 77% | 95% -> 100% |

Group improved by 13-20 points but did not reach the human level. The second rater found why: on 7 of 19 tickets, one missing fact decided the call, usually *is the affected system internal company IT or the customer's product?* In ServiceNow that comes from structured fields (caller, configuration item, service), not the ticket text. Text-only triage can't route what the text doesn't say. Feeding caller and CI context into the prompt is the next step.

### 3. Self-consistency is not a confidence signal

Each ticket is triaged three times and disagreement routes it to a human. Across 300 tickets, that flag caught mistakes at about the rate random flagging would. Consistent does not mean correct, so P1/P2 always go to a person regardless of agreement.

### Limits

- Small samples: 39 tickets for rater 1, 20 shared with rater 2. One ticket moves a percentage by 2.5-5 points, so treat small differences (like type dropping 85% -> 77%) as noise.
- The definitions experiment was measured on the same tickets the raters labeled, and the "before" answers came from a separate run, so some change is run-to-run variation.
- Both raters and the model may share textbook ITIL definitions; a real service desk has local rules.
- The tickets are synthetic: [Tobi-Bueck/customer-support-tickets](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets) (CC BY-NC 4.0), English only, filtered to the four IT queues, 300 sampled with a fixed seed.

## What it does

1. **Detects** CPU, memory, and disk breaches on the host (`monitor.py`). A cooldown means one sustained spike opens one incident, not an alert storm.
2. **Triages** with an LLM (`triage.py`), three times per incident, and votes on category, priority, and assignment group.
3. **Routes**: confident, low-priority incidents are auto-assigned. P1/P2, or any incident where the samples disagree, is held for human review.
4. **Writes to ServiceNow** (`servicenow.py`) through the Table API:
   - Runs as a dedicated `triage.agent` user (identity type Machine, `itil` role only), not admin.
   - Learns the categories and assignment groups the instance actually uses from the Aggregate API on `incident`, so it needs no access to `sys_choice`.
   - Maps priority to impact and urgency so ServiceNow calculates priority itself.
   - Puts the AI's reasoning and agreement score in the work notes. Held incidents stay unassigned.

## Evaluation tools

| Command | What it does |
|---|---|
| `python3 evaluate.py ...` | Accuracy per field, a majority-class baseline, and confident vs. flagged accuracy |
| `python3 audit.py make` | A blind sample for a human to label (labels hidden) |
| `python3 audit.py label` | Label it in the terminal, one ticket at a time |
| `python3 audit.py score` | Does the human agree more with the dataset or the model? |
| `python3 audit.py rater2` / `agree` | Second blind rater and inter-rater agreement (Cohen's kappa) |
| `python3 audit.py retriage` | Re-run the model with the raters' definitions and compare |
| `python3 audit.py confusion` | How each field goes wrong |

## How to run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="..."            # optional: OPENAI_MODEL (default gpt-5.4-mini)

# Optional: create incidents in ServiceNow
export SN_INSTANCE="https://devXXXXX.service-now.com"
export SN_USER="triage.agent"
export SN_PASSWORD='...'

python3 monitor.py                     # watch system health
python3 stress.py                      # in a second terminal, trigger a CPU spike
```

Reproduce the evaluation:

```bash
curl -L -o tickets.csv "https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/resolve/main/dataset-tickets-multi-lang-4-20k.csv"
python3 evaluate.py --csv tickets.csv \
  --filter "language=en" \
  --filter "queue=Technical Support|IT Support|Product Support|Service Outages and Maintenance" \
  --label "TYPE=type" --label "PRIORITY=priority" --label "ASSIGNMENT GROUP=queue" \
  --n 300 --out eval_300
```

## Context

ServiceNow's Predictive Intelligence learns from historical tickets, and Now Assist now brings generative AI triage to the platform. This project builds the pattern end to end to understand it: detection, triage, a human checkpoint, and an honest test of how far to trust it.

## Author

Akhil Yadati, ServiceNow Developer
