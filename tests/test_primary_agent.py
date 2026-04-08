import pytest
from pydantic import ValidationError

from tianhai.agents import PRIMARY_AGENT_ID, TianHaiPrimaryAgent
from tianhai.domain import (
    DiagnosisReport,
    DiagnosisResponseMode,
    JavaLogBatch,
    LogAnalysisRequest,
    WorkflowHandoffSignal,
)


def test_primary_agent_uses_phase2_structured_io_contract() -> None:
    agent = TianHaiPrimaryAgent()

    assert agent.id == PRIMARY_AGENT_ID
    assert agent.input_schema is LogAnalysisRequest
    assert agent.output_schema is DiagnosisReport
    assert agent.parse_response is True
    assert agent.structured_outputs is True
    assert agent.tools == []


def test_log_analysis_request_accepts_java_log_batch() -> None:
    request = LogAnalysisRequest(
        question="Why is checkout failing?",
        log_batch=JavaLogBatch(raw_excerpt="ERROR java.sql.SQLTimeoutException"),
    )

    assert request.log_batch.raw_excerpt == "ERROR java.sql.SQLTimeoutException"
    assert request.allow_workflow_handoff is True


def test_direct_response_report_rejects_workflow_handoff_signal() -> None:
    report = DiagnosisReport(
        response_mode=DiagnosisResponseMode.DIRECT_RESPONSE,
        summary="The supplied logs point to a database timeout.",
    )

    assert report.workflow_handoff is None

    with pytest.raises(ValidationError):
        DiagnosisReport(
            response_mode=DiagnosisResponseMode.DIRECT_RESPONSE,
            summary="The supplied logs point to a database timeout.",
            workflow_handoff=WorkflowHandoffSignal(reason="Needs more correlation."),
        )


def test_workflow_handoff_report_requires_handoff_signal() -> None:
    with pytest.raises(ValidationError):
        DiagnosisReport(
            response_mode=DiagnosisResponseMode.WORKFLOW_HANDOFF,
            summary="More durable investigation is needed.",
        )

    report = DiagnosisReport(
        response_mode=DiagnosisResponseMode.WORKFLOW_HANDOFF,
        summary="More durable investigation is needed.",
        workflow_handoff=WorkflowHandoffSignal(
            reason="The excerpt lacks upstream and database-side logs."
        ),
    )

    assert report.workflow_handoff is not None
