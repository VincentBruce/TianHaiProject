from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BoundaryName(StrEnum):
    AGENTS = "agents"
    TEAMS = "teams"
    WORKFLOWS = "workflows"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    TOOLS = "tools"


class AgnoPrimitive(StrEnum):
    AGENT = "Agent"
    TEAM = "Team"
    WORKFLOW = "Workflow"
    MEMORY = "Memory"
    KNOWLEDGE = "Knowledge"
    TOOL = "Tool"


@dataclass(frozen=True)
class ModuleBoundary:
    name: BoundaryName
    module: str
    agno_primitive: AgnoPrimitive
    phase1_scope: str
    first_business_phase: str


AGNO_FIRST_BOUNDARIES: tuple[ModuleBoundary, ...] = (
    ModuleBoundary(
        name=BoundaryName.AGENTS,
        module="tianhai.agents",
        agno_primitive=AgnoPrimitive.AGENT,
        phase1_scope="Boundary only; no Agent instances are registered.",
        first_business_phase="Phase 2",
    ),
    ModuleBoundary(
        name=BoundaryName.TEAMS,
        module="tianhai.teams",
        agno_primitive=AgnoPrimitive.TEAM,
        phase1_scope="Boundary only; no Team instances are registered.",
        first_business_phase="Phase 4",
    ),
    ModuleBoundary(
        name=BoundaryName.WORKFLOWS,
        module="tianhai.workflows",
        agno_primitive=AgnoPrimitive.WORKFLOW,
        phase1_scope="Boundary only; no Workflow instances are registered.",
        first_business_phase="Phase 3",
    ),
    ModuleBoundary(
        name=BoundaryName.MEMORY,
        module="tianhai.memory",
        agno_primitive=AgnoPrimitive.MEMORY,
        phase1_scope="Boundary only; no TianHai memory policy is implemented.",
        first_business_phase="Phase 5",
    ),
    ModuleBoundary(
        name=BoundaryName.KNOWLEDGE,
        module="tianhai.knowledge",
        agno_primitive=AgnoPrimitive.KNOWLEDGE,
        phase1_scope="Boundary only; no knowledge retrieval is implemented.",
        first_business_phase="Phase 6",
    ),
    ModuleBoundary(
        name=BoundaryName.TOOLS,
        module="tianhai.tools",
        agno_primitive=AgnoPrimitive.TOOL,
        phase1_scope="Boundary only; no log/search/evidence tools are implemented.",
        first_business_phase="Phase 6+",
    ),
)


def get_boundary(name: BoundaryName) -> ModuleBoundary:
    for boundary in AGNO_FIRST_BOUNDARIES:
        if boundary.name == name:
            return boundary
    raise KeyError(name)
