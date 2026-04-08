from __future__ import annotations

from tianhai.config import TianHaiSettings
from tianhai.runtime import create_agent_os, create_runtime_assembly


def build_app(settings: TianHaiSettings | None = None):
    assembly = create_runtime_assembly(settings)
    agent_os = create_agent_os(assembly)
    return agent_os.get_app()
