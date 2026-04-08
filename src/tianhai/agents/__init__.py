from tianhai.agents.primary import (
    DEFAULT_PRIMARY_AGENT_MODEL,
    PRIMARY_AGENT_ID,
    PRIMARY_AGENT_NAME,
    TianHaiPrimaryAgent,
)
from tianhai.runtime.boundaries import BoundaryName, get_boundary

BOUNDARY = get_boundary(BoundaryName.AGENTS)

__all__ = (
    "BOUNDARY",
    "DEFAULT_PRIMARY_AGENT_MODEL",
    "PRIMARY_AGENT_ID",
    "PRIMARY_AGENT_NAME",
    "TianHaiPrimaryAgent",
)
