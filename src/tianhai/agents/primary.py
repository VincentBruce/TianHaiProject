from __future__ import annotations

from agno.agent import Agent
from agno.models.base import Model

from tianhai.domain import DiagnosisReport, LogAnalysisRequest


PRIMARY_AGENT_ID = "tianhai-primary-agent"
PRIMARY_AGENT_NAME = "TianHai Primary Agent"
DEFAULT_PRIMARY_AGENT_MODEL = "openai:gpt-4o"


PRIMARY_AGENT_INSTRUCTIONS: tuple[str, ...] = (
    "You are TianHaiPrimaryAgent, the primary Agno Agent for Java service "
    "log diagnosis.",
    "Use only the provided LogAnalysisRequest content as your evidence boundary.",
    "Return a direct_response when the supplied logs and context are sufficient "
    "for a bounded diagnosis.",
    "When allow_workflow_handoff is false, prefer direct_response and record "
    "uncertainty in limitations.",
    "Return a workflow_handoff signal when the request needs durable "
    "investigation, more logs, cross-service correlation, or long-running "
    "follow-up.",
    "Do not create incidents, execute workflows, call teams, write memory, "
    "retrieve knowledge, run RAG, search external systems, or use client APIs.",
    "Do not invent evidence. If evidence is weak or missing, state that in limitations.",
)


class TianHaiPrimaryAgent(Agent):
    """Primary Agno Agent entrypoint for TianHai log analysis."""

    def __init__(
        self,
        *,
        model: Model | str | None = DEFAULT_PRIMARY_AGENT_MODEL,
        db: object | None = None,
    ) -> None:
        super().__init__(
            id=PRIMARY_AGENT_ID,
            name=PRIMARY_AGENT_NAME,
            model=model,
            db=db,
            description="Primary TianHai agent for Java service log diagnosis.",
            instructions=list(PRIMARY_AGENT_INSTRUCTIONS),
            input_schema=LogAnalysisRequest,
            output_schema=DiagnosisReport,
            parse_response=True,
            structured_outputs=True,
            tools=[],
            add_knowledge_to_context=False,
            add_history_to_context=False,
            telemetry=False,
        )
