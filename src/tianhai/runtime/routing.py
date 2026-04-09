from __future__ import annotations

from dataclasses import dataclass

from tianhai.domain import (
    DiagnosisReport,
    DiagnosisResponseMode,
    InvestigationRoute,
    KnowledgeEvidence,
    LogAnalysisRequest,
)
from tianhai.knowledge import DEFAULT_KNOWLEDGE_MAX_RESULTS


@dataclass(frozen=True)
class InvestigationRouteRule:
    route: InvestigationRoute
    summary: str
    uses_primary_agent: bool
    uses_knowledge_base: bool
    uses_incident_workflow: bool
    creates_incident: bool
    uses_internal_team: bool
    supports_control_plane: bool
    primary_agent_semantics: str
    knowledge_baseline_semantics: str
    incident_workflow_semantics: str


@dataclass(frozen=True)
class TianHaiInvestigationRoutingPolicy:
    routes: tuple[InvestigationRouteRule, ...]

    def get_route_rule(
        self,
        route: InvestigationRoute,
    ) -> InvestigationRouteRule:
        for item in self.routes:
            if item.route == route:
                return item
        raise KeyError(route)

    def classify_report(
        self,
        report: DiagnosisReport,
    ) -> InvestigationRoute:
        if report.response_mode == DiagnosisResponseMode.WORKFLOW_HANDOFF:
            return InvestigationRoute.DURABLE_INCIDENT_INVESTIGATION
        if report.knowledge_evidence:
            return InvestigationRoute.KNOWLEDGE_ASSISTED_RESPONSE
        return InvestigationRoute.IMMEDIATE_RESPONSE


@dataclass(frozen=True)
class InvestigationRouteDecision:
    route: InvestigationRoute
    rule: InvestigationRouteRule
    report: DiagnosisReport
    rationale: str


DEFAULT_INVESTIGATION_ROUTING_POLICY = TianHaiInvestigationRoutingPolicy(
    routes=(
        InvestigationRouteRule(
            route=InvestigationRoute.IMMEDIATE_RESPONSE,
            summary=(
                "Return the primary-agent direct response immediately without "
                "knowledge retrieval or durable investigation."
            ),
            uses_primary_agent=True,
            uses_knowledge_base=False,
            uses_incident_workflow=False,
            creates_incident=False,
            uses_internal_team=False,
            supports_control_plane=False,
            primary_agent_semantics=(
                "The primary agent produces the final bounded answer directly "
                "from the supplied request."
            ),
            knowledge_baseline_semantics=(
                "The knowledge baseline is not invoked on the immediate "
                "response branch."
            ),
            incident_workflow_semantics=(
                "The incident workflow is not created or consulted on the "
                "immediate response branch."
            ),
        ),
        InvestigationRouteRule(
            route=InvestigationRoute.KNOWLEDGE_ASSISTED_RESPONSE,
            summary=(
                "Keep the response non-durable, but attach TianHai durable "
                "knowledge evidence to the direct answer."
            ),
            uses_primary_agent=True,
            uses_knowledge_base=True,
            uses_incident_workflow=False,
            creates_incident=False,
            uses_internal_team=False,
            supports_control_plane=False,
            primary_agent_semantics=(
                "The primary agent still provides the bounded direct diagnosis "
                "instead of handing off to a workflow."
            ),
            knowledge_baseline_semantics=(
                "The knowledge baseline adds runbook or documentation evidence "
                "to the answer without turning the request into a durable incident."
            ),
            incident_workflow_semantics=(
                "The incident workflow remains out of band for the "
                "knowledge-assisted response branch."
            ),
        ),
        InvestigationRouteRule(
            route=InvestigationRoute.DURABLE_INCIDENT_INVESTIGATION,
            summary=(
                "Create or continue a durable incident investigation through "
                "the incident workflow."
            ),
            uses_primary_agent=True,
            uses_knowledge_base=True,
            uses_incident_workflow=True,
            creates_incident=True,
            uses_internal_team=True,
            supports_control_plane=True,
            primary_agent_semantics=(
                "The primary agent only emits a workflow handoff signal and "
                "does not execute the durable investigation itself."
            ),
            knowledge_baseline_semantics=(
                "The knowledge baseline can be used inside the workflow as "
                "durable evidence gathering, not as a non-durable RAG answer path."
            ),
            incident_workflow_semantics=(
                "The incident workflow owns incident lifecycle, control-plane "
                "gates, team execution, and the durable investigation result."
            ),
        ),
    )
)


