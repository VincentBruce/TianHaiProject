from __future__ import annotations

from tianhai.config import TianHaiSettings
from tianhai.runtime import create_agent_os, create_runtime_assembly
from tianhai.server.governance import apply_api_surface_governance


def build_app(settings: TianHaiSettings | None = None):
    assembly = create_runtime_assembly(settings)
    agent_os = create_agent_os(assembly)
    app = agent_os.get_app()
    app.state.tianhai_runtime_assembly = assembly
    app.state.tianhai_investigation_routing_policy = (
        assembly.investigation_routing_policy
    )
    app.state.tianhai_investigation_router = assembly.investigation_router
    return apply_api_surface_governance(app)
