from fastapi import FastAPI

from tianhai.agents import TianHaiPrimaryAgent
from tianhai.config import DatabaseBackend, TianHaiSettings
from tianhai.runtime import (
    RuntimeComponentSet,
    create_agent_os,
    create_runtime_assembly,
)
from tianhai.server.factory import build_app


def test_settings_select_sqlite_without_database_url() -> None:
    settings = TianHaiSettings(sqlite_db_file=":memory:")

    assert settings.database_backend == DatabaseBackend.SQLITE


def test_runtime_assembly_registers_primary_agent_only_for_phase2() -> None:
    settings = TianHaiSettings(sqlite_db_file=":memory:")

    assembly = create_runtime_assembly(settings)

    assert len(assembly.components.agents) == 1
    assert isinstance(assembly.components.agents[0], TianHaiPrimaryAgent)
    assert assembly.components.teams == ()
    assert assembly.components.workflows == ()
    assert assembly.components.knowledge == ()


def test_runtime_assembly_accepts_explicit_empty_component_override() -> None:
    settings = TianHaiSettings(sqlite_db_file=":memory:")

    assembly = create_runtime_assembly(settings, components=RuntimeComponentSet())

    assert assembly.components.is_business_empty()


def test_agentos_app_builds_with_phase2_primary_agent_runtime() -> None:
    settings = TianHaiSettings(sqlite_db_file=":memory:")
    assembly = create_runtime_assembly(settings)

    agent_os = create_agent_os(assembly)
    app = agent_os.get_app()

    assert isinstance(app, FastAPI)


def test_server_build_app_accepts_explicit_settings() -> None:
    app = build_app(TianHaiSettings(sqlite_db_file=":memory:"))

    assert isinstance(app, FastAPI)
