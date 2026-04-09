import threading
import time

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
    KnowledgeEvidence,
    KnowledgeSourceType,
    LogAnalysisRequest,
    LogEvidence,
    LogSeverity,
    WorkflowHandoffSignal,
)
from tianhai.teams import JavaLogAnalysisTeamInput, JavaLogAnalysisTeamResult
from tianhai.workflows import (
    INCIDENT_WORKFLOW_ID,
    HIGH_RISK_APPROVAL_STEP_NAME,
    JAVA_LOG_ANALYSIS_TEAM_STEP_NAME,
    TianHaiIncidentWorkflow,
)


def test_incident_workflow_uses_agno_workflow_contract() -> None:
    workflow = TianHaiIncidentWorkflow()

    assert isinstance(workflow, Workflow)
    assert workflow.id == INCIDENT_WORKFLOW_ID
    assert workflow.input_schema is IncidentWorkflowRequest
    assert len(workflow.steps) == 4
    assert workflow.steps[2].name == HIGH_RISK_APPROVAL_STEP_NAME
    assert workflow.steps[-1].name == JAVA_LOG_ANALYSIS_TEAM_STEP_NAME
    assert all(getattr(step, "agent", None) is None for step in workflow.steps)
    assert all(getattr(step, "team", None) is None for step in workflow.steps)


def test_incident_workflow_run_records_execution_state() -> None:
    log_analysis_team = FakeLogAnalysisTeam()
    knowledge_base = FakeKnowledgeBase()
    workflow = TianHaiIncidentWorkflow(
        log_analysis_team=log_analysis_team,
        knowledge_base=knowledge_base,
    )
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
    assert response.content.incident.diagnosis_result.knowledge_evidence == (
        _knowledge_evidence(),
    )
    assert log_analysis_team.inputs[0].incident_id == "inc-run"
    assert log_analysis_team.inputs[0].workflow_run_id == "run-inc-run"
    assert log_analysis_team.inputs[0].knowledge_evidence == (_knowledge_evidence(),)
    assert knowledge_base.max_results == [5]


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


def test_incident_workflow_pauses_high_risk_investigation_for_approval() -> None:
    log_analysis_team = FakeLogAnalysisTeam()
    workflow = TianHaiIncidentWorkflow(log_analysis_team=log_analysis_team)
    incident = workflow.create_incident(
        request=_request(),
        handoff=WorkflowHandoffSignal(
            reason="Critical incident needs bounded but operator-approved investigation.",
            urgency="critical",
        ),
        incident_id="inc-high-risk",
    )

    response = workflow.run_incident(
        incident,
        run_id="run-inc-high-risk",
        session_id="session-inc-high-risk",
    )

    assert isinstance(response, WorkflowRunOutput)
    assert response.is_paused is True
    assert response.paused_step_name == HIGH_RISK_APPROVAL_STEP_NAME
    assert response.steps_requiring_confirmation[0].step_name == HIGH_RISK_APPROVAL_STEP_NAME
    assert log_analysis_team.inputs == []


def test_incident_workflow_concurrent_high_and_low_risk_runs_do_not_pollute_approval_gate() -> None:
    barrier = threading.Barrier(2)
    log_analysis_team = FakeLogAnalysisTeam()
    workflow = TianHaiIncidentWorkflow(
        log_analysis_team=log_analysis_team,
        knowledge_base=FakeKnowledgeBase(),
    )
    original_executor = workflow.steps[0].active_executor

    def barriered_record_incident_execution(
        step_input,
        *,
        run_context=None,
        session_state=None,
    ):
        result = original_executor(
            step_input,
            run_context=run_context,
            session_state=session_state,
        )
        barrier.wait(timeout=2)
        return result

    workflow.steps[0].executor = barriered_record_incident_execution
    workflow.steps[0].active_executor = barriered_record_incident_execution

    high_risk_incident = workflow.create_incident(
        request=_request(constraints=("production",)),
        handoff=WorkflowHandoffSignal(
            reason="Critical incident requires approval before deeper investigation.",
            urgency="critical",
        ),
        incident_id="inc-concurrent-high",
    )
    low_risk_incident = workflow.create_incident(
        request=_request(),
        handoff=WorkflowHandoffSignal(
            reason="Bounded investigation without approval requirement.",
        ),
        incident_id="inc-concurrent-low",
    )

    results: dict[str, WorkflowRunOutput] = {}
    failures: list[BaseException] = []

    def run_named(name: str, incident) -> None:
        try:
            results[name] = workflow.run_incident(
                incident,
                run_id=f"run-{name}",
                session_id=f"session-{name}",
            )
        except BaseException as exc:  # pragma: no cover - test failure path
            failures.append(exc)

    high_thread = threading.Thread(
        target=run_named,
        args=("high", high_risk_incident),
    )
    low_thread = threading.Thread(
        target=run_named,
        args=("low", low_risk_incident),
    )

    high_thread.start()
    time.sleep(0.05)
    low_thread.start()
    high_thread.join(timeout=2)
    low_thread.join(timeout=2)

    assert failures == []
    assert high_thread.is_alive() is False
    assert low_thread.is_alive() is False
    assert results["high"].is_paused is True
    assert results["high"].paused_step_name == HIGH_RISK_APPROVAL_STEP_NAME
    assert results["low"].is_paused is False
    assert isinstance(results["low"].content, IncidentWorkflowResult)
    assert results["low"].content.incident.status == IncidentStatus.COMPLETED
    assert [entry.incident_id for entry in log_analysis_team.inputs] == [
        "inc-concurrent-low",
    ]


def _request(
    *,
    constraints: tuple[str, ...] = (),
) -> LogAnalysisRequest:
    return LogAnalysisRequest(
        question="Why is checkout failing?",
        log_batch=JavaLogBatch(raw_excerpt="ERROR java.sql.SQLTimeoutException"),
        constraints=constraints,
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
                knowledge_evidence=input.knowledge_evidence,
                recommended_actions=("Inspect database latency and pool usage.",),
                limitations=("Only current incident logs were used.",),
            )
        )


class FakeKnowledgeBase:
    def __init__(self) -> None:
        self.max_results: list[int] = []

    def retrieve_for_log_analysis(
        self,
        request: LogAnalysisRequest,
        *,
        max_results: int,
    ) -> object:
        self.max_results.append(max_results)
        assert request.question == "Why is checkout failing?"
        return FakeKnowledgeRetrievalResult()


class FakeKnowledgeRetrievalResult:
    @property
    def evidence(self) -> tuple[KnowledgeEvidence, ...]:
        return (_knowledge_evidence(),)


def _knowledge_evidence() -> KnowledgeEvidence:
    return KnowledgeEvidence(
        id="kb-checkout-runbook",
        summary="Checkout SQL timeouts can follow HikariCP saturation.",
        source_type=KnowledgeSourceType.JAVA_SERVICE_NOTES,
        title="Checkout runbook",
        excerpt="Check HikariCP pool saturation before retry settings.",
        source_uri="runbooks/checkout.md",
        service_name="checkout",
    )
