from agno.run.workflow import WorkflowRunOutput
from agno.workflow import Workflow

from tianhai.domain import (
    IncidentCancellationRequest,
    IncidentContinuationRequest,
    IncidentStatus,
    IncidentWorkflowRequest,
    IncidentWorkflowResult,
    JavaLogBatch,
    LogAnalysisRequest,
    WorkflowHandoffSignal,
)
from tianhai.workflows import INCIDENT_WORKFLOW_ID, TianHaiIncidentWorkflow


def test_incident_workflow_uses_agno_workflow_contract() -> None:
    workflow = TianHaiIncidentWorkflow()

    assert isinstance(workflow, Workflow)
    assert workflow.id == INCIDENT_WORKFLOW_ID
    assert workflow.input_schema is IncidentWorkflowRequest
    assert len(workflow.steps) == 2
    assert all(step.agent is None for step in workflow.steps)
    assert all(step.team is None for step in workflow.steps)


def test_incident_workflow_run_records_execution_state() -> None:
    workflow = TianHaiIncidentWorkflow()
    incident = workflow.create_incident(
        request=_request(),
        handoff=WorkflowHandoffSignal(reason="Needs durable investigation."),
        incident_id="inc-run",
    )

    response = workflow.run_incident(
        incident,
        run_id="run-inc-run",
        session_id="session-inc-run",
    )

    assert isinstance(response, WorkflowRunOutput)
    assert isinstance(response.content, IncidentWorkflowResult)
    assert response.run_id == "run-inc-run"
    assert response.content.incident.status == IncidentStatus.RUNNING
    assert response.content.execution_state.run_id == "run-inc-run"
    assert response.content.execution_state.session_id == "session-inc-run"
    assert response.content.requires_continuation is False


def test_incident_workflow_records_missing_inputs_as_awaiting_continuation() -> None:
    workflow = TianHaiIncidentWorkflow()
    incident = workflow.create_incident(
        request=_request(),
        handoff=WorkflowHandoffSignal(
            reason="Needs database-side evidence.",
            missing_inputs=("database logs",),
        ),
        incident_id="inc-awaiting",
    )

    response = workflow.run_incident(
        incident,
        run_id="run-inc-awaiting",
        session_id="session-inc-awaiting",
    )

    assert isinstance(response, WorkflowRunOutput)
    assert isinstance(response.content, IncidentWorkflowResult)
    assert response.content.incident.status == IncidentStatus.AWAITING_CONTINUATION
    assert response.content.requires_continuation is True
    assert "Missing input: database logs" in response.content.next_actions


def test_incident_workflow_continue_records_continuation() -> None:
    workflow = TianHaiIncidentWorkflow()
    incident = workflow.create_incident(
        request=_request(),
        handoff=WorkflowHandoffSignal(
            reason="Needs database-side evidence.",
            missing_inputs=("database logs",),
        ),
        incident_id="inc-continue",
    )

    response = workflow.continue_incident(
        incident,
        IncidentContinuationRequest(
            reason="Added database logs.",
            additional_log_batch=JavaLogBatch(raw_excerpt="ERROR lock wait timeout"),
            resolved_missing_inputs=("database logs",),
        ),
        run_id="run-inc-continue",
        session_id="session-inc-continue",
    )

    assert isinstance(response, WorkflowRunOutput)
    assert isinstance(response.content, IncidentWorkflowResult)
    assert response.content.incident.status == IncidentStatus.RUNNING
    assert response.content.incident.execution.continuation_count == 1
    assert response.content.incident.continuations[0].reason == "Added database logs."
    assert response.content.requires_continuation is False


def test_incident_workflow_cancel_marks_record_without_client_api() -> None:
    workflow = TianHaiIncidentWorkflow()
    incident = workflow.create_incident(
        request=_request(),
        handoff=WorkflowHandoffSignal(reason="Needs durable investigation."),
        incident_id="inc-cancel",
    )

    cancelled = workflow.cancel_incident(
        incident,
        IncidentCancellationRequest(reason="Operator cancelled."),
        run_id="missing-run",
    )

    assert cancelled.status == IncidentStatus.CANCELLED
    assert cancelled.events[-1].details["workflow_cancelled"] == "False"


def _request() -> LogAnalysisRequest:
    return LogAnalysisRequest(
        question="Why is checkout failing?",
        log_batch=JavaLogBatch(raw_excerpt="ERROR java.sql.SQLTimeoutException"),
    )
