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
    """The categories and groups this instance actually uses on incidents.

    Learned from the incident table with the Aggregate API, so the
    integration user only needs the itil role (no access to sys_choice).
    """

    def __init__(self):
        self.category_value = self._used_values("category")
        self.group_id = self._used_values("assignment_group")
        # Monitoring incidents are raised by the integration user itself.
        users = _get("/api/now/table/sys_user", {
            "sysparm_query": f"user_name={os.environ['SN_USER']}",
            "sysparm_fields": "sys_id",
            "sysparm_limit": "1",
        })
        self.caller_id = users[0]["sys_id"] if users else ""
        override = os.environ.get("SN_GROUPS")
        if override:
            keep = {n.strip() for n in override.split(",") if n.strip()}
            self.group_id = {n: v for n, v in self.group_id.items() if n in keep}

    @staticmethod
    def _used_values(field):
        """Return {display label: stored value} for values used on incidents."""
        stats = _get("/api/now/stats/incident", {
            "sysparm_group_by": field,
            "sysparm_count": "true",
            "sysparm_display_value": "all",
        })
        out = {}
        for s in stats:
            for f in s.get("groupby_fields", []):
                label, value = f.get("display_value"), f.get("value")
                if label and value:
                    out[label] = value
        return out

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
        "caller_id": taxonomy.caller_id,
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
