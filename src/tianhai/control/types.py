from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from tianhai.domain.incidents import utc_now
from tianhai.domain.logs import TianHaiDomainModel


class IncidentControlAction(StrEnum):
    APPROVAL = "approval"
    PAUSE = "pause"
    CONTINUE = "continue"
    CANCELLATION = "cancellation"


class IncidentControlState(StrEnum):
    ACTIVE = "active"
    AWAITING_APPROVAL = "awaiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class IncidentApprovalStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class IncidentControlCapability(TianHaiDomainModel):
    action: IncidentControlAction
    supported: bool = True
    available: bool = False
    detail: str = Field(min_length=1)


class IncidentHighRiskAssessment(TianHaiDomainModel):
    requires_approval: bool = False
    reasons: tuple[str, ...] = ()


class IncidentApprovalDecision(TianHaiDomainModel):
    approved: bool
    reviewed_by: str | None = None
    note: str | None = None
    reviewed_at: datetime = Field(default_factory=utc_now)


class IncidentControlSnapshot(TianHaiDomainModel):
    incident_id: str = Field(min_length=1)
    run_id: str | None = None
    session_id: str | None = None
    control_state: IncidentControlState
    approval_status: IncidentApprovalStatus = IncidentApprovalStatus.NOT_REQUIRED
    paused_step_name: str | None = None
    paused_step_type: str | None = None
    paused_message: str | None = None
    high_risk_assessment: IncidentHighRiskAssessment = Field(
        default_factory=IncidentHighRiskAssessment,
    )
    supported_capabilities: tuple[IncidentControlCapability, ...] = ()
    available_actions: tuple[IncidentControlAction, ...] = ()
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def awaiting_approval_requires_pending_status(self) -> IncidentControlSnapshot:
        if (
            self.control_state == IncidentControlState.AWAITING_APPROVAL
            and self.approval_status != IncidentApprovalStatus.PENDING
        ):
            raise ValueError(
                "awaiting_approval snapshots must use approval_status='pending'"
            )
        return self
