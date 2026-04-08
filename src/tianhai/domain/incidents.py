from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import Field, model_validator

from tianhai.domain.diagnosis import (
    DiagnosisFinding,
    KnowledgeEvidence,
    LogAnalysisRequest,
    LogEvidence,
    WorkflowHandoffSignal,
    WorkflowHandoffUrgency,
)
from tianhai.domain.logs import JavaLogBatch, TianHaiDomainModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class IncidentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class IncidentStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    AWAITING_CONTINUATION = "awaiting_continuation"
    CONTINUATION_REQUESTED = "continuation_requested"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class IncidentWorkflowPhase(StrEnum):
    CREATED = "created"
    SCOPE_RECORDED = "scope_recorded"
    WORKFLOW_RUNNING = "workflow_running"
    AWAITING_CONTINUATION = "awaiting_continuation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class IncidentLifecycleEventType(StrEnum):
    CREATED = "created"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_UPDATED = "execution_updated"
    CONTINUATION_REQUESTED = "continuation_requested"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_INCIDENT_STATUSES = frozenset(
    {
        IncidentStatus.COMPLETED,
        IncidentStatus.CANCELLED,
        IncidentStatus.FAILED,
    }
)


class IncidentExecutionState(TianHaiDomainModel):
    status: IncidentStatus = IncidentStatus.CREATED
    phase: IncidentWorkflowPhase = IncidentWorkflowPhase.CREATED
    workflow_id: str | None = None
    workflow_name: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    message: str | None = None
    continuation_count: int = Field(default=0, ge=0)
    started_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_INCIDENT_STATUSES

    @model_validator(mode="after")
    def completed_at_must_not_precede_started_at(self) -> IncidentExecutionState:
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("incident completed_at must not precede started_at")
        if (
            self.cancelled_at is not None
            and self.started_at is not None
            and self.cancelled_at < self.started_at
        ):
            raise ValueError("incident cancelled_at must not precede started_at")
        return self


class IncidentLifecycleEvent(TianHaiDomainModel):
    event_type: IncidentLifecycleEventType
    status: IncidentStatus
    phase: IncidentWorkflowPhase
    summary: str = Field(min_length=1)
    occurred_at: datetime = Field(default_factory=utc_now)
    run_id: str | None = None
    details: dict[str, str] = Field(default_factory=dict)


class IncidentContinuationRequest(TianHaiDomainModel):
    reason: str = Field(min_length=1)
    additional_log_batch: JavaLogBatch | None = None
    operator_notes: str | None = None
    resolved_missing_inputs: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    requested_at: datetime = Field(default_factory=utc_now)


class IncidentCancellationRequest(TianHaiDomainModel):
    reason: str = Field(min_length=1)
    requested_by: str | None = None
    requested_at: datetime = Field(default_factory=utc_now)


