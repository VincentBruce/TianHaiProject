from fastapi import FastAPI

from tianhai.config import DatabaseBackend, TianHaiSettings
from tianhai.runtime import create_agent_os, create_runtime_assembly
from tianhai.server.factory import build_app


def test_settings_select_sqlite_without_database_url() -> None:
    settings = TianHaiSettings(sqlite_db_file=":memory:")

    assert settings.database_backend == DatabaseBackend.SQLITE


def test_runtime_assembly_has_no_phase2_business_components() -> None:
    settings = TianHaiSettings(sqlite_db_file=":memory:")

    assembly = create_runtime_assembly(settings)

    assert assembly.components.is_business_empty()


def test_agentos_app_builds_with_db_only_phase1_runtime() -> None:
    settings = TianHaiSettings(sqlite_db_file=":memory:")
    assembly = create_runtime_assembly(settings)

    agent_os = create_agent_os(assembly)
    app = agent_os.get_app()

    assert isinstance(app, FastAPI)


def test_server_build_app_accepts_explicit_settings() -> None:
    app = build_app(TianHaiSettings(sqlite_db_file=":memory:"))

    assert isinstance(app, FastAPI)
