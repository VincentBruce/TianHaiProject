# Phase 3: Incident and Workflow Layer

## Design Note

Phase 3 introduces TianHai incident diagnosis records and maps durable log
investigation handoff signals onto an Agno `Workflow`. The workflow layer stays
below any client API or control plane: it exposes typed internal request/result
objects, records lifecycle transitions, and uses Agno workflow session/run
state for execution tracking.

The local Agno docs and installed Agno 2.5.14 API show `Workflow` supports
`input_schema`, function/`Step` executors, `cancel_run`, `continue_run`, and
AgentOS registration through the `workflows` component list. TianHai uses those
native workflow primitives rather than making `TianHaiPrimaryAgent` execute
workflow logic. The primary agent continues to emit only
`WorkflowHandoffSignal`.

## Scope

- Typed incident diagnosis records, lifecycle states, lifecycle events, and
  workflow execution state.
- Internal incident creation from a Phase 2 `LogAnalysisRequest` and
  `WorkflowHandoffSignal`.
- An Agno `Workflow` for durable log investigation handoff intake.
- Internal support for execution state, cancellation marking, and continuation
  requests.
- Runtime assembly registration for the incident workflow.
- Focused tests for lifecycle invariants, workflow configuration, workflow
  execution smoke checks, and Phase 3 boundaries.

## Out Of Scope

- No Java Log Analysis Team.
- No memory policy.
- No knowledge retrieval.
- No RAG/search/log/evidence tools.
- No control plane or client API.
- No change that turns `TianHaiPrimaryAgent` into a workflow executor.

## Verification

- `uv run pytest`: 22 passed.
- `uv run python -m compileall -q src tests`: passed.
- `git diff --check`: passed.
- Runtime smoke check: `build_app(TianHaiSettings(sqlite_db_file=":memory:"))`
  returns a `FastAPI` app with `TianHaiPrimaryAgent` and
  `TianHaiIncidentWorkflow` registered through `AgentOS`.
- Workflow smoke check: a `TianHaiIncidentWorkflow` created through runtime
  assembly can create an incident, run it with an explicit run/session id, and
  return an Agno `WorkflowRunOutput` whose content is an
  `IncidentWorkflowResult`.
- Boundary check: the primary agent still only emits workflow handoff signals;
  no Java Log Analysis Team, memory policy, knowledge retrieval, RAG/search
  tool, control plane, or client API is implemented.

## Next-Phase Entry Criteria

- Start Phase 4 only after this Phase 3 test baseline remains green.
- Implement the Java Log Analysis Team under `tianhai.teams` and invoke it only
  from workflow-controlled boundaries.
- Keep the existing incident creation, execution state, cancellation, and
  continuation contracts stable unless Phase 4 finds a verified integration
  issue.
- Keep memory policy, knowledge retrieval, RAG/search tools, control plane, and
  client API work deferred to their planned phases.
