# Phase 9: Explicit Investigation Routing

## Design Note

Phase 9 defines TianHai's explicit routing semantics above the existing Phase 2
primary agent, Phase 6 knowledge baseline, and Phase 3/4/7 durable incident
workflow stack. The route layer stays internal to the runtime: it introduces a
typed routing policy and router that distinguish three branches without
finalizing any client endpoint, payload, or streaming protocol.

The local Agno docs and the already adopted TianHai patterns keep the split
clear. `Agent` remains the single-agent primitive for bounded diagnosis,
`Knowledge` remains the retrieval primitive for durable runbook and
documentation evidence, and `Workflow` remains the long-running execution
primitive for incident lifecycle, approvals, continuation, and internal team
execution. Phase 9 therefore does not turn the primary agent into a knowledge
retriever or workflow executor, and it does not treat RAG-assisted answers as a
shortcut into the durable investigation path.

## Scope

- Define three explicit internal routes:
  - immediate response;
  - knowledge-assisted response;
  - durable incident investigation.
- Add a typed routing policy that pins the semantics of:
  - `primary agent` on each route;
  - `knowledge baseline` on each route;
  - `incident workflow` on each route.
- Add an internal router that resolves:
  - `workflow_handoff` to the durable incident branch;
  - direct responses with routed knowledge evidence to the knowledge-assisted
    branch;
  - direct responses without routed knowledge evidence to the immediate branch.
- Attach routing metadata to runtime assembly and app state without adding a new
  AgentOS public surface or `/tianhai/*` route.
- Add focused tests that lock the separation between RAG-assisted answers and
  durable incident investigation.

## Out Of Scope

- No finalized client API contract.
- No new `/tianhai/*` endpoint.
- No streaming payload, event schema, or protocol detail.
- No RAG/search hardening, ranking hardening, or source-verification hardening.
- No change that makes the primary agent retrieve knowledge directly.
- No change that collapses knowledge-assisted responses into the durable
  incident workflow branch.

## Verification

- `uv run pytest -q`: 51 passed.
- `uv run pytest tests/test_investigation_routing.py tests/test_runtime_assembly.py tests/test_api_surface_governance.py tests/test_primary_agent.py tests/test_incident_workflow.py -q`:
  25 passed.
- `uv run python -m compileall -q src tests`: passed.
- `git diff --check`: passed.
- Phase 9 routing regression check: a direct response carrying primary-authored
  `knowledge_evidence` is no longer treated as a legal
  `knowledge_assisted_response` input; the router clears that evidence unless
  the Phase 6 knowledge baseline returns routed evidence for the request.
- Phase 9 routing smoke check: an in-memory runtime assembly can upgrade a
  direct response to `knowledge_assisted_response` only when the Phase 6
  knowledge baseline returns evidence, keep `workflow_handoff` on the separate
  `durable_incident_investigation` branch without taking the non-durable RAG
  path, and still build an app that exposes no `/tianhai/*` product routes.

## Next-Phase Entry Criteria

- Start Phase 10 only after this Phase 9 routing baseline remains green.
- Finalize the client-facing API contract against these three explicit routes
  rather than against raw AgentOS auto surfaces.
- Keep `/tianhai/*` as the product namespace while mapping request submission,
  incident reads, and control actions onto the already-defined routing
  semantics.
- Keep streaming payloads, protocol details, and endpoint names deferred to
  Phase 10.
- Preserve the distinction between knowledge-assisted responses and durable
  incident investigation unless a later phase records a verified need to change
  the routing policy.
