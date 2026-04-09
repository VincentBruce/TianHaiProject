from __future__ import annotations

from tianhai.runtime import (
    TianHaiRuntimeAssembly,
    create_agent_os,
    create_runtime_assembly,
)
from tianhai.server.governance import apply_api_surface_governance


runtime: TianHaiRuntimeAssembly = create_runtime_assembly()
agent_os = create_agent_os(runtime)
app = apply_api_surface_governance(agent_os.get_app())


def serve() -> None:
    agent_os.serve(
        app="tianhai.server.app:app",
        reload=runtime.settings.agentos_reload,
    )
