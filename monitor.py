import psutil
import time
import json
from datetime import datetime
from openai import OpenAI

import os
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

CPU_THRESHOLD = 70
MEMORY_THRESHOLD = 80
DISK_THRESHOLD = 90

def get_system_metrics():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    return cpu, memory, disk

def detect_anomaly(cpu, memory, disk):
    issues = []
    if cpu > CPU_THRESHOLD:
        issues.append(f"High CPU usage detected: {cpu}%")
    if memory > MEMORY_THRESHOLD:
        issues.append(f"High memory usage detected: {memory}%")
    if disk > DISK_THRESHOLD:
        issues.append(f"Low disk space detected: {disk}% used")
    return issues

def ai_triage(title, description):
    prompt = f"""You are an expert ITSM triage agent. Analyze this IT incident and respond ONLY in this exact format:

CATEGORY: [one of: Infrastructure, Access Management, Network, Collaboration Tools, Application Support, General IT]
PRIORITY: [one of: P1 - Critical, P2 - High, P3 - Medium, P4 - Low]
SLA: [one of: 1 hour, 4 hours, 8 hours, 24 hours]
ASSIGNMENT GROUP: [one of: Infrastructure Team, Security & IAM Team, Network Operations Team, End User Computing Team, Application Support Team, Service Desk]
REASON: [one sentence explaining why you chose this priority]

Incident Title: {title}
Incident Description: {description}"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300
    )
    return response.choices[0].message.content

def log_incident(issue, ai_result):
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "detected_issue": issue,
        "ai_triage_result": ai_result
    }
    try:
        with open("incidents_log.json", "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []
    data.append(entry)
    with open("incidents_log.json", "w") as f:
        json.dump(data, f, indent=2)

def run_monitor():
    print("\n========== Autonomous ITSM Monitoring Agent ==========")
    print("Watching system health... (Press Ctrl+C to stop)\n")

    while True:
        cpu, memory, disk = get_system_metrics()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CPU: {cpu}% | Memory: {memory}% | Disk: {disk}%")

        issues = detect_anomaly(cpu, memory, disk)

        if issues:
            for issue in issues:
                print(f"\n🚨 ANOMALY DETECTED: {issue}")
                print("Auto-generating incident and triaging with AI...\n")

                title = "System Performance Anomaly Detected"
                description = f"Automated monitoring detected the following condition: {issue}. This was detected without human intervention via continuous system health monitoring."

                result = ai_triage(title, description)
                print("--- AI Triage Result ---")
                print(result)
                print("=" * 60)

                log_incident(issue, result)
                print("Incident logged to incidents_log.json\n")

        time.sleep(5)

if __name__ == "__main__":
    try:
        run_monitor()
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")