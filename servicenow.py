"""Minimal ServiceNow Table API client for the triage agent.

Set these in your shell to enable it (never commit them):
    export SN_INSTANCE="https://devXXXXX.service-now.com"
    export SN_USER="admin"
    export SN_PASSWORD="..."
"""
import os

import requests

PRIORITY_TO_IMPACT_URGENCY = {
    # Matches the out-of-box incident priority lookup.
    "P1": ("1", "1"),
    "P2": ("1", "2"),
    "P3": ("2", "2"),
    "P4": ("2", "3"),
}

PRIORITY_OPTIONS = ["P1 - Critical", "P2 - High", "P3 - Moderate", "P4 - Low"]


def configured():
    return all(os.environ.get(k) for k in ("SN_INSTANCE", "SN_USER", "SN_PASSWORD"))


def _base():
    return os.environ["SN_INSTANCE"].rstrip("/")


def _get(path, params):
    r = requests.get(
        f"{_base()}{path}",
        params=params,
        auth=(os.environ["SN_USER"], os.environ["SN_PASSWORD"]),
        headers={"Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["result"]


class Taxonomy:
    """The instance's own categories and incident-handling groups."""

    def __init__(self):
        choices = _get("/api/now/table/sys_choice", {
            "sysparm_query": "name=incident^element=category^inactive=false^language=en",
            "sysparm_fields": "label,value",
        })
        self.category_value = {c["label"]: c["value"] for c in choices}

        override = os.environ.get("SN_GROUPS")
        if override:
            names = [n.strip() for n in override.split(",") if n.strip()]
            query = "active=true^nameIN" + ",".join(names)
        else:
            # Groups that actually work incidents on this instance.
            stats = _get("/api/now/stats/incident", {
                "sysparm_group_by": "assignment_group",
                "sysparm_count": "true",
                "sysparm_display_value": "true",
            })
            names = [
                f["display_value"]
                for s in stats
                for f in s.get("groupby_fields", [])
                if f.get("display_value")
            ]
            query = "active=true^nameIN" + ",".join(names) if names else "active=true"
        groups = _get("/api/now/table/sys_user_group", {
            "sysparm_query": query,
            "sysparm_fields": "name,sys_id",
            "sysparm_limit": "25",
        })
        self.group_id = {g["name"]: g["sys_id"] for g in groups}

    def as_prompt_taxonomy(self):
        return {
            "CATEGORY": sorted(self.category_value),
            "PRIORITY": PRIORITY_OPTIONS,
            "ASSIGNMENT GROUP": sorted(self.group_id),
        }


def create_incident(title, description, result, status, why, taxonomy):
    """Create the incident with the AI's decision. Returns (number, url)."""
    d = result["decision"]
    impact, urgency = PRIORITY_TO_IMPACT_URGENCY.get(d.get("PRIORITY", "")[:2].upper(), ("2", "2"))

    note = (
        f"AI triage ({result['confidence']:.0%} agreement across {len(result['samples'])} samples)\n"
        f"Category: {d.get('CATEGORY')} | Priority: {d.get('PRIORITY')} | Group: {d.get('ASSIGNMENT GROUP')}\n"
        f"Reason: {d.get('REASON')}\n"
    )
    payload = {
        "short_description": title,
        "description": description,
        "impact": impact,
        "urgency": urgency,
        "category": taxonomy.category_value.get(d.get("CATEGORY"), ""),
    }
    if status == "auto_assigned":
        payload["assignment_group"] = taxonomy.group_id.get(d.get("ASSIGNMENT GROUP"), "")
        payload["work_notes"] = note + "Auto-assigned by the triage agent."
    else:
        # Leave it unassigned for a human; the recommendation is in the work notes.
        payload["work_notes"] = note + f"Held for human review: {why}. Assignment not set by the agent."

    r = requests.post(
        f"{_base()}/api/now/table/incident",
        json=payload,
        auth=(os.environ["SN_USER"], os.environ["SN_PASSWORD"]),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    rec = r.json()["result"]
    url = f"{_base()}/nav_to.do?uri=incident.do?sys_id={rec['sys_id']}"
    return rec["number"], url