class TianHaiInvestigationRouter:
    """Resolve TianHai routing between immediate, knowledge, and durable branches."""

    def __init__(
        self,
        *,
        knowledge_base: object | None = None,
        knowledge_max_results: int = DEFAULT_KNOWLEDGE_MAX_RESULTS,
        routing_policy: TianHaiInvestigationRoutingPolicy = (
            DEFAULT_INVESTIGATION_ROUTING_POLICY
        ),
    ) -> None:
        self.knowledge_base = knowledge_base
        self.knowledge_max_results = knowledge_max_results
        self.routing_policy = routing_policy

    def route_primary_report(
        self,
        *,
        request: LogAnalysisRequest,
        primary_report: DiagnosisReport,
    ) -> InvestigationRouteDecision:
        if primary_report.response_mode == DiagnosisResponseMode.WORKFLOW_HANDOFF:
            return InvestigationRouteDecision(
                route=InvestigationRoute.DURABLE_INCIDENT_INVESTIGATION,
                rule=self.routing_policy.get_route_rule(
                    InvestigationRoute.DURABLE_INCIDENT_INVESTIGATION
                ),
                report=primary_report,
                rationale=(
                    "The primary agent emitted workflow_handoff, so the request "
                    "must continue on the durable incident investigation branch."
                ),
            )

        sanitized_report = _strip_primary_authored_knowledge_evidence(primary_report)

        knowledge_evidence = self._retrieve_knowledge_evidence(request)
        if knowledge_evidence:
            enriched_report = sanitized_report.model_copy(
                update={
                    "knowledge_evidence": knowledge_evidence,
                }
            )
            return InvestigationRouteDecision(
                route=InvestigationRoute.KNOWLEDGE_ASSISTED_RESPONSE,
                rule=self.routing_policy.get_route_rule(
                    InvestigationRoute.KNOWLEDGE_ASSISTED_RESPONSE
                ),
                report=enriched_report,
                rationale=(
                    "TianHai durable knowledge matched the direct-response "
                    "request, so the answer stays non-durable but becomes "
                    "knowledge-assisted."
                ),
            )

        return InvestigationRouteDecision(
            route=InvestigationRoute.IMMEDIATE_RESPONSE,
            rule=self.routing_policy.get_route_rule(
                InvestigationRoute.IMMEDIATE_RESPONSE
            ),
            report=sanitized_report,
            rationale=(
                "No durable incident handoff or routed knowledge evidence is "
                "required, so the primary-agent answer can be returned immediately."
            ),
        )

    def _retrieve_knowledge_evidence(
        self,
        request: LogAnalysisRequest,
    ) -> tuple[KnowledgeEvidence, ...]:
        if self.knowledge_base is None or not hasattr(
            self.knowledge_base,
            "retrieve_for_log_analysis",
        ):
            return ()

        retrieval_result = self.knowledge_base.retrieve_for_log_analysis(
            request,
            max_results=self.knowledge_max_results,
        )
        evidence = getattr(retrieval_result, "evidence", ())
        return tuple(_coerce_knowledge_evidence(item) for item in evidence)


def _strip_primary_authored_knowledge_evidence(
    report: DiagnosisReport,
) -> DiagnosisReport:
    if report.response_mode != DiagnosisResponseMode.DIRECT_RESPONSE:
        return report
    if not report.knowledge_evidence:
        return report
    return report.model_copy(update={"knowledge_evidence": ()})


def _coerce_knowledge_evidence(value: object) -> KnowledgeEvidence:
    if isinstance(value, KnowledgeEvidence):
        return value
    return KnowledgeEvidence.model_validate(value)


__all__ = (
    "DEFAULT_INVESTIGATION_ROUTING_POLICY",
    "InvestigationRouteDecision",
    "InvestigationRouteRule",
    "TianHaiInvestigationRouter",
    "TianHaiInvestigationRoutingPolicy",
)
