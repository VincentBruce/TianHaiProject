from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from tianhai.domain.logs import (
    JavaLogBatch,
    LogPosition,
    LogSeverity,
    LogSource,
    TianHaiDomainModel,
)


class DiagnosisResponseMode(StrEnum):
    DIRECT_RESPONSE = "direct_response"
    WORKFLOW_HANDOFF = "workflow_handoff"


class DiagnosisConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class WorkflowHandoffUrgency(StrEnum):
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowHandoffType(StrEnum):
    DURABLE_LOG_INVESTIGATION = "durable_log_investigation"


class LogAnalysisRequest(TianHaiDomainModel):
    question: str = Field(min_length=1)
    log_batch: JavaLogBatch
    service_context: str | None = None
    constraints: tuple[str, ...] = ()
    allow_workflow_handoff: bool = True


class LogEvidence(TianHaiDomainModel):
    id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    log_excerpt: str | None = None
    severity: LogSeverity = LogSeverity.UNKNOWN
    source: LogSource | None = None
    position: LogPosition | None = None


class DiagnosisFinding(TianHaiDomainModel):
    title: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    severity: LogSeverity = LogSeverity.UNKNOWN
    evidence_ids: tuple[str, ...] = ()


class WorkflowHandoffSignal(TianHaiDomainModel):
    handoff_type: WorkflowHandoffType = (
        WorkflowHandoffType.DURABLE_LOG_INVESTIGATION
    )
    reason: str = Field(min_length=1)
    urgency: WorkflowHandoffUrgency = WorkflowHandoffUrgency.NORMAL
    missing_inputs: tuple[str, ...] = ()
    suggested_next_step: str | None = None


class DiagnosisReport(TianHaiDomainModel):
    response_mode: DiagnosisResponseMode = DiagnosisResponseMode.DIRECT_RESPONSE
    summary: str = Field(min_length=1)
    confidence: DiagnosisConfidence = DiagnosisConfidence.UNKNOWN
    findings: tuple[DiagnosisFinding, ...] = ()
    evidence: tuple[LogEvidence, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    workflow_handoff: WorkflowHandoffSignal | None = None

    @model_validator(mode="after")
    def handoff_must_match_response_mode(self) -> DiagnosisReport:
        if self.response_mode == DiagnosisResponseMode.DIRECT_RESPONSE:
            if self.workflow_handoff is not None:
                raise ValueError(
                    "direct response reports must not include workflow_handoff"
                )
        elif self.workflow_handoff is None:
            raise ValueError("workflow handoff reports require workflow_handoff")
        return self
