# Phase 2: Primary Agent

## Design Note

Phase 2 introduces the first real TianHai business component: a primary Agno
`Agent` entrypoint for Java service log diagnosis. The agent stays thin and
Agno-first: it declares structured input and output schemas, constrains prompt
behavior, and registers with `AgentOS` through the existing runtime assembly.

The local Agno docs and installed Agno 2.5.14 API show `Agent` supports
`input_schema`, `output_schema`, `parse_response`, and `structured_outputs`.
TianHai uses those native settings instead of wrapping or replacing Agno's run
loop. Workflow handoff is represented only as a typed output signal for a
future durable investigation layer; no workflow execution, incident lifecycle,
team collaboration, memory policy, knowledge retrieval, RAG/search tool, or
client API is implemented in this phase.

## Scope

- `TianHaiPrimaryAgent` as the primary Agno `Agent` entrypoint.
- Structured log-analysis request schema.
- Structured diagnosis report schema with direct response and workflow handoff
  signal modes.
- Runtime assembly registration for the primary agent.
- Focused tests for schema invariants, agent configuration, and AgentOS smoke
  build.

## Out Of Scope

- No incident records or incident lifecycle.
- No workflow implementation or execution.
- No team collaboration.
- No memory policy, knowledge retrieval, RAG, search, or evidence tools.
- No TianHai client API.

## Verification

- `uv run pytest`: 14 passed.
- `uv run python -m compileall -q src tests`: passed.
- Runtime smoke check: `build_app(TianHaiSettings(sqlite_db_file=":memory:"))`
  returns a `FastAPI` app with `TianHaiPrimaryAgent` registered through
  `AgentOS`.
- Boundary check: teams, workflows, memory, knowledge, and tools remain without
  Phase 3+ implementations.

## Next-Phase Entry Criteria

- Start Phase 3 only after this Phase 2 test baseline remains green.
- Implement typed incident diagnosis models and lifecycle separately from the
  Phase 2 `DiagnosisReport` schema.
- Map `WorkflowHandoffSignal` to an Agno `Workflow` entrypoint without changing
  the primary agent into a workflow executor.
- Keep team collaboration, memory policy, knowledge retrieval, RAG/search tools,
  and client API work deferred to their planned phases.
