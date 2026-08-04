"""
backend/conditions_catalog.py — Phase 17: Registration UI (Disease Checklist)

The fixed list of common conditions shown as checkboxes on the
registration form. Deliberately a plain Python list, not a database
table — this list is the same for every patient and doesn't change per
request, so there's no reason to hit the database (or even the network)
just to render checkboxes. Compare to UserCondition in db/models.py,
which IS a per-user, per-row table — that's what actually gets written
to once a patient picks items from this fixed list.

"Other" is intentionally NOT in this list — the frontend renders it as
its own checkbox + free-text input (see frontend/js/register.js), and
whatever the patient types there is sent alongside anything picked from
this list, not as a value from it.
"""

AVAILABLE_CONDITIONS: list[str] = [
    "Diabetes",
    "Hypertension (High Blood Pressure)",
    "Pregnant",
    "Asthma",
    "Heart Disease",
    "Tuberculosis (TB)",
    "Malaria (recurring)",
    "HIV/AIDS",
    "Epilepsy",
    "Kidney Disease",
    "Liver Disease",
    "Hepatitis",
    "Anemia",
    "Malnutrition",
    "Mental Health Condition",
    "Physical Disability",
    "Allergy",
    "Cancer",
    "Stroke (History Of)",
    "Thyroid Disorder",
]