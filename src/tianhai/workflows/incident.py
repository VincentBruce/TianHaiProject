from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from agno.models.base import Model
from agno.run.base import RunContext
from agno.run.team import TeamRunOutput
from agno.run.workflow import WorkflowRunOutput, WorkflowRunOutputEvent
from agno.workflow import Step, StepInput, StepOutput, Workflow

from tianhai.domain import (
    IncidentCancellationRequest,
    IncidentContinuationRequest,
    IncidentRecord,
    IncidentStatus,
    IncidentWorkflowRequest,
    IncidentWorkflowResult,
    LogAnalysisRequest,
    WorkflowHandoffSignal,
    add_incident_continuation,
    cancel_incident,
    complete_incident,
    create_incident_record,
    fail_incident,
    mark_incident_awaiting_continuation,
    mark_incident_scope_recorded,
    start_incident_execution,
)
from tianhai.teams import (
    DEFAULT_JAVA_LOG_ANALYSIS_TEAM_MODEL,
    JavaLogAnalysisTeamResult,
    TianHaiJavaLogAnalysisTeam,
    build_java_log_analysis_team_input,
    incident_diagnosis_result_from_team_result,
)


INCIDENT_WORKFLOW_ID = "tianhai-incident-diagnosis-workflow"
INCIDENT_WORKFLOW_NAME = "TianHai Incident Diagnosis Workflow"
RECORD_EXECUTION_STEP_NAME = "record_incident_execution"
CONTINUATION_GATE_STEP_NAME = "record_continuation_gate"
JAVA_LOG_ANALYSIS_TEAM_STEP_NAME = "run_java_log_analysis_team"


