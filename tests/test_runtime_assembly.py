from pathlib import Path

from fastapi import FastAPI

from tianhai.agents import TianHaiPrimaryAgent
from tianhai.config import DatabaseBackend, TianHaiSettings
from tianhai.knowledge import TianHaiKnowledgeBase
from tianhai.memory import TianHaiMemoryPolicy
from tianhai.runtime import (
    RuntimeComponentSet,
    create_agent_os,
    create_db,
    create_runtime_assembly,
)
from tianhai.server.factory import build_app
from tianhai.teams import TianHaiJavaLogAnalysisTeam
from tianhai.workflows import TianHaiIncidentWorkflow


def test_settings_select_sqlite_without_database_url() -> None:
    settings = TianHaiSettings(sqlite_db_file=":memory:")

    assert settings.database_backend == DatabaseBackend.SQLITE


def test_in_memory_sqlite_setting_does_not_create_root_memory_file() -> None:
    memory_artifact = Path(__file__).resolve().parents[1] / ":memory:"
    memory_artifact.unlink(missing_ok=True)
    assert not memory_artifact.exists()

    db = create_db(TianHaiSettings(sqlite_db_file=":memory:"))
    db.upsert_learning(
        id="in-memory-smoke",
        learning_type="test_learning",
        content={"value": "not on disk"},
    )

    assert str(db.db_engine.url) == "sqlite://"
    assert db.db_file is None
    assert not memory_artifact.exists()


def test_runtime_assembly_registers_phase6_agent_workflow_and_knowledge() -> None:
    settings = TianHaiSettings(sqlite_db_file=":memory:")

    assembly = create_runtime_assembly(settings)

    assert len(assembly.components.agents) == 1
    assert isinstance(assembly.components.agents[0], TianHaiPrimaryAgent)
    assert assembly.components.teams == ()
    assert len(assembly.components.workflows) == 1
    assert isinstance(assembly.components.workflows[0], TianHaiIncidentWorkflow)
    assert assembly.components.workflows[0].db is assembly.db
    assert isinstance(
        assembly.components.workflows[0].log_analysis_team,
        TianHaiJavaLogAnalysisTeam,
    )
    assert isinstance(assembly.knowledge_base, TianHaiKnowledgeBase)
    assert assembly.components.workflows[0].knowledge_base is assembly.knowledge_base
    assert assembly.components.knowledge == (assembly.knowledge_base.knowledge,)
    assert isinstance(assembly.memory_policy, TianHaiMemoryPolicy)


def test_runtime_assembly_accepts_explicit_empty_component_override() -> None:
    settings = TianHaiSettings(sqlite_db_file=":memory:")

    assembly = create_runtime_assembly(settings, components=RuntimeComponentSet())

    assert assembly.components.is_business_empty()


def test_agentos_app_builds_with_phase6_runtime() -> None:
    settings = TianHaiSettings(sqlite_db_file=":memory:")
    assembly = create_runtime_assembly(settings)

    agent_os = create_agent_os(assembly)
    app = agent_os.get_app()

    assert isinstance(app, FastAPI)


def test_server_build_app_accepts_explicit_settings() -> None:
    app = build_app(TianHaiSettings(sqlite_db_file=":memory:"))

    assert isinstance(app, FastAPI)
