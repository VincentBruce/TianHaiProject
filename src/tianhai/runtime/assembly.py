from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tianhai import __version__
from tianhai.config import DatabaseBackend, TianHaiSettings


@dataclass(frozen=True)
class RuntimeComponentSet:
    """Agno runtime components registered for AgentOS."""

    agents: tuple[object, ...] = ()
    teams: tuple[object, ...] = ()
    workflows: tuple[object, ...] = ()
    knowledge: tuple[object, ...] = ()

    def is_business_empty(self) -> bool:
        return not (self.agents or self.teams or self.workflows or self.knowledge)


@dataclass(frozen=True)
class TianHaiRuntimeAssembly:
    settings: TianHaiSettings
    db: object
    components: RuntimeComponentSet = field(default_factory=RuntimeComponentSet)


def create_db(settings: TianHaiSettings) -> object:
    """Create the Agno database configured for the current runtime."""

    if settings.database_backend == DatabaseBackend.POSTGRES:
        from agno.db.postgres import PostgresDb

        return PostgresDb(db_url=settings.database_url)

    from agno.db.sqlite import SqliteDb

    db_file = settings.sqlite_db_file
    if db_file != ":memory:":
        Path(db_file).expanduser().parent.mkdir(parents=True, exist_ok=True)
    return SqliteDb(db_file=db_file)


def create_runtime_assembly(
    settings: TianHaiSettings | None = None,
    *,
    db: object | None = None,
    components: RuntimeComponentSet | None = None,
) -> TianHaiRuntimeAssembly:
    resolved_settings = settings or TianHaiSettings()
    resolved_db = db if db is not None else create_db(resolved_settings)
    resolved_components = (
        components
        if components is not None
        else create_default_components(resolved_settings, db=resolved_db)
    )
    return TianHaiRuntimeAssembly(
        settings=resolved_settings,
        db=resolved_db,
        components=resolved_components,
    )


def create_default_components(
    settings: TianHaiSettings,
    *,
    db: object | None = None,
) -> RuntimeComponentSet:
    from tianhai.agents import TianHaiPrimaryAgent
    from tianhai.workflows import TianHaiIncidentWorkflow

    return RuntimeComponentSet(
        agents=(TianHaiPrimaryAgent(model=settings.primary_agent_model),),
        workflows=(
            TianHaiIncidentWorkflow(
                db=db,
                java_log_team_model=settings.java_log_team_model,
            ),
        ),
    )


def create_agent_os(assembly: TianHaiRuntimeAssembly):
    """Create an AgentOS instance for the configured runtime components."""

    from agno.os import AgentOS

    return AgentOS(
        id=assembly.settings.app_id,
        name=assembly.settings.app_name,
        description=assembly.settings.app_description,
        version=__version__,
        db=assembly.db,
        agents=list(assembly.components.agents),
        teams=list(assembly.components.teams),
        workflows=list(assembly.components.workflows),
        knowledge=list(assembly.components.knowledge),
        telemetry=assembly.settings.agentos_telemetry,
        auto_provision_dbs=assembly.settings.agentos_auto_provision_dbs,
    )
