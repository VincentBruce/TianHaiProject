from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from agno.run.base import RunContext
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
    create_incident_record,
    mark_incident_awaiting_continuation,
    mark_incident_scope_recorded,
    start_incident_execution,
)


INCIDENT_WORKFLOW_ID = "tianhai-incident-diagnosis-workflow"
INCIDENT_WORKFLOW_NAME = "TianHai Incident Diagnosis Workflow"
RECORD_EXECUTION_STEP_NAME = "record_incident_execution"
CONTINUATION_GATE_STEP_NAME = "record_continuation_gate"


class TianHaiIncidentWorkflow(Workflow):
    """Agno Workflow entrypoint for durable incident investigation intake."""

    def __init__(
        self,
        *,
        db: object | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        debug_mode: bool = False,
    ) -> None:
        super().__init__(
            id=INCIDENT_WORKFLOW_ID,
            name=INCIDENT_WORKFLOW_NAME,
            description="Records TianHai incident workflow handoffs and execution state.",
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


def _coerce_workflow_request(value: object) -> IncidentWorkflowRequest:
    if isinstance(value, IncidentWorkflowRequest):
        return value
    return IncidentWorkflowRequest.model_validate(value)


def _coerce_incident_record(value: object) -> IncidentRecord:
    if isinstance(value, IncidentRecord):
        return value
    return IncidentRecord.model_validate(value)


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
