# Phase 8: API Surface Governance

## Design Note

Phase 8 defines the boundary between TianHai's future product API surface,
future realtime streaming, and the raw AgentOS auto-generated surfaces already
exposed by `agent_os.get_app()`. The local Agno AgentOS docs show two relevant
upstream patterns: AgentOS can compose with a custom FastAPI `base_app`, and
route conflicts can later be resolved explicitly when product routes need to
override default AgentOS behavior. TianHai uses that guidance to reserve
`/tianhai/*` as the product contract namespace while keeping the current raw
AgentOS routes as ops/dev surfaces only.

This phase intentionally does not finalize any client endpoint shape, streaming
protocol, payload schema, or investigation routing semantics. Instead, it adds
typed governance metadata and route inspection so the current runtime can state
which surfaces are product-contract boundaries, which are raw AgentOS, and
where future HTTP and streaming features must be added.

## Scope

- Define typed governance for:
  - TianHai product HTTP surfaces under `/tianhai/*`;
  - TianHai product realtime streaming under `/tianhai/*`;
  - raw AgentOS HTTP auto surfaces for ops/dev;
  - raw AgentOS realtime streaming for ops/dev.
- Attach API-surface governance metadata and a live route snapshot to the built
  FastAPI app.
- Record where future capabilities belong:
  - request submission, incident reads, and control actions on TianHai product
    HTTP surfaces;
  - status and operator-attention updates on TianHai product streaming;
  - raw agent/workflow/session/knowledge/trace/schedule operations on AgentOS
    ops/dev surfaces only.
- Add focused tests that lock the current Phase 8 boundary:
  - no `/tianhai/*` product routes are registered yet;
  - current public routes are classified as raw AgentOS surfaces;
  - `/workflows/ws` is treated as raw AgentOS realtime streaming, not TianHai
    client streaming.

## Out Of Scope

- No investigation routing semantics.
- No finalized client API contract.
- No new `/tianhai/*` client API endpoint.
- No streaming payload, event schema, or protocol detail.
- No change that promotes raw AgentOS auto surfaces into TianHai's product API.

## Verification

- `uv run pytest tests/test_api_surface_governance.py -q`: 3 passed.
- `uv run pytest -q`: 46 passed.
- `uv run python -m compileall -q src tests`: passed.
- `git diff --check`: passed.
- Route inventory smoke check:
  `build_app(TianHaiSettings(sqlite_db_file=":memory:"))` exposes no
  `/tianhai/*` routes, produces no unclassified public routes, and currently
  exposes `/workflows/ws` only as a raw AgentOS realtime surface.
- Governance smoke check: future request submission, incident reads, and
  control actions map to TianHai product HTTP governance, while future status
  and operator-attention updates map to TianHai product realtime governance,
  without fixing endpoint names or payloads in Phase 8.

## Next-Phase Entry Criteria

- Start Phase 9 only after this Phase 8 baseline remains green.
- Define explicit investigation routing behind the Phase 8 product boundary
  rather than by exposing raw AgentOS routes as the client contract.
- Keep `/tianhai/*` as the reserved product namespace while Phase 9 sets only
  routing semantics.
- Keep endpoint shapes, streaming payloads, and protocol details deferred until
  Phase 10 client contract work.
- Preserve raw AgentOS auto surfaces as ops/dev-only unless a later phase
  explicitly changes that governance rule.
