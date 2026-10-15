import json
import time
from datetime import datetime

import psutil

from triage import MODEL, ai_triage, needs_review, parse_triage

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


def log_incident(issue, ai_result, status):
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "detected_issue": issue,
        "model": MODEL,
        "status": status,
        "ai_triage_result": ai_result,
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
    print(f"Model: {MODEL}")
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

            title = "System Performance Anomaly Detected"
            description = (
                f"Automated monitoring detected the following condition: {issue}. "
                "This was detected without human intervention via continuous system health monitoring."
            )

            result = ai_triage(title, description)
            status = "pending_review" if needs_review(parse_triage(result)) else "auto_assigned"

            print("--- AI Triage Result ---")
            print(result)
            if status == "pending_review":
                print("\nSTATUS: Pending human review (high priority)")
            else:
                print("\nSTATUS: Auto-assigned")
            print("=" * 60)

            log_incident(issue, result, status)
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
