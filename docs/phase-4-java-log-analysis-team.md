# Phase 4: Java Log Analysis Team

## Design Note

Phase 4 introduces TianHai's first bounded Agno `Team` for Java log analysis.
The team is responsible for log parsing, error analysis, evidence gathering,
and report synthesis, but it remains an internal workflow dependency rather
than an AgentOS-exposed public team entrypoint.

The local Agno docs show `Team` as the collaboration primitive for reasoning
tasks where agents divide responsibilities, and `Workflow` as the primitive for
predictable multi-step orchestration. They also show teams using Pydantic
`input_schema` and `output_schema`, and workflow `Step` supporting controlled
execution via either agents, teams, or executors. TianHai keeps the
workflow-controlled boundary by invoking the Java log analysis team from an
incident workflow step after the existing continuation gate. The team receives
only the current request, incident, continuation, and workflow context data; it
has no tools, memory writes, knowledge retrieval, RAG, external search, control
plane, or client API surface.

## Scope

- A bounded `TianHaiJavaLogAnalysisTeam` under `tianhai.teams`.
- Structured team input and output schemas for current-context Java log
  analysis.
- Four explicit team member roles: log parsing, error analysis, evidence
  gathering, and report synthesis.
- Incident workflow invocation from a controlled workflow step after missing
  handoff inputs are resolved.
- Focused tests for team configuration, workflow integration, and public
  boundary constraints.

## Out Of Scope

- No memory policy.
- No knowledge retrieval.
- No RAG/search/log/evidence tools.
- No control plane.
- No client API.
- No AgentOS public team registration.

## Verification

- `uv run pytest`: 25 passed.
- `uv run python -m compileall -q src tests`: passed.
- `git diff --check`: passed.
- Runtime smoke check: `build_app(TianHaiSettings(sqlite_db_file=":memory:"))`
  returns a `FastAPI` app with `TianHaiPrimaryAgent` and
  `TianHaiIncidentWorkflow` registered through `AgentOS`.
- Boundary check: `TianHaiJavaLogAnalysisTeam` is attached only as an internal
  workflow dependency; `RuntimeComponentSet.teams` remains empty, so no public
  AgentOS team entrypoint is registered.
- Workflow smoke check: the incident workflow invokes the Java log analysis
  team only after the continuation gate has no unresolved handoff inputs, maps
  the structured team result into `IncidentDiagnosisResult`, and keeps missing
  handoff input incidents in `AWAITING_CONTINUATION` without calling the team.

## Next-Phase Entry Criteria

- Start Phase 5 only after this Phase 4 test baseline remains green.
- Implement memory policy on top of Agno learning and memory stores without
  changing the Java Log Analysis Team into a memory writer by default.
- Keep knowledge retrieval, RAG/search tools, control plane, and client API work
  deferred to their planned phases.
- Keep team collaboration workflow-controlled unless a later phase explicitly
  defines a public product/API boundary for it.
