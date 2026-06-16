# ITSM Incident Triage Agent
# Automatically classifies IT incidents by priority, category, and assignment group

def classify_incident(title, description):
    title = title.lower()
    description = description.lower()
    text = title + " " + description

    # --- Determine Category ---
    if any(word in text for word in ["server", "database", "cpu", "memory", "disk", "storage"]):
        category = "Infrastructure"
    elif any(word in text for word in ["login", "password", "access", "permission", "locked"]):
        category = "Access Management"
    elif any(word in text for word in ["network", "vpn", "wifi", "internet", "connectivity"]):
        category = "Network"
    elif any(word in text for word in ["email", "outlook", "teams", "calendar"]):
        category = "Collaboration Tools"
    elif any(word in text for word in ["software", "application", "app", "install", "crash"]):
        category = "Application Support"
    else:
        category = "General IT"

    # --- Determine Priority ---
    if any(word in text for word in ["down", "outage", "critical", "production", "all users", "everyone"]):
        priority = "P1 - Critical"
        sla = "1 hour"
    elif any(word in text for word in ["slow", "intermittent", "some users", "degraded"]):
        priority = "P2 - High"
        sla = "4 hours"
    elif any(word in text for word in ["single user", "one user", "my", "i cannot", "i can't"]):
        priority = "P3 - Medium"
        sla = "8 hours"
    else:
        priority = "P4 - Low"
        sla = "24 hours"

    # --- Assign Group ---
    assignment_map = {
        "Infrastructure": "Infrastructure Team",
        "Access Management": "Security & IAM Team",
        "Network": "Network Operations Team",
        "Collaboration Tools": "End User Computing Team",
        "Application Support": "Application Support Team",
        "General IT": "Service Desk"
    }
    assignment_group = assignment_map[category]

    return {
        "category": category,
        "priority": priority,
        "sla": sla,
        "assignment_group": assignment_group
    }


def run_triage():
    print("\n========== ITSM Incident Triage Agent ==========")
    title = input("Enter incident title: ")
    description = input("Enter incident description: ")

    result = classify_incident(title, description)

    print("\n--- Triage Result ---")
    print(f"Category       : {result['category']}")
    print(f"Priority       : {result['priority']}")
    print(f"SLA Target     : {result['sla']}")
    print(f"Assign To      : {result['assignment_group']}")
    print("=============================================\n")


if __name__ == "__main__":
    run_triage()