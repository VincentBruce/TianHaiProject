from __future__ import annotations

from tianhai.control.types import IncidentHighRiskAssessment
from tianhai.domain import IncidentRecord, IncidentSeverity


DEFAULT_HIGH_RISK_SEVERITIES = frozenset(
    {
        IncidentSeverity.HIGH,
        IncidentSeverity.CRITICAL,
    }
)
HIGH_RISK_CONSTRAINT_KEYWORDS = (
    "prod",
    "production",
    "customer-impact",
    "customer impacting",
    "customer-facing",
    "security",
    "sensitive",
    "credential",
    "pii",
)


def assess_incident_high_risk(
    incident: IncidentRecord,
) -> IncidentHighRiskAssessment:
    reasons: list[str] = []

    if incident.severity in DEFAULT_HIGH_RISK_SEVERITIES:
        reasons.append(
            f"Incident severity '{incident.severity.value}' requires operator approval."
        )

    constraint_text = " ".join(
        (
            *incident.request.constraints,
            *(
                constraint
                for continuation in incident.continuations
                for constraint in continuation.constraints
            ),
        )
    ).lower()
    if constraint_text and any(
        keyword in constraint_text for keyword in HIGH_RISK_CONSTRAINT_KEYWORDS
    ):
        reasons.append(
            "Incident constraints indicate production or sensitive operational context."
        )

    return IncidentHighRiskAssessment(
        requires_approval=bool(reasons),
        reasons=tuple(reasons),
    )
