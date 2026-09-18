"""
Synthetic past-incident records for the live data index (type="incident").

No real incident/CAD data is available (per Plan.md §5 open decision), so this is a
seeded demo dataset — not sourced from data/docs/. Addresses repeat on purpose so the
"past incidents at this address" retrieval value (officer/responder safety flags,
prior call context) is demonstrable, same as a real CAD system would surface.
"""

INCIDENT_CHUNKS = [
    {
        "id": "incident-001",
        "text": (
            "Prior call at 42 Oak Street: 68-year-old male choked on food during dinner. "
            "Caller performed abdominal thrusts before EMS arrival, object dislodged on scene. "
            "Patient alert and breathing normally on EMS arrival, transport declined."
        ),
        "metadata": {
            "type": "incident",
            "address": "42 Oak Street",
            "date": "2026-03-14",
            "incidentType": "choking",
            "outcome": "resolved-on-scene",
            "hazardFlag": "none",
            "priorityAtTime": "P1-critical",
        },
    },
    {
        "id": "incident-002",
        "text": (
            "Prior call at 42 Oak Street: welfare check requested by neighbor. Responding "
            "officer noted an aggressive unrestrained dog on the property blocking entry to "
            "the front door. Animal control was requested before officers could make contact."
        ),
        "metadata": {
            "type": "incident",
            "address": "42 Oak Street",
            "date": "2026-05-02",
            "incidentType": "welfare-check",
            "outcome": "animal-control-requested",
            "hazardFlag": "aggressive-dog-on-property",
            "priorityAtTime": "P3-monitor",
        },
    },
    {
        "id": "incident-003",
        "text": (
            "Prior call at 118 Birch Avenue: 54-year-old male found unresponsive, not "
            "breathing, no pulse. Bystander CPR started before EMS arrival. AED applied on "
            "scene, one shock delivered, return of spontaneous circulation achieved. "
            "Transported to hospital in stable condition."
        ),
        "metadata": {
            "type": "incident",
            "address": "118 Birch Avenue",
            "date": "2026-01-22",
            "incidentType": "cardiac-arrest",
            "outcome": "transported-stable",
            "hazardFlag": "none",
            "priorityAtTime": "P1-critical",
        },
    },
    {
        "id": "incident-004",
        "text": (
            "Prior call at 118 Birch Avenue: resident reported a fall from a ladder while "
            "cleaning gutters. Suspected fractured wrist, no loss of consciousness. "
            "Transported for evaluation."
        ),
        "metadata": {
            "type": "incident",
            "address": "118 Birch Avenue",
            "date": "2026-04-09",
            "incidentType": "fall-injury",
            "outcome": "transported-stable",
            "hazardFlag": "none",
            "priorityAtTime": "P2-assess",
        },
    },
    {
        "id": "incident-005",
        "text": (
            "Prior call at 7 Maple Court: pregnant caller choking on a piece of hard candy. "
            "Chest thrusts performed per pregnant/obese variant protocol, object dislodged "
            "before EMS arrival. Patient transported as a precaution given pregnancy."
        ),
        "metadata": {
            "type": "incident",
            "address": "7 Maple Court",
            "date": "2026-02-18",
            "incidentType": "choking",
            "outcome": "transported-precautionary",
            "hazardFlag": "none",
            "priorityAtTime": "P1-critical",
        },
    },
    {
        "id": "incident-006",
        "text": (
            "Prior call at 7 Maple Court: domestic disturbance reported by neighbor. Dispatch "
            "notes indicate a firearm registered to a resident at this address from a prior, "
            "unrelated call. Responding units advised to stage and confirm scene safety before "
            "approach."
        ),
        "metadata": {
            "type": "incident",
            "address": "7 Maple Court",
            "date": "2025-11-30",
            "incidentType": "domestic-disturbance",
            "outcome": "units-dispatched",
            "hazardFlag": "firearm-on-premises",
            "priorityAtTime": "P1-critical",
        },
    },
    {
        "id": "incident-007",
        "text": (
            "Prior call at 900 Cedar Boulevard: caller found family member in cardiac arrest "
            "in the garage. Responding crew detected elevated carbon monoxide levels from a "
            "running vehicle left in an enclosed space. Patient pronounced deceased on scene. "
            "Fire department ventilated the structure; hazmat precautions taken for entry."
        ),
        "metadata": {
            "type": "incident",
            "address": "900 Cedar Boulevard",
            "date": "2025-12-05",
            "incidentType": "cardiac-arrest",
            "outcome": "deceased-on-scene",
            "hazardFlag": "carbon-monoxide-elevated-levels",
            "priorityAtTime": "P1-critical",
        },
    },
    {
        "id": "incident-008",
        "text": (
            "Prior call at 55 Pine Street: 8-month-old infant choking on a small toy part. "
            "Caller performed infant back blows per dispatcher pre-arrival instructions, "
            "object cleared before EMS arrival. Infant alert and crying normally, transported "
            "for routine evaluation."
        ),
        "metadata": {
            "type": "incident",
            "address": "55 Pine Street",
            "date": "2026-06-11",
            "incidentType": "choking",
            "outcome": "transported-precautionary",
            "hazardFlag": "none",
            "priorityAtTime": "P1-critical",
        },
    },
]
