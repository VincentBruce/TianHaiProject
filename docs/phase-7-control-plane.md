# Phase 7: Control Plane

## Design Note

Phase 7 adds TianHai's internal incident control plane without defining the
future client API contract. The control plane stays inside the Agno runtime:
high-risk investigation steps are paused through workflow-level HITL on a
dedicated approval step, approval decisions are resolved against Agno
`StepRequirement` objects, continuation is handled through `Workflow.continue_run`,
and cancellation still flows through the existing incident/workflow lifecycle.
The approval gate is resolved from run-local step input rather than by mutating
shared workflow step configuration, so concurrent high-risk and low-risk runs do
not interfere with each other.

The local Agno docs show two constraints that shape this phase. First,
workflow-level HITL should use workflow primitives such as
`Step.requires_confirmation` rather than agent or team tool-level HITL, but
TianHai's review remediation keeps the approval decision run-scoped by
resolving it from step input at pause time instead of toggling shared step
state.
Second, paused workflow execution is resumed with `continue_run`, while
run-level cancellation still uses `cancel_run`. TianHai keeps those native
primitives and layers a small internal `TianHaiIncidentControlPlane` service on
top for later API exposure.

## Scope

- Internal incident control types under `tianhai.control`.
- Internal control-plane service exposing approval, pause, continue, and
  cancellation capabilities.
- High-risk incident assessment mapped onto a workflow-level approval step
  before the internal Java log analysis team runs.
- Runtime assembly access to the incident control plane without adding a public
  AgentOS endpoint or `/tianhai/*` API.
- Focused tests for pause/approve/continue/cancel control flow and runtime
  assembly wiring.

## Out Of Scope

- No `/tianhai/*` client API.
- No API surface governance.
- No streaming contract changes.
- No RAG, search, or retrieval hardening.
- No change that turns the Java log analysis team into a public AgentOS team or
  a control-plane actor.

## Verification

- `uv run pytest -q`: 43 passed.
- `uv run pytest tests/test_incident_workflow.py tests/test_control_plane.py tests/test_runtime_assembly.py -q`: 16 passed.
- `uv run python -m compileall -q src tests`: passed.
- `git diff --check`: passed.
- Local control-plane smoke check: a high-risk incident created against an
  in-memory SQLite workflow pauses on `request_high_risk_approval`, can be
  approved through `TianHaiIncidentControlPlane`, and then completes through
  `continue_paused_execution` using a fake internal team and fake knowledge
  provider.
- Concurrency regression check: high-risk and low-risk runs executed against the
  same workflow instance no longer contaminate each other's approval gate; the
  high-risk run still pauses on `request_high_risk_approval` while the low-risk
  run completes without approval.
- Runtime assembly check: `create_runtime_assembly(TianHaiSettings(sqlite_db_file=":memory:"))`
  now exposes an internal `incident_control_plane` alongside the Phase 6
  workflow, while still registering no public team surface.

## Next-Phase Entry Criteria

- Start Phase 8 only after this Phase 7 baseline remains green.
- Keep the new control-plane service internal while defining the later
  `/tianhai/*` API and AgentOS boundary in Phase 8.
- Preserve workflow-level HITL for high-risk investigation control; do not move
  approval logic into agent or team tool calls.
- Keep streaming, API governance details, and client contract work deferred to
  the planned API phases.
- Keep RAG, search, source verification, and retrieval hardening deferred to
  Phase 14.
