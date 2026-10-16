import json
import time
from datetime import datetime

import psutil

import servicenow
from triage import DEFAULT_TAXONOMY, MODEL, SAMPLES, format_result, route, triage_with_confidence

CPU_THRESHOLD = 70
MEMORY_THRESHOLD = 80
DISK_THRESHOLD = 90

POLL_SECONDS = 5
# While a condition stays breached, don't open a duplicate incident
# for the same metric until this many seconds have passed.
COOLDOWN_SECONDS = 300

LOG_FILE = "incidents_log.json"


def get_system_metrics():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    return cpu, memory, disk


def detect_anomaly(cpu, memory, disk):
    """Return a list of (metric, message) for each breached threshold."""
    issues = []
    if cpu > CPU_THRESHOLD:
        issues.append(("cpu", f"High CPU usage detected: {cpu}%"))
    if memory > MEMORY_THRESHOLD:
        issues.append(("memory", f"High memory usage detected: {memory}%"))
    if disk > DISK_THRESHOLD:
        issues.append(("disk", f"Low disk space detected: {disk}% used"))
    return issues


def log_incident(issue, result, status, why, sn_number=None):
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "detected_issue": issue,
        "model": MODEL,
        "status": status,
        "why": why,
        "confidence": result["confidence"],
        "decision": result["decision"],
        "servicenow_incident": sn_number,
    }
    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []
    data.append(entry)
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def run_monitor():
    print("\n========== Autonomous ITSM Monitoring Agent ==========")
    print(f"Model: {MODEL} | Samples per incident: {SAMPLES}")

    taxonomy = None
    prompt_taxonomy = DEFAULT_TAXONOMY
    if servicenow.configured():
        try:
            taxonomy = servicenow.Taxonomy()
            if not taxonomy.category_value or not taxonomy.group_id:
                raise RuntimeError("no categories or groups found on existing incidents")
            prompt_taxonomy = taxonomy.as_prompt_taxonomy()
            print(f"ServiceNow: {servicenow._base()}")
            print(f"  {len(taxonomy.category_value)} categories, {len(taxonomy.group_id)} assignment groups loaded from the instance")
        except Exception as exc:
            taxonomy = None
            print(f"ServiceNow: could not load taxonomy ({exc}). Logging locally only.")
    else:
        print("ServiceNow: not configured (logging locally only)")
    print("Watching system health... (Press Ctrl+C to stop)\n")

    last_incident = {}  # metric -> time an incident was last opened

    while True:
        cpu, memory, disk = get_system_metrics()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CPU: {cpu}% | Memory: {memory}% | Disk: {disk}%")

        breached = set()
        for metric, issue in detect_anomaly(cpu, memory, disk):
            breached.add(metric)
            now = time.time()
            if now - last_incident.get(metric, 0) < COOLDOWN_SECONDS:
                continue  # incident already open for this condition
            last_incident[metric] = now

            print(f"\n🚨 ANOMALY DETECTED: {issue}")
            print("Auto-generating incident and triaging with AI...\n")

            title = f"Monitoring alert: {issue}"
            description = (
                f"Automated monitoring detected the following condition: {issue}. "
                "This was detected without human intervention via continuous system health monitoring."
            )

            result = triage_with_confidence(title, description, prompt_taxonomy)
            status, why = route(result)

            print("--- AI Triage Result ---")
            print(format_result(result))
            label = "Pending human review" if status == "pending_review" else "Auto-assigned"
            print(f"\nSTATUS: {label} ({why})")

            sn_number = None
            if taxonomy:
                try:
                    sn_number, url = servicenow.create_incident(title, description, result, status, why, taxonomy)
                    print(f"ServiceNow: created {sn_number}  {url}")
                except Exception as exc:  # keep monitoring even if the instance is unreachable
                    print(f"ServiceNow: failed to create incident ({exc})")
            print("=" * 60)

            log_incident(issue, result, status, why, sn_number)
            print(f"Incident logged to {LOG_FILE}\n")

        # A metric that has recovered can raise a fresh incident next time.
        for metric in list(last_incident):
            if metric not in breached:
                del last_incident[metric]

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        run_monitor()
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
