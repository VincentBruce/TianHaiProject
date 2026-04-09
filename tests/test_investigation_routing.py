from tianhai.domain import (
    DiagnosisReport,
    DiagnosisResponseMode,
    InvestigationRoute,
    JavaLogBatch,
    KnowledgeEvidence,
    KnowledgeSourceType,
    LogAnalysisRequest,
    WorkflowHandoffSignal,
)
from tianhai.runtime import (
    DEFAULT_INVESTIGATION_ROUTING_POLICY,
    TianHaiInvestigationRouter,
)


def test_phase9_routing_policy_defines_three_explicit_routes() -> None:
    policy = DEFAULT_INVESTIGATION_ROUTING_POLICY

    assert tuple(rule.route for rule in policy.routes) == (
        InvestigationRoute.IMMEDIATE_RESPONSE,
        InvestigationRoute.KNOWLEDGE_ASSISTED_RESPONSE,
        InvestigationRoute.DURABLE_INCIDENT_INVESTIGATION,
    )
    assert (
        policy.get_route_rule(InvestigationRoute.IMMEDIATE_RESPONSE).uses_knowledge_base
        is False
    )
    assert (
        policy.get_route_rule(
            InvestigationRoute.KNOWLEDGE_ASSISTED_RESPONSE
        ).uses_incident_workflow
        is False
    )
    durable_rule = policy.get_route_rule(
        InvestigationRoute.DURABLE_INCIDENT_INVESTIGATION
    )
    assert durable_rule.creates_incident is True
    assert durable_rule.uses_internal_team is True
    assert durable_rule.supports_control_plane is True


def test_router_keeps_direct_response_on_immediate_branch_without_knowledge_match() -> None:
    knowledge_base = FakeKnowledgeBase(evidence=())
    router = TianHaiInvestigationRouter(knowledge_base=knowledge_base)

    decision = router.route_primary_report(
        request=_request(),
        primary_report=_direct_report(),
    )

    assert decision.route == InvestigationRoute.IMMEDIATE_RESPONSE
    assert decision.report.response_mode == DiagnosisResponseMode.DIRECT_RESPONSE
    assert decision.report.knowledge_evidence == ()
    assert knowledge_base.max_results == [5]


def test_router_ignores_primary_authored_knowledge_evidence_without_baseline() -> None:
    router = TianHaiInvestigationRouter(knowledge_base=None)

    decision = router.route_primary_report(
        request=_request(),
        primary_report=_direct_report(knowledge_evidence=(_knowledge_evidence(),)),
    )

    assert decision.route == InvestigationRoute.IMMEDIATE_RESPONSE
    assert decision.report.response_mode == DiagnosisResponseMode.DIRECT_RESPONSE
    assert decision.report.knowledge_evidence == ()


def test_router_upgrades_direct_response_to_knowledge_assisted_branch() -> None:
    knowledge_base = FakeKnowledgeBase(evidence=(_knowledge_evidence(),))
    router = TianHaiInvestigationRouter(knowledge_base=knowledge_base)

    decision = router.route_primary_report(
        request=_request(),
        primary_report=_direct_report(),
    )

    assert decision.route == InvestigationRoute.KNOWLEDGE_ASSISTED_RESPONSE
    assert decision.report.response_mode == DiagnosisResponseMode.DIRECT_RESPONSE
    assert decision.report.workflow_handoff is None
    assert decision.report.knowledge_evidence == (_knowledge_evidence(),)
    assert decision.rule.creates_incident is False
    assert decision.rule.uses_incident_workflow is False


def test_router_keeps_workflow_handoff_on_durable_branch_without_rag_lookup() -> None:
    knowledge_base = FakeKnowledgeBase(evidence=(_knowledge_evidence(),))
    router = TianHaiInvestigationRouter(knowledge_base=knowledge_base)

    decision = router.route_primary_report(
        request=_request(),
        primary_report=DiagnosisReport(
            response_mode=DiagnosisResponseMode.WORKFLOW_HANDOFF,
            summary="Durable investigation is required.",
            workflow_handoff=WorkflowHandoffSignal(
                reason="Needs correlation across more systems.",
            ),
        ),
    )

    assert decision.route == InvestigationRoute.DURABLE_INCIDENT_INVESTIGATION
    assert decision.report.workflow_handoff is not None
    assert decision.rule.creates_incident is True
    assert decision.rule.uses_incident_workflow is True
    assert knowledge_base.max_results == []


def _request() -> LogAnalysisRequest:
    return LogAnalysisRequest(
        question="Why is checkout failing?",
        log_batch=JavaLogBatch(raw_excerpt="ERROR java.sql.SQLTimeoutException"),
    )


def _direct_report(
    *,
    knowledge_evidence: tuple[KnowledgeEvidence, ...] = (),
) -> DiagnosisReport:
    return DiagnosisReport(
        response_mode=DiagnosisResponseMode.DIRECT_RESPONSE,
        summary="The supplied logs point to a database timeout.",
        knowledge_evidence=knowledge_evidence,
    )


def _knowledge_evidence() -> KnowledgeEvidence:
    return KnowledgeEvidence(
        id="kb-checkout-timeout",
        summary="Checkout SQL timeouts can follow HikariCP saturation.",
        source_type=KnowledgeSourceType.JAVA_SERVICE_NOTES,
        title="Checkout timeout runbook",
        excerpt="Inspect HikariCP active connections before retry settings.",
        source_uri="runbooks/checkout-timeout.md",
        service_name="checkout",
    )


class FakeKnowledgeBase:
    def __init__(self, *, evidence: tuple[KnowledgeEvidence, ...]) -> None:
        self.evidence = evidence
        self.max_results: list[int] = []

    def retrieve_for_log_analysis(
        self,
        request: LogAnalysisRequest,
        *,
        max_results: int,
    ) -> object:
        self.max_results.append(max_results)
        assert request.question == "Why is checkout failing?"
        return FakeKnowledgeRetrievalResult(self.evidence)


class FakeKnowledgeRetrievalResult:
    def __init__(self, evidence: tuple[KnowledgeEvidence, ...]) -> None:
        self.evidence = evidence
