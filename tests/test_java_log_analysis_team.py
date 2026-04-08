from agno.team import Team
from agno.team.mode import TeamMode

from tianhai.domain import (
    IncidentContinuationRequest,
    IncidentStatus,
    JavaLogBatch,
    KnowledgeEvidence,
    KnowledgeSourceType,
    LogAnalysisRequest,
    WorkflowHandoffSignal,
    add_incident_continuation,
    create_incident_record,
)
from tianhai.teams import (
    JAVA_LOG_ANALYSIS_TEAM_ID,
    JavaLogAnalysisTeamInput,
    JavaLogAnalysisTeamResult,
    TianHaiJavaLogAnalysisTeam,
    build_java_log_analysis_team_input,
    incident_diagnosis_result_from_team_result,
)


def test_java_log_analysis_team_uses_bounded_agno_team_contract() -> None:
    team = TianHaiJavaLogAnalysisTeam()

    assert isinstance(team, Team)
    assert team.id == JAVA_LOG_ANALYSIS_TEAM_ID
    assert team.mode == TeamMode.coordinate
    assert team.input_schema is JavaLogAnalysisTeamInput
    assert team.output_schema is JavaLogAnalysisTeamResult
    assert team.parse_response is True
    assert team.tools == []
    assert team.add_knowledge_to_context is False
    assert team.add_history_to_context is False
    assert team.enable_agentic_memory is False
    assert len(team.members) == 4
    assert all(member.tools == [] for member in team.members)


def test_java_log_analysis_team_input_uses_only_incident_context() -> None:
    incident = create_incident_record(
        request=LogAnalysisRequest(
            question="Why is checkout failing?",
            log_batch=JavaLogBatch(raw_excerpt="ERROR checkout timed out"),
            service_context="checkout service",
            constraints=("Use only supplied logs.",),
        ),
        handoff=WorkflowHandoffSignal(
            reason="Needs durable investigation.",
            missing_inputs=("database logs",),
        ),
        incident_id="inc-team-input",
    )
    incident = add_incident_continuation(
        incident,
        IncidentContinuationRequest(
            reason="Added database logs.",
            additional_log_batch=JavaLogBatch(raw_excerpt="ERROR lock wait timeout"),
            operator_notes="Database pool was saturated.",
            resolved_missing_inputs=("database logs",),
            constraints=("Do not infer upstream service state.",),
        ),
    )

    knowledge_evidence = (
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

    team_input = build_java_log_analysis_team_input(
        incident,
        knowledge_evidence=knowledge_evidence,
    )

    assert team_input.incident_id == "inc-team-input"
    assert team_input.question == "Why is checkout failing?"
    assert team_input.log_batch.raw_excerpt == "ERROR checkout timed out"
    assert team_input.continuation_log_batches[0].raw_excerpt == (
        "ERROR lock wait timeout"
    )
    assert team_input.continuation_notes == (
        "Added database logs.",
        "Database pool was saturated.",
    )
    assert team_input.resolved_missing_inputs == ("database logs",)
    assert team_input.constraints == (
        "Use only supplied logs.",
        "Do not infer upstream service state.",
    )
    assert team_input.knowledge_evidence == knowledge_evidence


def test_team_result_maps_to_completed_incident_diagnosis_result() -> None:
    knowledge_evidence = (
        KnowledgeEvidence(
            id="kb-known-issue-sql-timeout",
            summary="Known issue for SQL timeout triage.",
            source_type=KnowledgeSourceType.KNOWN_ISSUES,
            title="SQL timeout known issue",
        ),
    )
    diagnosis_result = incident_diagnosis_result_from_team_result(
        JavaLogAnalysisTeamResult(
            summary="The supplied logs point to a database lock timeout.",
            knowledge_evidence=knowledge_evidence,
            recommended_actions=("Inspect database lock contention.",),
            limitations=("Only supplied incident logs were used.",),
        )
    )

    assert diagnosis_result.status == IncidentStatus.COMPLETED
    assert diagnosis_result.summary == (
        "The supplied logs point to a database lock timeout."
    )
    assert diagnosis_result.knowledge_evidence == knowledge_evidence
    assert diagnosis_result.requires_continuation is False
