# ITSM Incident Triage Agent

An agent that detects system problems, opens incidents in ServiceNow, and triages them with an LLM. Critical or uncertain calls are held for a human. The project also tests how far that triage can be trusted, and found that the benchmark was the weak link, not the model.

![Demo: a CPU spike is detected, triaged as P2, and held for human review](demo.gif)

*Live run: `stress.py` pushes CPU to 100%, the agent opens one incident, the model triages it, and the high-priority result is held for human review.*

## Key finding

On 300 labeled IT tickets, the model looked worse than guessing on priority (38% vs. a 47% baseline). A blind audit told a different story. I labeled 39 of those tickets myself, as a ServiceNow administrator, without seeing either the dataset's label or the model's answer.

| Field | I agree with the dataset | I agree with the model | Random chance |
|---|---|---|---|
| Type (Incident / Request / Problem / Change) | 59% | **85%** | 25% |
| Priority (high / medium / low) | 36% | **85%** | 33% |
| Assignment group (4 IT queues) | 28% | **54%** | 25% |

On priority and group, the dataset's labels were close to random relative to an administrator's judgment. The model's "low accuracy" was mostly disagreement with a noisy answer key.

**Lesson:** before trusting an AI triage score, check the labels it is scored against.

**Second finding: self-consistency was not a reliable confidence signal.** Each ticket is triaged three times, and disagreement routes it to a human. Across the 300 tickets, the flag caught mistakes at roughly the rate random flagging would. It helped on type (72% vs. 52% accuracy for confident vs. flagged answers) but not on priority or group. Agreement means the model is consistent, not that it is right, so the review gate also has to cover high priority regardless of confidence.

### Limits

- One rater and 39 tickets. The gap is large, but a single administrator is not ground truth. A second rater would show how much people agree with each other.
- The model and I may share textbook ITIL definitions; a real service desk has local rules.
- The tickets are synthetic: [Tobi-Bueck/customer-support-tickets](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets) (CC BY-NC 4.0), English only, filtered to the four IT queues, 300 sampled with a fixed seed.
- Group accuracy is weak even against my labels (54%). The four queues overlap and there is no security team, so some tickets have no clean home.

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
