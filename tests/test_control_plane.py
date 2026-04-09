from agno.run.team import TeamRunOutput
from agno.run.workflow import WorkflowRunOutput

from tianhai.config import TianHaiSettings
from tianhai.control import (
    IncidentApprovalDecision,
    IncidentApprovalStatus,
    IncidentControlAction,
    IncidentControlState,
    TianHaiIncidentControlPlane,
)
from tianhai.domain import (
    DiagnosisFinding,
    IncidentCancellationRequest,
    IncidentStatus,
    KnowledgeEvidence,
    KnowledgeSourceType,
    LogAnalysisRequest,
    LogEvidence,
    LogSeverity,
    WorkflowHandoffSignal,
    WorkflowHandoffUrgency,
)
from tianhai.domain.logs import JavaLogBatch
from tianhai.runtime import create_db
from tianhai.teams import JavaLogAnalysisTeamInput, JavaLogAnalysisTeamResult
from tianhai.workflows import TianHaiIncidentWorkflow


def test_control_plane_reports_pending_high_risk_approval() -> None:
    log_analysis_team = FakeLogAnalysisTeam()
    workflow = TianHaiIncidentWorkflow(
        db=_db(),
        log_analysis_team=log_analysis_team,
        knowledge_base=FakeKnowledgeBase(),
    )
    control_plane = TianHaiIncidentControlPlane(workflow=workflow)
    incident = workflow.create_incident(
        request=_request(),
        handoff=WorkflowHandoffSignal(
            reason="Critical checkout incident needs deeper investigation.",
            urgency=WorkflowHandoffUrgency.CRITICAL,
        ),
        incident_id="inc-control-pending",
    )

    paused = workflow.run_incident(
        incident,
        run_id="run-control-pending",
        session_id="session-control-pending",
    )

    assert isinstance(paused, WorkflowRunOutput)
    assert paused.is_paused is True
    assert log_analysis_team.inputs == []

    snapshot = control_plane.snapshot(incident, run_response=paused)

    assert snapshot.control_state == IncidentControlState.AWAITING_APPROVAL
    assert snapshot.approval_status == IncidentApprovalStatus.PENDING
    assert snapshot.available_actions == (
        IncidentControlAction.APPROVAL,
        IncidentControlAction.CANCELLATION,
    )
    assert snapshot.high_risk_assessment.requires_approval is True
    assert "severity 'critical'" in snapshot.high_risk_assessment.reasons[0]


def test_control_plane_approval_then_continue_completes_incident() -> None:
    log_analysis_team = FakeLogAnalysisTeam()
    workflow = TianHaiIncidentWorkflow(
        db=_db(),
        log_analysis_team=log_analysis_team,
        knowledge_base=FakeKnowledgeBase(),
    )
    control_plane = TianHaiIncidentControlPlane(workflow=workflow)
    incident = workflow.create_incident(
        request=_request(),
        handoff=WorkflowHandoffSignal(
            reason="Critical checkout incident needs deeper investigation.",
            urgency=WorkflowHandoffUrgency.CRITICAL,
        ),
        incident_id="inc-control-continue",
    )

    paused = workflow.run_incident(
        incident,
        run_id="run-control-continue",
        session_id="session-control-continue",
    )
    approved = control_plane.approve_pending_run(
        paused,
        IncidentApprovalDecision(
            approved=True,
            reviewed_by="operator-1",
            note="Approval granted for high-risk analysis.",
        ),
    )
    approved_snapshot = control_plane.snapshot(incident, run_response=approved)
    continued = control_plane.continue_paused_execution(run_response=approved)

    assert approved_snapshot.control_state == IncidentControlState.PAUSED
    assert approved_snapshot.approval_status == IncidentApprovalStatus.APPROVED
    assert approved_snapshot.available_actions == (
        IncidentControlAction.CONTINUE,
        IncidentControlAction.CANCELLATION,
    )
    assert isinstance(continued, WorkflowRunOutput)
    assert continued.content.incident.status == IncidentStatus.COMPLETED
    assert log_analysis_team.inputs[0].incident_id == "inc-control-continue"


def test_control_plane_rejection_then_cancellation_marks_incident() -> None:
    workflow = TianHaiIncidentWorkflow(
        db=_db(),
        log_analysis_team=FakeLogAnalysisTeam(),
        knowledge_base=FakeKnowledgeBase(),
    )
    control_plane = TianHaiIncidentControlPlane(workflow=workflow)
    incident = workflow.create_incident(
        request=_request(),
        handoff=WorkflowHandoffSignal(
            reason="Critical checkout incident needs deeper investigation.",
            urgency=WorkflowHandoffUrgency.CRITICAL,
        ),
        incident_id="inc-control-cancel",
    )

    paused = workflow.run_incident(
        incident,
        run_id="run-control-cancel",
        session_id="session-control-cancel",
    )
    rejected = control_plane.reject_pending_run(
        paused,
        IncidentApprovalDecision(
            approved=False,
            reviewed_by="operator-2",
            note="Reject automated investigation escalation.",
        ),
    )
    rejected_snapshot = control_plane.snapshot(incident, run_response=rejected)
    cancelled_incident = control_plane.cancel_incident(
        incident,
        IncidentCancellationRequest(reason="High-risk approval rejected."),
        run_response=rejected,
    )

    assert rejected_snapshot.approval_status == IncidentApprovalStatus.REJECTED
    assert rejected_snapshot.available_actions == (IncidentControlAction.CANCELLATION,)
    assert cancelled_incident.status == IncidentStatus.CANCELLED


def _request() -> LogAnalysisRequest:
    return LogAnalysisRequest(
        question="Why is checkout failing?",
        log_batch=JavaLogBatch(raw_excerpt="ERROR java.sql.SQLTimeoutException"),
        constraints=("production",),
    )


def _db() -> object:
    return create_db(TianHaiSettings(sqlite_db_file=":memory:"))


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
    def retrieve_for_log_analysis(
        self,
        request: LogAnalysisRequest,
        *,
        max_results: int,
    ) -> object:
        assert request.question == "Why is checkout failing?"
        assert max_results == 5
        return FakeKnowledgeRetrievalResult()


class FakeKnowledgeRetrievalResult:
    @property
    def evidence(self) -> tuple[KnowledgeEvidence, ...]:
        return (
            KnowledgeEvidence(
                id="kb-checkout-runbook",
                summary="Checkout SQL timeouts can follow HikariCP saturation.",
                source_type=KnowledgeSourceType.JAVA_SERVICE_NOTES,
                title="Checkout runbook",
                excerpt="Check HikariCP pool saturation before retry settings.",
                source_uri="runbooks/checkout.md",
                service_name="checkout",
            ),
        )
