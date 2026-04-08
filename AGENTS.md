# AGENTS.md

## Purpose

This repository is the early design and implementation home for TianHai, a Java service log analysis assistant built on Agno and served through AgentOS.

## Source of Truth

- `00-master-plan-TianHai.md` is the roadmap source.
- Before phase work, read `00-master-plan-TianHai.md`.
- Implement only the phase explicitly requested by the user.
- Do not prebuild future phases.
- If a request would touch a future phase, stop and confirm with the user before proceeding.

## Current Direction

- Runtime: Python with `uv`.
- Agent framework: `Agno`.
- Serving layer: `AgentOS`.
- Primary topology: long-running server backend first; client contract later.
- Product priority: Java log diagnosis, durable investigations, evidence-backed outputs.

## Working Rules

- Follow local Agno docs before introducing custom patterns.
- Local Agno docs: `/Users/lisztf./Documents/Agno AgentOS/docs.agno.com`.
- Use Agent for single-agent capability, Team for collaboration, Workflow for long-running execution.
- Keep Sessions, State, Learning, Memory, and Knowledge Agno-first.
- Treat context lookup and RAG as tools/services, not baseline agents.
- Keep TianHai as a clean runtime; do not inherit learning-stage runtime artifacts.
- Keep TianHai's policy, schemas, tools, and orchestration boundaries layered on top of Agno rather than replacing it.

## Phase Execution

- Start each phase with a short design note.
- Implement only that phase.
- Run relevant tests and smoke checks.
- Update phase notes with results and next-phase entry criteria.
- If external review finds verified issues, handle them as a bounded remediation batch.

## Repository Conventions

- Manage Python dependencies with `uv`.
- Target Python `3.12` unless Agno guidance requires otherwise.
- Use environment-driven configuration with `.env.example` once runtime config exists.
- Prefer PostgreSQL for durable production state; SQLite is acceptable for local development when it does not lock the design.
- Add build, run, lint, and test commands only when the toolchain exists.

## Structure Policy

- Do not create empty trees or placeholder modules.
- Introduce structure only when a phase requires it.
- Expected later structure:
  - `src/tianhai/`: application package
  - `src/tianhai/agents/`: Agno agents
  - `src/tianhai/teams/`: Agno teams
  - `src/tianhai/workflows/`: long-running investigations
  - `src/tianhai/memory/`: TianHai memory policy
  - `src/tianhai/knowledge/`: retrieval-facing knowledge integrations
  - `src/tianhai/tools/`: log, search, and evidence tools
  - `src/tianhai/server/`: AgentOS and API/runtime entrypoints
  - `tests/`: automated tests
  - `docs/`: phase design notes
