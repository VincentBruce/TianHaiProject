from __future__ import annotations

from agno.agent import Agent
from agno.models.base import Model
from agno.team import Team
from agno.team.mode import TeamMode
from pydantic import Field

from tianhai.domain import (
    DiagnosisFinding,
    IncidentDiagnosisResult,
    IncidentRecord,
    IncidentStatus,
    JavaLogBatch,
    KnowledgeEvidence,
    LogEvidence,
)
from tianhai.domain.logs import TianHaiDomainModel


JAVA_LOG_ANALYSIS_TEAM_ID = "tianhai-java-log-analysis-team"
JAVA_LOG_ANALYSIS_TEAM_NAME = "TianHai Java Log Analysis Team"
DEFAULT_JAVA_LOG_ANALYSIS_TEAM_MODEL = "openai:gpt-4o"

LOG_PARSER_AGENT_ID = "tianhai-log-parser-agent"
ERROR_ANALYSIS_AGENT_ID = "tianhai-error-analysis-agent"
EVIDENCE_GATHERING_AGENT_ID = "tianhai-evidence-gathering-agent"
REPORT_SYNTHESIS_AGENT_ID = "tianhai-report-synthesis-agent"


class JavaLogAnalysisTeamInput(TianHaiDomainModel):
    incident_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    log_batch: JavaLogBatch
    service_context: str | None = None
    constraints: tuple[str, ...] = ()
    handoff_reason: str = Field(min_length=1)
    continuation_log_batches: tuple[JavaLogBatch, ...] = ()
    continuation_notes: tuple[str, ...] = ()
    resolved_missing_inputs: tuple[str, ...] = ()
    knowledge_evidence: tuple[KnowledgeEvidence, ...] = ()
    workflow_run_id: str | None = None
    workflow_session_id: str | None = None


