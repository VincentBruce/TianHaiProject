# Phase 5: Memory v1

## Design Note

Phase 5 introduces TianHai's first memory policy layer without turning the
primary agent, incident workflow, or Java Log Analysis Team into implicit
memory writers. The policy is a standalone runtime service layered on top of
Agno storage primitives: Agno `MemoryManager`/`UserMemory` for per-user
preferences and Agno learning-table backed stores for service context,
investigation patterns, and the TianHai memory write journal.

The local Agno docs and installed Agno 2.5.14 API show memory can be managed
through `MemoryManager` and learning can be stored through `LearningMachine`
stores and `db.upsert_learning(...)`. TianHai uses those primitives directly
for explicit, auditable writes instead of adding agentic memory tools to the
Phase 4 team or introducing durable knowledge retrieval.

## Scope

- TianHai memory policy objects under `tianhai.memory`.
- Store-specific write policies for:
  - service context, stored as Agno entity memory learning records;
  - user preferences, stored as Agno user memories through `MemoryManager`;
  - investigation patterns, stored as TianHai-scoped Agno learning records.
- Inspectable memory write records before and after application.
- Correctable applied writes by replaying a corrected payload to the same
  store-specific target.
- Runtime assembly access to the memory policy without public AgentOS team,
  tool, API, RAG, or knowledge registration.

## Out Of Scope

- No durable knowledge retrieval.
- No RAG/search/log/evidence tools.
- No control plane.
- No TianHai client API.
- No default memory writes from the Java Log Analysis Team.
- No automatic LLM-based extraction from conversations.

## Verification

- `uv run pytest`: 34 passed.
- `uv run python -m compileall -q src tests`: passed.
- `git diff --check`: passed.
- Memory policy smoke check: a write can be proposed without touching the
  target store, then applied to the correct Agno-backed store, inspected from
  the TianHai write journal, and corrected in place against the same target.
- Review remediation check: applied write corrections now reject changes to
  the store-specific target, including user preference `user_id` changes and
  service context `service_name` / `environment` target changes.
- Boundary check: `TianHaiJavaLogAnalysisTeam` and its member agents still keep
  Agno memory and learning disabled, and `RuntimeComponentSet.teams` remains
  empty so no public AgentOS team entrypoint is registered.

## Next-Phase Entry Criteria

- Start Phase 6 only after this Phase 5 test baseline remains green.
- Implement durable knowledge and evidence retrieval separately from TianHai
  user preferences, service context, investigation patterns, and memory write
  journal records.
- Do not use the Phase 5 memory policy as a RAG/search/runbook store.
- Keep Java Log Analysis Team memory writes opt-in only unless a later phase
  explicitly adds a workflow-controlled approval path.
- Preserve the inspect/correct write journal contract when adding future
  knowledge or control-plane surfaces.