class IncidentDiagnosisResult(TianHaiDomainModel):
    summary: str = Field(min_length=1)
    status: IncidentStatus
    findings: tuple[DiagnosisFinding, ...] = ()
    evidence: tuple[LogEvidence, ...] = ()
    knowledge_evidence: tuple[KnowledgeEvidence, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    requires_continuation: bool = False


class IncidentRecord(TianHaiDomainModel):
    incident_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    severity: IncidentSeverity = IncidentSeverity.UNKNOWN
    request: LogAnalysisRequest
    handoff: WorkflowHandoffSignal
    execution: IncidentExecutionState = Field(default_factory=IncidentExecutionState)
    diagnosis_result: IncidentDiagnosisResult | None = None
    continuations: tuple[IncidentContinuationRequest, ...] = ()
    events: tuple[IncidentLifecycleEvent, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def status(self) -> IncidentStatus:
        return self.execution.status

    @property
    def is_terminal(self) -> bool:
        return self.execution.is_terminal

    @model_validator(mode="after")
    def updated_at_must_not_precede_created_at(self) -> IncidentRecord:
        if self.updated_at < self.created_at:
            raise ValueError("incident updated_at must not precede created_at")
        return self


class IncidentWorkflowRequest(TianHaiDomainModel):
    incident: IncidentRecord
    continuation: IncidentContinuationRequest | None = None


class IncidentWorkflowResult(TianHaiDomainModel):
    incident: IncidentRecord
    summary: str = Field(min_length=1)
    execution_state: IncidentExecutionState
    requires_continuation: bool = False
    next_actions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


def create_incident_record(
    *,
    request: LogAnalysisRequest,
    handoff: WorkflowHandoffSignal,
    incident_id: str | None = None,
    created_at: datetime | None = None,
) -> IncidentRecord:
    now = created_at or utc_now()
    execution = IncidentExecutionState(
        status=IncidentStatus.CREATED,
        phase=IncidentWorkflowPhase.CREATED,
        updated_at=now,
    )
    event = _event(
        execution=execution,
        event_type=IncidentLifecycleEventType.CREATED,
        summary="Incident created from primary-agent workflow handoff.",
        occurred_at=now,
        details={"handoff_type": handoff.handoff_type.value},
    )
    return IncidentRecord(
        incident_id=incident_id or f"inc-{uuid4()}",
        title=_title_from_request(request),
        severity=incident_severity_from_handoff(handoff),
        request=request,
        handoff=handoff,
        execution=execution,
        events=(event,),
        created_at=now,
        updated_at=now,
    )


def incident_severity_from_handoff(
    handoff: WorkflowHandoffSignal,
) -> IncidentSeverity:
    if handoff.urgency == WorkflowHandoffUrgency.CRITICAL:
        return IncidentSeverity.CRITICAL
    if handoff.urgency == WorkflowHandoffUrgency.HIGH:
        return IncidentSeverity.HIGH
    if handoff.urgency == WorkflowHandoffUrgency.NORMAL:
        return IncidentSeverity.MEDIUM
    return IncidentSeverity.UNKNOWN


def start_incident_execution(
    record: IncidentRecord,
    *,
    workflow_id: str | None,
    workflow_name: str | None,
    run_id: str | None,
    session_id: str | None,
    message: str | None = None,
    occurred_at: datetime | None = None,
) -> IncidentRecord:
    _ensure_can_run(record)
    now = occurred_at or utc_now()
    execution = record.execution.model_copy(
        update={
            "status": IncidentStatus.RUNNING,
            "phase": IncidentWorkflowPhase.WORKFLOW_RUNNING,
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "run_id": run_id,
            "session_id": session_id,
            "message": message or "Incident workflow execution started.",
            "started_at": record.execution.started_at or now,
            "updated_at": now,
            "completed_at": None,
            "cancelled_at": None,
        }
    )
    return _with_event(
        record,
        execution=execution,
        event_type=IncidentLifecycleEventType.EXECUTION_STARTED,
        summary="Incident workflow execution started.",
        occurred_at=now,
    )


def mark_incident_scope_recorded(
    record: IncidentRecord,
    *,
    message: str = "Incident workflow scope recorded.",
    occurred_at: datetime | None = None,
) -> IncidentRecord:
    _ensure_not_terminal(record)
    now = occurred_at or utc_now()
    execution = record.execution.model_copy(
        update={
            "status": IncidentStatus.RUNNING,
            "phase": IncidentWorkflowPhase.SCOPE_RECORDED,
            "message": message,
            "updated_at": now,
        }
    )
    return _with_event(
        record,
        execution=execution,
        event_type=IncidentLifecycleEventType.EXECUTION_UPDATED,
        summary=message,
        occurred_at=now,
    )


def mark_incident_awaiting_continuation(
    record: IncidentRecord,
    *,
    missing_inputs: tuple[str, ...] = (),
    message: str = "Incident workflow is awaiting continuation input.",
    occurred_at: datetime | None = None,
) -> IncidentRecord:
    _ensure_not_terminal(record)
    now = occurred_at or utc_now()
    execution = record.execution.model_copy(
        update={
            "status": IncidentStatus.AWAITING_CONTINUATION,
            "phase": IncidentWorkflowPhase.AWAITING_CONTINUATION,
            "message": message,
            "updated_at": now,
        }
    )
    details = {}
    if missing_inputs:
        details["missing_inputs"] = ", ".join(missing_inputs)
    return _with_event(
        record,
        execution=execution,
        event_type=IncidentLifecycleEventType.CONTINUATION_REQUESTED,
        summary=message,
        occurred_at=now,
        details=details,
    )


def add_incident_continuation(
    record: IncidentRecord,
    continuation: IncidentContinuationRequest,
    *,
    occurred_at: datetime | None = None,
) -> IncidentRecord:
    _ensure_not_terminal(record)
    now = occurred_at or utc_now()
    continuation_count = len(record.continuations) + 1
    execution = record.execution.model_copy(
        update={
            "status": IncidentStatus.CONTINUATION_REQUESTED,
            "phase": IncidentWorkflowPhase.SCOPE_RECORDED,
            "message": "Incident continuation requested.",
            "continuation_count": continuation_count,
            "updated_at": now,
        }
    )
    return _with_event(
        record,
        execution=execution,
        event_type=IncidentLifecycleEventType.CONTINUATION_REQUESTED,
        summary="Incident continuation requested.",
        occurred_at=now,
        continuations=record.continuations + (continuation,),
    )


def complete_incident(
    record: IncidentRecord,
    result: IncidentDiagnosisResult,
    *,
    occurred_at: datetime | None = None,
) -> IncidentRecord:
    _ensure_not_terminal(record)
    now = occurred_at or utc_now()
    execution = record.execution.model_copy(
        update={
            "status": IncidentStatus.COMPLETED,
            "phase": IncidentWorkflowPhase.COMPLETED,
            "message": result.summary,
            "updated_at": now,
            "completed_at": now,
        }
    )
    return _with_event(
        record,
        execution=execution,
        event_type=IncidentLifecycleEventType.COMPLETED,
        summary="Incident diagnosis completed.",
        occurred_at=now,
        diagnosis_result=result,
    )


def cancel_incident(
    record: IncidentRecord,
    cancellation: IncidentCancellationRequest,
    *,
    workflow_cancelled: bool | None = None,
    occurred_at: datetime | None = None,
) -> IncidentRecord:
    if record.status == IncidentStatus.CANCELLED:
        return record
    _ensure_not_terminal(record)
    now = occurred_at or utc_now()
    execution = record.execution.model_copy(
        update={
            "status": IncidentStatus.CANCELLED,
            "phase": IncidentWorkflowPhase.CANCELLED,
            "message": cancellation.reason,
            "updated_at": now,
            "completed_at": now,
            "cancelled_at": now,
        }
    )
    details: dict[str, str] = {"reason": cancellation.reason}
    if cancellation.requested_by:
        details["requested_by"] = cancellation.requested_by
    if workflow_cancelled is not None:
        details["workflow_cancelled"] = str(workflow_cancelled)
    return _with_event(
        record,
        execution=execution,
        event_type=IncidentLifecycleEventType.CANCELLED,
        summary="Incident cancelled.",
        occurred_at=now,
        details=details,
    )


def fail_incident(
    record: IncidentRecord,
    *,
    error: str,
    occurred_at: datetime | None = None,
) -> IncidentRecord:
    if record.status == IncidentStatus.FAILED:
        return record
    _ensure_not_terminal(record)
    now = occurred_at or utc_now()
    execution = record.execution.model_copy(
        update={
            "status": IncidentStatus.FAILED,
            "phase": IncidentWorkflowPhase.FAILED,
            "message": error,
            "updated_at": now,
            "completed_at": now,
        }
    )
    return _with_event(
        record,
        execution=execution,
        event_type=IncidentLifecycleEventType.FAILED,
        summary="Incident workflow failed.",
        occurred_at=now,
        details={"error": error},
    )


def _ensure_not_terminal(record: IncidentRecord) -> None:
    if record.is_terminal:
        raise ValueError(f"incident {record.incident_id} is already {record.status}")


def _ensure_can_run(record: IncidentRecord) -> None:
    _ensure_not_terminal(record)


def _event(
    *,
    execution: IncidentExecutionState,
    event_type: IncidentLifecycleEventType,
    summary: str,
    occurred_at: datetime,
    details: dict[str, str] | None = None,
) -> IncidentLifecycleEvent:
    return IncidentLifecycleEvent(
        event_type=event_type,
        status=execution.status,
        phase=execution.phase,
        summary=summary,
        occurred_at=occurred_at,
        run_id=execution.run_id,
        details=details or {},
    )


def _with_event(
    record: IncidentRecord,
    *,
    execution: IncidentExecutionState,
    event_type: IncidentLifecycleEventType,
    summary: str,
    occurred_at: datetime,
    details: dict[str, str] | None = None,
    continuations: tuple[IncidentContinuationRequest, ...] | None = None,
    diagnosis_result: IncidentDiagnosisResult | None = None,
) -> IncidentRecord:
    return record.model_copy(
        update={
            "execution": execution,
            "continuations": (
                continuations
                if continuations is not None
                else record.continuations
            ),
            "diagnosis_result": (
                diagnosis_result
                if diagnosis_result is not None
                else record.diagnosis_result
            ),
            "events": record.events
            + (
                _event(
                    execution=execution,
                    event_type=event_type,
                    summary=summary,
                    occurred_at=occurred_at,
                    details=details,
                ),
            ),
            "updated_at": occurred_at,
        }
    )


def _title_from_request(request: LogAnalysisRequest) -> str:
    question = request.question.strip()
    if len(question) <= 80:
        return question
    return f"{question[:77]}..."
