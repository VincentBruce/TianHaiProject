# Phase 1: Architecture Foundation

## Design Note

Phase 1 establishes the minimal TianHai runtime foundation without implementing
Phase 2+ business capabilities. The repository uses a `src/` Python package
layout, `uv` dependency management, Pydantic typed models for Java log records,
and an Agno-first runtime assembly centered on `AgentOS`.

The local Agno docs show `AgentOS` imported from `agno.os`, exposed through
`agent_os.get_app()`, and served with `agent_os.serve(...)`. Agno storage docs
show `PostgresDb` for production use and `SqliteDb` for local development. The
current Agno API requires at least one AgentOS component or a database, so Phase
1 uses an Agno `db` and keeps agents, teams, workflows, memory, knowledge, and
tools as explicit empty business capability boundaries.

## Scope

- Repository architecture for a Python 3.12 `uv` project.
- Runtime assembly that creates an AgentOS app from environment-driven settings.
- Java log analysis domain models only, with no parsing or diagnosis logic.
- Agno-first module boundaries for agents, teams, workflows, memory, knowledge,
  and tools.
- Basic pytest baseline.

## Out Of Scope

- No `TianHaiPrimaryAgent`.
- No agent/team/workflow implementations.
- No incident lifecycle, memory policy, knowledge retrieval, or tools.
- No diagnosis report schema or client API contract.

## Verification

- `uv run pytest`: 9 passed.
- Runtime smoke check: `build_app(TianHaiSettings(sqlite_db_file=":memory:"))`
  returns a `FastAPI` app through Agno `AgentOS`.
- `uv run python -m compileall -q src tests`: passed.
- Boundary check: agents, teams, workflows, memory, knowledge, and tools expose
  module boundary contracts but register no Phase 2+ business components.

## Next-Phase Entry Criteria

- Implement Phase 2 only after keeping this Phase 1 baseline green.
- Add `TianHaiPrimaryAgent` under `tianhai.agents` as the first real Agno
  `Agent`.
- Define structured input/output schemas for primary-agent log analysis without
  changing incident/workflow/team/memory/knowledge/tool behavior.
- Register the primary agent in runtime assembly only as part of Phase 2.