class TianHaiIncidentWorkflow(Workflow):
    """Agno Workflow entrypoint for durable incident investigation intake."""

    def __init__(
        self,
        *,
        db: object | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        debug_mode: bool = False,
        log_analysis_team: object | None = None,
        java_log_team_model: Model | str | None = DEFAULT_JAVA_LOG_ANALYSIS_TEAM_MODEL,
    ) -> None:
        self.log_analysis_team = log_analysis_team or TianHaiJavaLogAnalysisTeam(
            model=java_log_team_model,
        )
        super().__init__(
            id=INCIDENT_WORKFLOW_ID,
            name=INCIDENT_WORKFLOW_NAME,
            description=(
                "Records TianHai incident workflow handoffs and runs bounded "
                "Java log analysis through an internal team."
            ),
            db=db,
            steps=[
                Step(
                    name=RECORD_EXECUTION_STEP_NAME,
                    executor=record_incident_execution,
                    description="Record incident workflow execution state.",
                    max_retries=0,
                ),
                Step(
                    name=CONTINUATION_GATE_STEP_NAME,
                    executor=record_continuation_gate,
                    description="Record whether the incident needs continuation input.",
                    max_retries=0,
                ),
                Step(
                    name=JAVA_LOG_ANALYSIS_TEAM_STEP_NAME,
                    executor=self.run_java_log_analysis_team,
                    description=(
                        "Run the workflow-internal Java log analysis team when "
                        "handoff inputs are complete."
                    ),
                    max_retries=0,
                ),
            ],
            input_schema=IncidentWorkflowRequest,
            session_id=session_id,
            user_id=user_id,
            debug_mode=debug_mode,
            telemetry=False,
        )

    def create_incident(
        self,
        *,
        request: LogAnalysisRequest,
        handoff: WorkflowHandoffSignal,
        incident_id: str | None = None,
    ) -> IncidentRecord:
        return create_incident_record(
            request=request,
            handoff=handoff,
            incident_id=incident_id,
        )

    def run_incident(
        self,
        incident: IncidentRecord,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        continuation: IncidentContinuationRequest | None = None,
    ) -> WorkflowRunOutput | Iterator[WorkflowRunOutputEvent]:
        return self.run(
            input=IncidentWorkflowRequest(
                incident=incident,
                continuation=continuation,
            ),
            run_id=run_id,
            session_id=session_id or incident.execution.session_id or incident.incident_id,
            user_id=user_id,
        )

    def cancel_incident(
        self,
        incident: IncidentRecord,
        cancellation: IncidentCancellationRequest,
        *,
        run_id: str | None = None,
    ) -> IncidentRecord:
        workflow_run_id = run_id or incident.execution.run_id
        workflow_cancelled: bool | None = None
        if workflow_run_id is not None:
            workflow_cancelled = self.cancel_run(workflow_run_id)
        return cancel_incident(
            incident,
            cancellation,
            workflow_cancelled=workflow_cancelled,
        )

    def continue_incident(
        self,
        incident: IncidentRecord,
        continuation: IncidentContinuationRequest,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> WorkflowRunOutput | Iterator[WorkflowRunOutputEvent]:
        return self.run_incident(
            incident,
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
            continuation=continuation,
        )

    def continue_paused_execution(
        self,
        *,
        run_id: str,
        session_id: str,
        **kwargs: Any,
    ) -> WorkflowRunOutput | Iterator[WorkflowRunOutputEvent]:
        return self.continue_run(
            run_id=run_id,
            session_id=session_id,
            **kwargs,
        )

    def run_java_log_analysis_team(
        self,
        step_input: StepInput,
        *,
        run_context: RunContext | None = None,
        session_state: dict[str, Any] | None = None,
    ) -> StepOutput:
        return execute_java_log_analysis_team_step(
            step_input,
            log_analysis_team=self.log_analysis_team,
            run_context=run_context,
            session_state=session_state,
        )


def record_incident_execution(
    step_input: StepInput,
    *,
    run_context: RunContext | None = None,
    session_state: dict[str, Any] | None = None,
) -> StepOutput:
    workflow_request = _coerce_workflow_request(step_input.input)
    incident = workflow_request.incident
    if workflow_request.continuation is not None:
        incident = add_incident_continuation(
            incident,
            workflow_request.continuation,
        )

    incident = start_incident_execution(
        incident,
        workflow_id=run_context.workflow_id if run_context else None,
        workflow_name=run_context.workflow_name if run_context else None,
        run_id=run_context.run_id if run_context else None,
        session_id=run_context.session_id if run_context else None,
    )
    incident = mark_incident_scope_recorded(incident)
    _write_incident_session_state(session_state, incident)

    return StepOutput(
        step_name=RECORD_EXECUTION_STEP_NAME,
        content=incident,
        success=True,
    )


def record_continuation_gate(
    step_input: StepInput,
    *,
    session_state: dict[str, Any] | None = None,
) -> StepOutput:
    incident = _coerce_incident_record(step_input.previous_step_content)
    missing_inputs = _remaining_missing_inputs(incident)
    requires_continuation = bool(missing_inputs)
    if requires_continuation:
        incident = mark_incident_awaiting_continuation(
            incident,
            missing_inputs=missing_inputs,
            message="Incident workflow is awaiting handoff continuation input.",
        )

    result = IncidentWorkflowResult(
        incident=incident,
        summary=_result_summary(incident, requires_continuation),
        execution_state=incident.execution,
        requires_continuation=requires_continuation,
        next_actions=_next_actions(incident, missing_inputs),
        limitations=_limitations(incident),
    )
    _write_incident_session_state(session_state, incident)

    return StepOutput(
        step_name=CONTINUATION_GATE_STEP_NAME,
        content=result,
        success=True,
    )


def execute_java_log_analysis_team_step(
    step_input: StepInput,
    *,
    log_analysis_team: object,
    run_context: RunContext | None = None,
    session_state: dict[str, Any] | None = None,
) -> StepOutput:
    workflow_result = _coerce_incident_workflow_result(
        step_input.previous_step_content,
    )
    incident = workflow_result.incident
    if workflow_result.requires_continuation:
        _write_incident_session_state(session_state, incident)
        return StepOutput(
            step_name=JAVA_LOG_ANALYSIS_TEAM_STEP_NAME,
            content=workflow_result,
            success=True,
        )

    try:
        team_input = build_java_log_analysis_team_input(incident)
        team_response = log_analysis_team.run(
            input=team_input,
            run_id=_team_run_id(run_context),
            session_id=incident.execution.session_id,
            user_id=run_context.user_id if run_context else None,
        )
        team_result = _coerce_java_log_analysis_team_result(
            _team_response_content(team_response),
        )
        diagnosis_result = incident_diagnosis_result_from_team_result(team_result)
        incident = complete_incident(incident, diagnosis_result)
        result = IncidentWorkflowResult(
            incident=incident,
            summary=team_result.summary,
            execution_state=incident.execution,
            requires_continuation=False,
            next_actions=team_result.recommended_actions,
            limitations=team_result.limitations,
        )
    except Exception as exc:
        incident = fail_incident(
            incident,
            error=f"Java log analysis team failed: {exc}",
        )
        result = IncidentWorkflowResult(
            incident=incident,
            summary="Incident workflow failed while running Java log analysis team.",
            execution_state=incident.execution,
            requires_continuation=False,
            next_actions=("Inspect the team failure and retry inside the workflow.",),
            limitations=(
                "The Java log analysis team did not produce a valid bounded report.",
            ),
        )

    _write_incident_session_state(session_state, incident)
    return StepOutput(
        step_name=JAVA_LOG_ANALYSIS_TEAM_STEP_NAME,
        content=result,
        success=True,
    )


def _coerce_workflow_request(value: object) -> IncidentWorkflowRequest:
    if isinstance(value, IncidentWorkflowRequest):
        return value
    return IncidentWorkflowRequest.model_validate(value)


def _coerce_incident_record(value: object) -> IncidentRecord:
    if isinstance(value, IncidentRecord):
        return value
    return IncidentRecord.model_validate(value)


def _coerce_incident_workflow_result(value: object) -> IncidentWorkflowResult:
    if isinstance(value, IncidentWorkflowResult):
        return value
    return IncidentWorkflowResult.model_validate(value)


def _coerce_java_log_analysis_team_result(
    value: object,
) -> JavaLogAnalysisTeamResult:
    if isinstance(value, JavaLogAnalysisTeamResult):
        return value
    return JavaLogAnalysisTeamResult.model_validate(value)


def _team_response_content(value: object) -> object:
    if isinstance(value, TeamRunOutput):
        return value.content
    raise TypeError("Java log analysis team returned a streaming response")


def _team_run_id(run_context: RunContext | None) -> str | None:
    if run_context is None or run_context.run_id is None:
        return None
    return f"{run_context.run_id}-{JAVA_LOG_ANALYSIS_TEAM_STEP_NAME}"


def _write_incident_session_state(
    session_state: dict[str, Any] | None,
    incident: IncidentRecord,
) -> None:
    if session_state is None:
        return
    session_state["tianhai_incident_id"] = incident.incident_id
    session_state["tianhai_incident_status"] = incident.status.value
    session_state["tianhai_incident_phase"] = incident.execution.phase.value
    session_state["tianhai_incident_continuation_count"] = (
        incident.execution.continuation_count
    )


def _result_summary(
    incident: IncidentRecord,
    requires_continuation: bool,
) -> str:
    if requires_continuation:
        return (
            "Incident workflow recorded the handoff and is waiting for "
            "continuation input."
        )
    if incident.status == IncidentStatus.RUNNING:
        return "Incident workflow recorded the durable investigation scope."
    return f"Incident workflow recorded status {incident.status.value}."


def _next_actions(
    incident: IncidentRecord,
    missing_inputs: tuple[str, ...],
) -> tuple[str, ...]:
    if missing_inputs:
        return (
            "Provide the missing handoff inputs before deeper investigation.",
            *tuple(f"Missing input: {item}" for item in missing_inputs),
        )
    return ("Keep the incident active for bounded downstream investigation.",)


def _remaining_missing_inputs(incident: IncidentRecord) -> tuple[str, ...]:
    resolved = {
        item
        for continuation in incident.continuations
        for item in continuation.resolved_missing_inputs
    }
    return tuple(item for item in incident.handoff.missing_inputs if item not in resolved)


def _limitations(incident: IncidentRecord) -> tuple[str, ...]:
    limitations = (
        "This workflow records incident lifecycle and execution state only.",
        "No team collaboration, memory, knowledge retrieval, RAG, search, "
        "or client API is invoked.",
    )
    if incident.continuations:
        return limitations + ("Continuation input was recorded for this incident.",)
    return limitations
