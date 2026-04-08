# Phase 6: Knowledge and Evidence Baseline

## Design Note

Phase 6 introduces TianHai's durable knowledge baseline separately from Phase 5
memory. User preferences, service-context memories, investigation patterns, and
the memory write journal remain under `tianhai.memory`; runbook and
documentation retrieval now lives under `tianhai.knowledge`.

The local Agno docs show `Knowledge` configured with `vector_db`, `contents_db`,
`max_results`, and `search(...)` / `insert(...)` as the native knowledge
primitive. TianHai uses Agno `Knowledge` as the public knowledge object and
adds a small TianHai `VectorDb` implementation backed by the existing Agno
database for the Phase 6 baseline. This keeps the API Agno-first while avoiding
new external vector-store dependencies and leaves retrieval hardening,
ranking, search tools, and bulk ingestion to Phase 14.

Workflow integration is intentionally narrow: the incident workflow retrieves
bounded knowledge evidence before invoking the internal Java log analysis team,
then passes that evidence as structured `knowledge_evidence`. The team can cite
durable Java service notes, known issues, and Agno documentation, but it still
does not perform additional retrieval, RAG, external search, memory writes,
control-plane actions, or client API calls.

## Scope

- A dedicated `tianhai.knowledge` baseline service using Agno `Knowledge`.
- A TianHai-scoped Agno `VectorDb` baseline for durable keyword retrieval from
  the existing Agno database.
- Typed knowledge documents and queries for:
  - Java service notes;
  - known issues;
  - Agno documentation.
- `KnowledgeEvidence` in diagnosis and incident output schemas.
- Workflow-to-team propagation of retrieved knowledge evidence.
- Runtime assembly registration of the Agno knowledge component for AgentOS.
- Focused tests for knowledge/memory separation, corpus filtering, workflow
  integration, and runtime assembly.

## Out Of Scope

- No RAG/search tool hardening.
- No retrieval ranking hardening beyond the Phase 6 keyword baseline.
- No bulk ingestion pipeline for local Agno docs or service runbook trees.
- No control plane.
- No TianHai client API.
- No change that treats Phase 5 memory policy as a runbook, RAG, or knowledge
  store.
- No default memory writes from the Java Log Analysis Team.

## Verification

- `uv run pytest`: 38 passed.
- `uv run python -m compileall -q src tests`: passed.
- `git diff --check`: passed.
- Remediation check: `sqlite_db_file=":memory:"` now uses a true in-memory
  SQLite engine and does not create the project-root `:memory:` runtime file.
- Knowledge baseline smoke check: a Java service note can be inserted through
  TianHai's Agno `Knowledge` wrapper, retrieved as `KnowledgeEvidence`, and
  stored under `tianhai_knowledge` / `tianhai_knowledge_document` rather than
  the Phase 5 memory write journal.
- Corpus retrieval smoke check: Java service notes, known issues, and Agno
  documentation can be filtered independently.
- Workflow smoke check: the incident workflow retrieves knowledge evidence and
  passes it to `TianHaiJavaLogAnalysisTeam` without invoking memory writes,
  external search, control-plane actions, or client APIs.
- Runtime smoke check: `build_app(TianHaiSettings(sqlite_db_file=":memory:"))`
  returns a `FastAPI` app with the primary agent, incident workflow, and Agno
  knowledge component registered through `AgentOS`.

## Next-Phase Entry Criteria

- Start Phase 7 only after the Phase 6 test baseline remains green.
- Keep approval, pause, continue, cancellation, and high-risk action control
  surfaces in Phase 7; do not move them into the knowledge baseline.
- Preserve the separation between TianHai memory policy stores and durable
  knowledge retrieval when adding control-plane behavior.
- Keep RAG/search hardening, ranking, source verification, search tools, and
  bulk documentation ingestion deferred to Phase 14.
- Keep `/tianhai/*` client contract work deferred to the later API phases.
