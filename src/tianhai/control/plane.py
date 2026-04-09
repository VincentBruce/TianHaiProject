from __future__ import annotations

from copy import deepcopy

from agno.run.base import RunStatus
from agno.run.workflow import WorkflowRunOutput
from agno.workflow.types import StepRequirement

from tianhai.control.policy import assess_incident_high_risk
from tianhai.control.types import (
    IncidentApprovalDecision,
    IncidentApprovalStatus,
    IncidentControlAction,
    IncidentControlCapability,
    IncidentControlSnapshot,
    IncidentControlState,
)
from tianhai.domain import IncidentCancellationRequest, IncidentRecord, IncidentStatus


class TianHaiIncidentControlPlane:
    """Internal control-plane service for incident approval and run control."""

    def __init__(self, *, workflow: object) -> None:
        self.workflow = workflow

    def assess_high_risk(self, incident: IncidentRecord):
        return assess_incident_high_risk(incident)

    def snapshot(
        self,
        incident: IncidentRecord,
        *,
        run_response: WorkflowRunOutput | None = None,
    ) -> IncidentControlSnapshot:
        high_risk = self.assess_high_risk(incident)
        approval_requirement = self._first_confirmation_requirement(run_response)
        approval_status = self._approval_status(run_response, high_risk.requires_approval)
        control_state = self._control_state(
            incident,
            run_response=run_response,
            approval_status=approval_status,
        )
        capabilities = self._capabilities(
            incident,
            control_state=control_state,
            approval_status=approval_status,
            high_risk_required=high_risk.requires_approval,
            run_response=run_response,
        )

        return IncidentControlSnapshot(
            incident_id=incident.incident_id,
            run_id=(run_response.run_id if run_response is not None else incident.execution.run_id),
            session_id=(
                run_response.session_id
                if run_response is not None
                else incident.execution.session_id
            ),
            control_state=control_state,
            approval_status=approval_status,
            paused_step_name=(
                approval_requirement.step_name
                if approval_requirement is not None
                else (run_response.paused_step_name if run_response is not None else None)
            ),
            paused_step_type=(
                str(approval_requirement.step_type)
                if approval_requirement is not None and approval_requirement.step_type is not None
                else None
            ),
            paused_message=(
                approval_requirement.confirmation_message
                if approval_requirement is not None
                else None
            ),
            high_risk_assessment=high_risk,
            supported_capabilities=capabilities,
            available_actions=tuple(
                capability.action
                for capability in capabilities
                if capability.available
            ),
        )

    def approve_pending_run(
        self,
        run_response: WorkflowRunOutput,
        decision: IncidentApprovalDecision,
    ) -> WorkflowRunOutput:
        if not decision.approved:
            raise ValueError("approve_pending_run requires approved=True")
        return self._resolve_pending_confirmation(run_response, confirmed=True)

    def reject_pending_run(
        self,
        run_response: WorkflowRunOutput,
        decision: IncidentApprovalDecision,
    ) -> WorkflowRunOutput:
        if decision.approved:
            raise ValueError("reject_pending_run requires approved=False")
        return self._resolve_pending_confirmation(run_response, confirmed=False)

    def continue_paused_execution(
        self,
        *,
        run_response: WorkflowRunOutput | None = None,
        run_id: str | None = None,
        session_id: str | None = None,
        step_requirements: list[StepRequirement] | None = None,
    ):
        workflow_continue = getattr(self.workflow, "continue_paused_execution")
        return workflow_continue(
            run_response=run_response,
            run_id=run_id,
            session_id=session_id,
            step_requirements=step_requirements,
        )

    def cancel_incident(
        self,
        incident: IncidentRecord,
        cancellation: IncidentCancellationRequest,
        *,
        run_response: WorkflowRunOutput | None = None,
        run_id: str | None = None,
    ) -> IncidentRecord:
        cancelled_run_id = run_id
        if run_response is not None:
            cancelled_run_id = cancelled_run_id or run_response.run_id
            paused_resolution = self._maybe_reject_pending_confirmation(run_response)
            if paused_resolution is not None or (
                run_response.is_paused
                and self._approval_status(
                    run_response,
                    high_risk_required=False,
                )
                == IncidentApprovalStatus.REJECTED
            ):
                try:
                    self.continue_paused_execution(
                        run_response=paused_resolution or deepcopy(run_response)
                    )
                except Exception:
                    pass

        workflow_cancel = getattr(self.workflow, "cancel_incident")
        return workflow_cancel(
            incident,
            cancellation,
            run_id=cancelled_run_id,
        )

    def _resolve_pending_confirmation(
        self,
        run_response: WorkflowRunOutput,
        *,
        confirmed: bool,
    ) -> WorkflowRunOutput:
        resolved = deepcopy(run_response)
        requirement = self._first_confirmation_requirement(resolved)
        if requirement is None:
            raise ValueError("workflow run has no pending approval requirement")
        if confirmed:
            requirement.confirm()
        else:
            requirement.reject()
        return resolved

    def _maybe_reject_pending_confirmation(
        self,
        run_response: WorkflowRunOutput,
    ) -> WorkflowRunOutput | None:
        requirement = self._first_confirmation_requirement(run_response)
        if requirement is None:
            return None
        return self._resolve_pending_confirmation(run_response, confirmed=False)

    def _first_confirmation_requirement(
        self,
        run_response: WorkflowRunOutput | None,
    ) -> StepRequirement | None:
        if run_response is None:
            return None
        for requirement in run_response.active_step_requirements:
            if requirement.needs_confirmation:
                return requirement
        return None

    def _approval_status(
        self,
        run_response: WorkflowRunOutput | None,
        high_risk_required: bool,
    ) -> IncidentApprovalStatus:
        if run_response is None:
            return (
                IncidentApprovalStatus.NOT_REQUIRED
                if not high_risk_required
                else IncidentApprovalStatus.NOT_REQUIRED
            )

        if self._first_confirmation_requirement(run_response) is not None:
            return IncidentApprovalStatus.PENDING

        for requirement in run_response.step_requirements or []:
            if requirement.requires_confirmation and requirement.confirmed is True:
                return IncidentApprovalStatus.APPROVED
            if requirement.requires_confirmation and requirement.confirmed is False:
                return IncidentApprovalStatus.REJECTED

        return (
            IncidentApprovalStatus.NOT_REQUIRED
            if not high_risk_required
            else IncidentApprovalStatus.NOT_REQUIRED
        )

    def _control_state(
        self,
        incident: IncidentRecord,
        *,
        run_response: WorkflowRunOutput | None,
        approval_status: IncidentApprovalStatus,
    ) -> IncidentControlState:
        if incident.status == IncidentStatus.COMPLETED:
            return IncidentControlState.COMPLETED
        if incident.status == IncidentStatus.CANCELLED:
            return IncidentControlState.CANCELLED
        if incident.status == IncidentStatus.FAILED:
            return IncidentControlState.FAILED
        if approval_status == IncidentApprovalStatus.PENDING:
            return IncidentControlState.AWAITING_APPROVAL
        if run_response is not None and run_response.status == RunStatus.paused:
            return IncidentControlState.PAUSED
        return IncidentControlState.ACTIVE

    def _capabilities(
        self,
        incident: IncidentRecord,
        *,
        control_state: IncidentControlState,
        approval_status: IncidentApprovalStatus,
        high_risk_required: bool,
        run_response: WorkflowRunOutput | None,
    ) -> tuple[IncidentControlCapability, ...]:
        can_cancel = not incident.is_terminal
        can_pause = (
            high_risk_required
            and control_state == IncidentControlState.ACTIVE
            and not incident.is_terminal
        )
        can_approve = approval_status == IncidentApprovalStatus.PENDING
        can_continue = (
            control_state == IncidentControlState.PAUSED
            and run_response is not None
            and not run_response.active_step_requirements
            and not run_response.active_error_requirements
            and approval_status != IncidentApprovalStatus.REJECTED
        )

        return (
            IncidentControlCapability(
                action=IncidentControlAction.APPROVAL,
                available=can_approve,
                detail=(
                    "Resolve the pending workflow confirmation requirement for a high-risk incident step."
                    if can_approve
                    else "Approval becomes available only when the workflow is paused on a confirmation gate."
                ),
            ),
            IncidentControlCapability(
                action=IncidentControlAction.PAUSE,
                available=can_pause,
                detail=(
                    "High-risk incidents pause automatically through a workflow-level HITL approval gate."
                    if high_risk_required
                    else "Pause is reserved for high-risk investigation steps that require approval."
                ),
            ),
            IncidentControlCapability(
                action=IncidentControlAction.CONTINUE,
                available=can_continue,
                detail=(
                    "Continue the paused workflow after all approval or input requirements have been resolved."
                    if can_continue
                    else "Continue becomes available after a paused workflow has no unresolved requirements."
                ),
            ),
            IncidentControlCapability(
                action=IncidentControlAction.CANCELLATION,
                available=can_cancel,
                detail=(
                    "Cancel the incident and propagate cancellation to the workflow run when possible."
                    if can_cancel
                    else "Cancellation is unavailable once the incident is terminal."
                ),
            ),
        )
