from __future__ import annotations

from tianhai.config import TianHaiSettings
from tianhai.runtime import create_agent_os, create_runtime_assembly
from tianhai.server.governance import apply_api_surface_governance


def build_app(settings: TianHaiSettings | None = None):
    assembly = create_runtime_assembly(settings)
    agent_os = create_agent_os(assembly)
    return apply_api_surface_governance(agent_os.get_app())
