# TianHai Master Plan

## Rules

- TianHai is a Java service log analysis assistant.
- TianHai's runtime foundation must stay inside the Agno ecosystem.
- AgentOS is the serving layer.
- Agent is the unit of single-agent capability.
- Team is the multi-agent collaboration primitive.
- Workflow is the long-running execution primitive.
- Sessions, State, Learning, Memory, and Knowledge remain Agno-first.
- TianHai adds log-analysis policy, schemas, tools, and orchestration boundaries on top of Agno rather than replacing it.
- Context lookup and RAG are tool/service capabilities, not dedicated baseline agents.
- TianHai is built as a clean runtime and does not inherit learning-stage runtime artifacts.

## Phase Plan

### Phase 1: Architecture Foundation

- **Status:** completed
- Establish the repository architecture and runtime assembly
- Define TianHai's typed domain models for Java log analysis
- Create the Agno-first module boundaries for agents, teams, workflows, memory, knowledge, and tools
- Add a basic automated test baseline

### Phase 2: Primary Agent

- **Status:** completed
- Implement TianHaiPrimaryAgent as the primary Agno agent entrypoint
- Use structured input and output schemas for log-analysis requests and diagnosis reports
- Support direct responses and workflow handoff signals

### Phase 3: Incident and Workflow Layer

- **Status:** completed
- Define TianHai's typed incident diagnosis models
- Implement TianHai incident records and lifecycle
- Map long-running log investigations to Agno workflows
- Support incident creation, execution state, cancellation, and continuation

### Phase 4: Java Log Analysis Team

- **Status:** completed
- Implement TianHai's first bounded multi-agent team
- Use Agno Team for log parsing, error analysis, evidence gathering, and report synthesis
- Keep team collaboration inside workflow-controlled boundaries

### Phase 5: Memory v1

- **Status:** completed
- Implement TianHai memory policy on top of Agno learning and memory stores
- Introduce store-specific write policies for service context, user preferences, and investigation patterns
- Make memory writes inspectable and correctable

### Phase 6: Knowledge and Evidence Baseline

- **Status:** completed
- Separate durable runbook and documentation retrieval from user memory
- Add knowledge retrieval for Java service notes, known issues, and Agno documentation
- Support evidence-aware outputs for log-analysis tasks

### Phase 7: Control Plane

- **Status:** pending
- Add approval, pause, continue, and cancellation control surfaces
- Map high-risk investigation steps to Agno HITL-friendly patterns
- Define internal incident control capabilities for later API exposure

### Phase 8: API Surface Governance

- **Status:** pending
- Define the boundary between TianHai APIs, realtime streaming, and raw AgentOS surfaces
- Keep /tianhai/* as the product contract and AgentOS auto surfaces as ops and development interfaces
- Document where future HTTP and streaming features should be added

### Phase 9: Explicit Investigation Routing

- **Status:** pending
- Define routing between immediate response, knowledge-assisted response, and durable incident investigation
- Keep RAG-assisted answers and durable incident investigation as distinct orchestration branches
- Set routing semantics before client contract finalization

### Phase 10: Client API Contract

- **Status:** pending
- Finalize the API contract that the future TianHai client will consume
- Cover chat, log submission, incidents, results, status streaming, and follow-up actions
- Keep the client as a communication surface over the server runtime

### Phase 11: Memory and Learning Hardening

- **Status:** pending
- Harden TianHai's memory and learning system for long-running runtime use
- Tighten identity boundaries, recall cost control, and memory growth governance
- Make cross-agent and workflow memory behavior more auditable and maintainable

### Phase 12: Runtime Logging and Dev Cleanup

- **Status:** pending
- Standardize TianHai runtime logging on official Agno custom logging
- Improve readable timing and cross-component debugging during development
- Add dev-only cleanup for sessions, learning, memories, metrics, and optional knowledge data
- Avoid introducing a second TianHai-specific logging system

### Phase 13: Skills and Tool Surface

- **Status:** pending
- Integrate Agno Skills / LocalSkills while keeping upstream skill sources independently updateable
- Add official Agno toolkits only where they fit the product
- Keep skill loading, tool attachment, and non-Agno wrappers explicit

### Phase 14: Evidence Retrieval and Search Hardening

- **Status:** pending
- Harden RAG, context lookup, log search, and documentation search as shared TianHai tooling
- Improve retrieval planning, ranking, source verification, and evidence structure
- Make retrieved evidence inspectable as shared tool output

### Phase 15: Audit, Remediation, Cleanup, and Optimization

- **Status:** pending
- Audit every finished phase against its spec, local Agno docs, and the real TianHai codebase
- Record only verified findings with explicit evidence
- Fix confirmed defects, clean residual debt, and track each item to verification

## Event-Driven Review Remediation

- Trigger only from verified external review findings
- Handle each trigger as a bounded remediation batch outside phase numbering
- Fix confirmed issues and add regression coverage

## Execution Order

1. Complete a phase design
2. Implement the phase in code
3. Run tests and smoke checks
4. Update the phase document with results and next-phase entry criteria
