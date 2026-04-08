from agno.run.team import TeamRunOutput
from agno.run.workflow import WorkflowRunOutput
from agno.workflow import Workflow

from tianhai.domain import (
    DiagnosisFinding,
    IncidentCancellationRequest,
    IncidentContinuationRequest,
    IncidentStatus,
    IncidentWorkflowRequest,
    IncidentWorkflowResult,
    JavaLogBatch,
    LogAnalysisRequest,
    LogEvidence,
    LogSeverity,
    WorkflowHandoffSignal,
)
from tianhai.teams import JavaLogAnalysisTeamInput, JavaLogAnalysisTeamResult
from tianhai.workflows import (
    INCIDENT_WORKFLOW_ID,
    JAVA_LOG_ANALYSIS_TEAM_STEP_NAME,
    TianHaiIncidentWorkflow,
)


def test_incident_workflow_uses_agno_workflow_contract() -> None:
    workflow = TianHaiIncidentWorkflow()

    assert isinstance(workflow, Workflow)
    assert workflow.id == INCIDENT_WORKFLOW_ID
    assert workflow.input_schema is IncidentWorkflowRequest
    assert len(workflow.steps) == 3
    assert workflow.steps[-1].name == JAVA_LOG_ANALYSIS_TEAM_STEP_NAME
    assert all(step.agent is None for step in workflow.steps)
    assert all(step.team is None for step in workflow.steps)


def test_incident_workflow_run_records_execution_state() -> None:
    log_analysis_team = FakeLogAnalysisTeam()
    workflow = TianHaiIncidentWorkflow(log_analysis_team=log_analysis_team)
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
    assert response.content.incident.status == IncidentStatus.COMPLETED
    assert response.content.execution_state.run_id == "run-inc-run"
    assert response.content.execution_state.session_id == "session-inc-run"
    assert response.content.requires_continuation is False
    assert response.content.incident.diagnosis_result is not None
    assert response.content.incident.diagnosis_result.findings[0].evidence_ids == (
        "ev-timeout",
    )
    assert log_analysis_team.inputs[0].incident_id == "inc-run"
    assert log_analysis_team.inputs[0].workflow_run_id == "run-inc-run"


def test_incident_workflow_records_missing_inputs_as_awaiting_continuation() -> None:
    log_analysis_team = FakeLogAnalysisTeam()
    workflow = TianHaiIncidentWorkflow(log_analysis_team=log_analysis_team)
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
    assert log_analysis_team.inputs == []


def test_incident_workflow_continue_records_continuation() -> None:
    log_analysis_team = FakeLogAnalysisTeam()
    workflow = TianHaiIncidentWorkflow(log_analysis_team=log_analysis_team)
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
    assert response.content.incident.status == IncidentStatus.COMPLETED
    assert response.content.incident.execution.continuation_count == 1
    assert response.content.incident.continuations[0].reason == "Added database logs."
    assert response.content.requires_continuation is False
    assert log_analysis_team.inputs[0].resolved_missing_inputs == ("database logs",)
    assert log_analysis_team.inputs[0].continuation_log_batches[0].raw_excerpt == (
        "ERROR lock wait timeout"
    )


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


class FakeLogAnalysisTeam:
    def __init__(self) -> None:
        self.inputs: list[JavaLogAnalysisTeamInput] = []

    def run(
        self,
        input: JavaLogAnalysisTeamInput,
        **_: object,
    ) -> TeamRunOutput:
        self.inputs.append(input)
        return TeamRunOutput(
            content=JavaLogAnalysisTeamResult(
                summary="The supplied logs point to a Java SQL timeout.",
                findings=(
                    DiagnosisFinding(
                        title="SQL timeout",
                        detail="The current incident logs contain a SQL timeout.",
                        severity=LogSeverity.ERROR,
                        evidence_ids=("ev-timeout",),
                    ),
                ),
                evidence=(
                    LogEvidence(
                        id="ev-timeout",
                        summary="SQL timeout in supplied log excerpt.",
                        log_excerpt="ERROR java.sql.SQLTimeoutException",
                        severity=LogSeverity.ERROR,
                    ),
                ),
                recommended_actions=("Inspect database latency and pool usage.",),
                limitations=("Only current incident logs were used.",),
            )
        )