class JavaLogAnalysisTeamResult(TianHaiDomainModel):
    summary: str = Field(min_length=1)
    findings: tuple[DiagnosisFinding, ...] = ()
    evidence: tuple[LogEvidence, ...] = ()
    knowledge_evidence: tuple[KnowledgeEvidence, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


JAVA_LOG_ANALYSIS_TEAM_INSTRUCTIONS: tuple[str, ...] = (
    "You are TianHai's bounded Java log analysis team, invoked only inside "
    "the incident workflow.",
    "Use only JavaLogAnalysisTeamInput fields as evidence: the current "
    "request log batch, incident handoff reason, continuation log batches, "
    "continuation notes, resolved missing inputs, constraints, service "
    "context, workflow identifiers, and workflow-supplied knowledge_evidence.",
    "Treat knowledge_evidence as durable runbook or documentation context, not "
    "as user memory or log evidence.",
    "Do not use memory, perform additional knowledge retrieval, run RAG, call "
    "external search, use filesystem lookup, network calls, control-plane "
    "actions, or client APIs.",
    "Coordinate member work for log parsing, Java error analysis, evidence "
    "gathering, and final report synthesis.",
    "Create LogEvidence entries only from supplied logs or structured context. "
    "Every finding should cite evidence_ids when possible.",
    "When the supplied context is insufficient, keep the report bounded and "
    "record the uncertainty in limitations instead of inventing evidence.",
)


def build_java_log_analysis_team_input(
    incident: IncidentRecord,
    *,
    knowledge_evidence: tuple[KnowledgeEvidence, ...] = (),
) -> JavaLogAnalysisTeamInput:
    continuation_log_batches = tuple(
        continuation.additional_log_batch
        for continuation in incident.continuations
        if continuation.additional_log_batch is not None
    )
    continuation_notes = tuple(
        note
        for continuation in incident.continuations
        for note in (continuation.reason, continuation.operator_notes)
        if note
    )
    resolved_missing_inputs = tuple(
        item
        for continuation in incident.continuations
        for item in continuation.resolved_missing_inputs
    )
    continuation_constraints = tuple(
        constraint
        for continuation in incident.continuations
        for constraint in continuation.constraints
    )

    return JavaLogAnalysisTeamInput(
        incident_id=incident.incident_id,
        question=incident.request.question,
        log_batch=incident.request.log_batch,
        service_context=incident.request.service_context,
        constraints=incident.request.constraints + continuation_constraints,
        handoff_reason=incident.handoff.reason,
        continuation_log_batches=continuation_log_batches,
        continuation_notes=continuation_notes,
        resolved_missing_inputs=resolved_missing_inputs,
        knowledge_evidence=knowledge_evidence,
        workflow_run_id=incident.execution.run_id,
        workflow_session_id=incident.execution.session_id,
    )


def incident_diagnosis_result_from_team_result(
    team_result: JavaLogAnalysisTeamResult,
) -> IncidentDiagnosisResult:
    return IncidentDiagnosisResult(
        summary=team_result.summary,
        status=IncidentStatus.COMPLETED,
        findings=team_result.findings,
        evidence=team_result.evidence,
        knowledge_evidence=team_result.knowledge_evidence,
        recommended_actions=team_result.recommended_actions,
        limitations=team_result.limitations,
        requires_continuation=False,
    )


class TianHaiJavaLogAnalysisTeam(Team):
    """Bounded Agno Team for workflow-scoped Java log analysis."""

    def __init__(
        self,
        *,
        model: Model | str | None = DEFAULT_JAVA_LOG_ANALYSIS_TEAM_MODEL,
        db: object | None = None,
    ) -> None:
        super().__init__(
            id=JAVA_LOG_ANALYSIS_TEAM_ID,
            name=JAVA_LOG_ANALYSIS_TEAM_NAME,
            model=model,
            db=db,
            mode=TeamMode.coordinate,
            members=list(_build_team_members()),
            description=(
                "Workflow-internal TianHai team for Java log parsing, error "
                "analysis, evidence gathering, and report synthesis."
            ),
            instructions=list(JAVA_LOG_ANALYSIS_TEAM_INSTRUCTIONS),
            input_schema=JavaLogAnalysisTeamInput,
            output_schema=JavaLogAnalysisTeamResult,
            parse_response=True,
            tools=[],
            add_knowledge_to_context=False,
            search_knowledge=False,
            add_search_knowledge_instructions=False,
            add_history_to_context=False,
            read_chat_history=False,
            store_history_messages=False,
            add_team_history_to_members=False,
            enable_agentic_memory=False,
            update_memory_on_run=False,
            enable_user_memories=False,
            add_memories_to_context=False,
            learning=False,
            add_learnings_to_context=False,
            store_member_responses=True,
            telemetry=False,
        )


def _build_team_members() -> tuple[Agent, ...]:
    return (
        _team_member(
            agent_id=LOG_PARSER_AGENT_ID,
            name="TianHai Log Parser",
            role=(
                "Parse supplied Java log entries and raw excerpts into "
                "timestamp, severity, logger, thread, exception, and stack "
                "trace observations."
            ),
        ),
        _team_member(
            agent_id=ERROR_ANALYSIS_AGENT_ID,
            name="TianHai Error Analyst",
            role=(
                "Analyze Java exception chains, stack frames, severity, and "
                "message patterns from the supplied incident context."
            ),
        ),
        _team_member(
            agent_id=EVIDENCE_GATHERING_AGENT_ID,
            name="TianHai Evidence Gatherer",
            role=(
                "Gather evidence only from the supplied logs and structured "
                "incident context, and connect findings to evidence ids."
            ),
        ),
        _team_member(
            agent_id=REPORT_SYNTHESIS_AGENT_ID,
            name="TianHai Report Synthesizer",
            role=(
                "Synthesize a bounded diagnosis report with findings, "
                "evidence, recommended actions, and limitations."
            ),
        ),
    )


def _team_member(*, agent_id: str, name: str, role: str) -> Agent:
    return Agent(
        id=agent_id,
        name=name,
        role=role,
        instructions=[
            "Stay inside the JavaLogAnalysisTeamInput evidence boundary.",
            "Do not use tools, memory, additional knowledge retrieval, RAG, search, "
            "filesystem lookup, network calls, control-plane actions, or "
            "client APIs.",
            "If the provided logs and context are insufficient, state the "
            "limitation instead of inventing evidence.",
        ],
        tools=[],
        add_knowledge_to_context=False,
        search_knowledge=False,
        add_search_knowledge_instructions=False,
        add_history_to_context=False,
        read_chat_history=False,
        enable_agentic_memory=False,
        update_memory_on_run=False,
        enable_user_memories=False,
        add_memories_to_context=False,
        learning=False,
        add_learnings_to_context=False,
        telemetry=False,
    )


__all__ = (
    "DEFAULT_JAVA_LOG_ANALYSIS_TEAM_MODEL",
    "ERROR_ANALYSIS_AGENT_ID",
    "EVIDENCE_GATHERING_AGENT_ID",
    "JAVA_LOG_ANALYSIS_TEAM_ID",
    "JAVA_LOG_ANALYSIS_TEAM_INSTRUCTIONS",
    "JAVA_LOG_ANALYSIS_TEAM_NAME",
    "JavaLogAnalysisTeamInput",
    "JavaLogAnalysisTeamResult",
    "LOG_PARSER_AGENT_ID",
    "REPORT_SYNTHESIS_AGENT_ID",
    "TianHaiJavaLogAnalysisTeam",
    "build_java_log_analysis_team_input",
    "incident_diagnosis_result_from_team_result",
)
