import pytest

from tianhai.domain import (
    IncidentCancellationRequest,
    IncidentContinuationRequest,
    IncidentLifecycleEventType,
    IncidentSeverity,
    IncidentStatus,
    JavaLogBatch,
    LogAnalysisRequest,
    WorkflowHandoffSignal,
    WorkflowHandoffUrgency,
    add_incident_continuation,
    cancel_incident,
    create_incident_record,
    mark_incident_awaiting_continuation,
    mark_incident_scope_recorded,
    start_incident_execution,
)


def test_create_incident_record_from_workflow_handoff_signal() -> None:
    record = create_incident_record(
        request=_request(),
        handoff=WorkflowHandoffSignal(
            reason="The excerpt lacks upstream logs.",
            urgency=WorkflowHandoffUrgency.HIGH,
        ),
        incident_id="inc-orders-timeout",
    )

    assert record.incident_id == "inc-orders-timeout"
    assert record.title == "Why is checkout failing?"
    assert record.severity == IncidentSeverity.HIGH
    assert record.status == IncidentStatus.CREATED
    assert record.events[0].event_type == IncidentLifecycleEventType.CREATED


def test_incident_lifecycle_tracks_execution_and_continuation() -> None:
    record = create_incident_record(
        request=_request(),
        handoff=WorkflowHandoffSignal(
            reason="More correlation is required.",
            missing_inputs=("database logs",),
        ),
        incident_id="inc-continuation",
    )

    running = start_incident_execution(
        record,
        workflow_id="workflow-1",
        workflow_name="Incident Workflow",
        run_id="run-1",
        session_id="session-1",
    )
    scoped = mark_incident_scope_recorded(running)
    awaiting = mark_incident_awaiting_continuation(
        scoped,
        missing_inputs=("database logs",),
    )
    continued = add_incident_continuation(
        awaiting,
        IncidentContinuationRequest(
            reason="Added database logs.",
            additional_log_batch=JavaLogBatch(raw_excerpt="ERROR lock wait timeout"),
        ),
    )

    assert continued.status == IncidentStatus.CONTINUATION_REQUESTED
    assert continued.execution.continuation_count == 1
    assert continued.execution.run_id == "run-1"
    assert continued.continuations[0].reason == "Added database logs."
    assert continued.events[-1].event_type == (
        IncidentLifecycleEventType.CONTINUATION_REQUESTED
    )


def test_cancelled_incident_rejects_later_execution_and_continuation() -> None:
    record = create_incident_record(
        request=_request(),
        handoff=WorkflowHandoffSignal(reason="Needs durable investigation."),
        incident_id="inc-cancelled",
    )

    cancelled = cancel_incident(
        record,
        IncidentCancellationRequest(reason="Operator cancelled the investigation."),
    )

    assert cancelled.status == IncidentStatus.CANCELLED
    assert cancelled.is_terminal is True

    with pytest.raises(ValueError):
        start_incident_execution(
            cancelled,
            workflow_id="workflow-1",
            workflow_name="Incident Workflow",
            run_id="run-1",
            session_id="session-1",
        )

    with pytest.raises(ValueError):
        add_incident_continuation(
            cancelled,
            IncidentContinuationRequest(reason="Try to restart."),
        )


def _request() -> LogAnalysisRequest:
    return LogAnalysisRequest(
        question="Why is checkout failing?",
        log_batch=JavaLogBatch(raw_excerpt="ERROR java.sql.SQLTimeoutException"),
    )
