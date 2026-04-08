from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import uuid4

from agno.db.schemas import UserMemory
from agno.learn import EntityMemoryConfig, LearningMode
from agno.learn.schemas import EntityMemory
from agno.learn.stores import EntityMemoryStore
from agno.memory import MemoryManager
from pydantic import Field, model_validator

from tianhai.domain.incidents import utc_now
from tianhai.domain.logs import TianHaiDomainModel
from tianhai.memory.types import (
    INVESTIGATION_PATTERN_LEARNING_TYPE,
    SERVICE_CONTEXT_ENTITY_TYPE,
    SERVICE_CONTEXT_NAMESPACE,
    TIANHAI_MEMORY_WRITE_ENTITY_TYPE,
    TIANHAI_MEMORY_WRITE_JOURNAL_TYPE,
    TIANHAI_MEMORY_WRITE_NAMESPACE,
    TianHaiMemoryStore,
    TianHaiMemoryWriteStatus,
)


class MemoryWriteActor(TianHaiDomainModel):
    user_id: str | None = None
    agent_id: str | None = None
    team_id: str | None = None
    workflow_id: str | None = None
    session_id: str | None = None
    source: str = Field(default="manual", min_length=1)


class ServiceContextMemory(TianHaiDomainModel):
    store: Literal[TianHaiMemoryStore.SERVICE_CONTEXT] = (
        TianHaiMemoryStore.SERVICE_CONTEXT
    )
    service_name: str = Field(min_length=1)
    environment: str | None = None
    summary: str | None = None
    facts: tuple[str, ...] = ()
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_summary_or_facts(self) -> ServiceContextMemory:
        if self.summary is None and not self.facts:
            raise ValueError("service context memory requires summary or facts")
        return self


class UserPreferenceMemory(TianHaiDomainModel):
    store: Literal[TianHaiMemoryStore.USER_PREFERENCES] = (
        TianHaiMemoryStore.USER_PREFERENCES
    )
    user_id: str = Field(min_length=1)
    preference: str = Field(min_length=1)
    preference_scope: str = Field(default="general", min_length=1)
    source: str = Field(min_length=1)


class InvestigationPatternMemory(TianHaiDomainModel):
    store: Literal[TianHaiMemoryStore.INVESTIGATION_PATTERNS] = (
        TianHaiMemoryStore.INVESTIGATION_PATTERNS
    )
    pattern_name: str = Field(min_length=1)
    pattern: str = Field(min_length=1)
    applies_to: tuple[str, ...] = Field(min_length=1)
    evidence: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    source_incident_id: str | None = None
    source: str = Field(min_length=1)


MemoryPayload = Annotated[
    ServiceContextMemory | UserPreferenceMemory | InvestigationPatternMemory,
    Field(discriminator="store"),
]


class MemoryTargetRef(TianHaiDomainModel):
    store: TianHaiMemoryStore
    storage_kind: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    namespace: str | None = None
    learning_type: str | None = None
    entity_id: str | None = None
    entity_type: str | None = None
    user_id: str | None = None


class MemoryWriteCorrection(TianHaiDomainModel):
    reason: str = Field(min_length=1)
    corrected_by: str | None = None
    corrected_at: datetime = Field(default_factory=utc_now)
    payload: MemoryPayload


class MemoryWriteRecord(TianHaiDomainModel):
    write_id: str = Field(min_length=1)
    status: TianHaiMemoryWriteStatus
    payload: MemoryPayload
    actor: MemoryWriteActor = Field(default_factory=MemoryWriteActor)
    target: MemoryTargetRef | None = None
    rejection_reason: str | None = None
    corrections: tuple[MemoryWriteCorrection, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def is_applied(self) -> bool:
        return self.status in {
            TianHaiMemoryWriteStatus.APPLIED,
            TianHaiMemoryWriteStatus.CORRECTED,
        }


class TianHaiInvestigationPatternStore:
    """TianHai-scoped learning store for reusable investigation patterns."""

    def __init__(self, *, db: object) -> None:
        self.db = db

    def save(
        self,
        payload: InvestigationPatternMemory,
        *,
        target_id: str | None = None,
        actor: MemoryWriteActor | None = None,
    ) -> MemoryTargetRef:
        pattern_id = target_id or f"tianhai-pattern-{uuid4()}"
        content = payload.model_dump(mode="json")
        metadata = {
            "source": payload.source,
            "source_incident_id": payload.source_incident_id,
            "policy": "tianhai_memory_v1",
        }
        self.db.upsert_learning(
            id=pattern_id,
            learning_type=INVESTIGATION_PATTERN_LEARNING_TYPE,
            content=content,
            user_id=actor.user_id if actor else None,
            agent_id=actor.agent_id if actor else None,
            team_id=actor.team_id if actor else None,
            workflow_id=actor.workflow_id if actor else None,
            session_id=actor.session_id if actor else None,
            namespace=TianHaiMemoryStore.INVESTIGATION_PATTERNS.value,
            entity_id=pattern_id,
            entity_type=TianHaiMemoryStore.INVESTIGATION_PATTERNS.value,
            metadata=metadata,
        )
        return MemoryTargetRef(
            store=TianHaiMemoryStore.INVESTIGATION_PATTERNS,
            storage_kind="agno_learning",
            target_id=pattern_id,
            namespace=TianHaiMemoryStore.INVESTIGATION_PATTERNS.value,
            learning_type=INVESTIGATION_PATTERN_LEARNING_TYPE,
            entity_id=pattern_id,
            entity_type=TianHaiMemoryStore.INVESTIGATION_PATTERNS.value,
            user_id=actor.user_id if actor else None,
        )

    def get(self, pattern_id: str) -> InvestigationPatternMemory | None:
        result = self.db.get_learning(
            learning_type=INVESTIGATION_PATTERN_LEARNING_TYPE,
            namespace=TianHaiMemoryStore.INVESTIGATION_PATTERNS.value,
            entity_id=pattern_id,
            entity_type=TianHaiMemoryStore.INVESTIGATION_PATTERNS.value,
        )
        if not result or not result.get("content"):
            return None
        return InvestigationPatternMemory.model_validate(result["content"])


class TianHaiMemoryPolicy:
    """Explicit TianHai memory write policy on top of Agno stores."""

    def __init__(
        self,
        *,
        db: object,
        memory_manager: MemoryManager | None = None,
        service_context_store: EntityMemoryStore | None = None,
        investigation_pattern_store: TianHaiInvestigationPatternStore | None = None,
    ) -> None:
        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db=db)
        self.service_context_store = (
            service_context_store or _create_service_context_store(db=db)
        )
        self.investigation_pattern_store = (
            investigation_pattern_store or TianHaiInvestigationPatternStore(db=db)
        )

    def propose_write(
        self,
        payload: MemoryPayload,
        *,
        actor: MemoryWriteActor | None = None,
        write_id: str | None = None,
    ) -> MemoryWriteRecord:
        record = MemoryWriteRecord(
            write_id=write_id or f"tianhai-memory-write-{uuid4()}",
            status=TianHaiMemoryWriteStatus.PROPOSED,
            payload=payload,
            actor=actor or MemoryWriteActor(),
        )
        self._save_write_record(record)
        return record

    def apply_write(
        self,
        write_id: str,
        *,
        applied_by: str | None = None,
    ) -> MemoryWriteRecord:
        record = self.inspect_write(write_id)
        if record.status != TianHaiMemoryWriteStatus.PROPOSED:
            raise ValueError(
                f"memory write {write_id} is {record.status}; only proposed writes "
                "can be applied"
            )

        actor = _actor_with_source(record.actor, applied_by)
        target = self._write_payload(record.payload, actor=actor, target=record.target)
        updated = record.model_copy(
            update={
                "status": TianHaiMemoryWriteStatus.APPLIED,
                "target": target,
                "actor": actor,
                "updated_at": utc_now(),
            }
        )
        self._save_write_record(updated)
        return updated

    def reject_write(
        self,
        write_id: str,
        *,
        reason: str,
    ) -> MemoryWriteRecord:
        record = self.inspect_write(write_id)
        if record.is_applied:
            raise ValueError(f"memory write {write_id} has already been applied")
        updated = record.model_copy(
            update={
                "status": TianHaiMemoryWriteStatus.REJECTED,
                "rejection_reason": reason,
                "updated_at": utc_now(),
            }
        )
        self._save_write_record(updated)
        return updated

    def correct_write(
        self,
        write_id: str,
        *,
        corrected_payload: MemoryPayload,
        reason: str,
        corrected_by: str | None = None,
    ) -> MemoryWriteRecord:
        record = self.inspect_write(write_id)
        if record.status == TianHaiMemoryWriteStatus.REJECTED:
            raise ValueError(f"memory write {write_id} has been rejected")
        if record.payload.store != corrected_payload.store:
            raise ValueError("corrected memory payload must target the same store")
        if record.is_applied:
            _ensure_same_correction_target(record, corrected_payload)

        correction = MemoryWriteCorrection(
            reason=reason,
            corrected_by=corrected_by,
            payload=corrected_payload,
        )
        status = record.status
        target = record.target
        if record.is_applied:
            target = self._write_payload(
                corrected_payload,
                actor=record.actor,
                target=record.target,
            )
            status = TianHaiMemoryWriteStatus.CORRECTED

        updated = record.model_copy(
            update={
                "status": status,
                "payload": corrected_payload,
                "target": target,
                "corrections": record.corrections + (correction,),
                "updated_at": utc_now(),
            }
        )
        self._save_write_record(updated)
        return updated

    def inspect_write(self, write_id: str) -> MemoryWriteRecord:
        result = self.db.get_learning(
            learning_type=TIANHAI_MEMORY_WRITE_JOURNAL_TYPE,
            namespace=TIANHAI_MEMORY_WRITE_NAMESPACE,
            entity_id=write_id,
            entity_type=TIANHAI_MEMORY_WRITE_ENTITY_TYPE,
        )
        if not result or not result.get("content"):
            raise KeyError(write_id)
        return MemoryWriteRecord.model_validate(result["content"])

    def list_writes(
        self,
        *,
        status: TianHaiMemoryWriteStatus | None = None,
        store: TianHaiMemoryStore | None = None,
        limit: int = 100,
    ) -> tuple[MemoryWriteRecord, ...]:
        records = self.db.get_learnings(
            learning_type=TIANHAI_MEMORY_WRITE_JOURNAL_TYPE,
            namespace=TIANHAI_MEMORY_WRITE_NAMESPACE,
            limit=limit,
        )
        parsed = tuple(
            MemoryWriteRecord.model_validate(record["content"])
            for record in records
            if isinstance(record, dict) and record.get("content")
        )
        if status is not None:
            parsed = tuple(record for record in parsed if record.status == status)
        if store is not None:
            parsed = tuple(record for record in parsed if record.payload.store == store)
        return parsed

    def _write_payload(
        self,
        payload: MemoryPayload,
        *,
        actor: MemoryWriteActor,
        target: MemoryTargetRef | None,
    ) -> MemoryTargetRef:
        if isinstance(payload, ServiceContextMemory):
            return self._write_service_context(payload, actor=actor, target=target)
        if isinstance(payload, UserPreferenceMemory):
            return self._write_user_preference(payload, actor=actor, target=target)
        if isinstance(payload, InvestigationPatternMemory):
            return self.investigation_pattern_store.save(
                payload,
                target_id=target.target_id if target else None,
                actor=actor,
            )
        raise TypeError(f"Unsupported memory payload: {type(payload)!r}")

    def _write_service_context(
        self,
        payload: ServiceContextMemory,
        *,
        actor: MemoryWriteActor,
        target: MemoryTargetRef | None,
    ) -> MemoryTargetRef:
        entity_id = target.entity_id if target and target.entity_id else _service_entity_id(
            payload
        )
        entity = EntityMemory(
            entity_id=entity_id,
            entity_type=SERVICE_CONTEXT_ENTITY_TYPE,
            name=payload.service_name,
            description=payload.summary,
            properties={
                "service_name": payload.service_name,
                **({"environment": payload.environment} if payload.environment else {}),
                "source": payload.source,
            },
            facts=[
                {"id": f"fact-{index + 1}", "content": fact}
                for index, fact in enumerate(payload.facts)
            ],
            namespace=SERVICE_CONTEXT_NAMESPACE,
            agent_id=actor.agent_id,
            team_id=actor.team_id,
        )
        self.db.upsert_learning(
            id=_service_context_learning_id(entity_id),
            learning_type=self.service_context_store.learning_type,
            content=entity.to_dict(),
            user_id=None,
            agent_id=actor.agent_id,
            team_id=actor.team_id,
            workflow_id=actor.workflow_id,
            session_id=actor.session_id,
            namespace=SERVICE_CONTEXT_NAMESPACE,
            entity_id=entity.entity_id,
            entity_type=entity.entity_type,
            metadata={"source": payload.source, "policy": "tianhai_memory_v1"},
        )
        return MemoryTargetRef(
            store=TianHaiMemoryStore.SERVICE_CONTEXT,
            storage_kind="agno_entity_memory",
            target_id=_service_context_learning_id(entity_id),
            namespace=SERVICE_CONTEXT_NAMESPACE,
            learning_type=self.service_context_store.learning_type,
            entity_id=entity.entity_id,
            entity_type=entity.entity_type,
        )

    def _write_user_preference(
        self,
        payload: UserPreferenceMemory,
        *,
        actor: MemoryWriteActor,
        target: MemoryTargetRef | None,
    ) -> MemoryTargetRef:
        memory = UserMemory(
            memory=f"User preference ({payload.preference_scope}): {payload.preference}",
            memory_id=target.target_id if target else None,
            topics=["tianhai", "user_preference", payload.preference_scope],
            user_id=payload.user_id,
            input=payload.source,
            agent_id=actor.agent_id,
            team_id=actor.team_id,
        )
        if target is not None:
            memory_id = self.memory_manager.replace_user_memory(
                memory_id=target.target_id,
                memory=memory,
                user_id=payload.user_id,
            )
        else:
            memory_id = self.memory_manager.add_user_memory(
                memory=memory,
                user_id=payload.user_id,
            )
        if memory_id is None:
            raise RuntimeError("Agno MemoryManager did not return a memory id")
        return MemoryTargetRef(
            store=TianHaiMemoryStore.USER_PREFERENCES,
            storage_kind="agno_user_memory",
            target_id=memory_id,
            user_id=payload.user_id,
        )

    def _save_write_record(self, record: MemoryWriteRecord) -> None:
        self.db.upsert_learning(
            id=record.write_id,
            learning_type=TIANHAI_MEMORY_WRITE_JOURNAL_TYPE,
            content=record.model_dump(mode="json"),
            user_id=record.actor.user_id,
            agent_id=record.actor.agent_id,
            team_id=record.actor.team_id,
            workflow_id=record.actor.workflow_id,
            session_id=record.actor.session_id,
            namespace=TIANHAI_MEMORY_WRITE_NAMESPACE,
            entity_id=record.write_id,
            entity_type=TIANHAI_MEMORY_WRITE_ENTITY_TYPE,
            metadata={"policy": "tianhai_memory_v1"},
        )


def create_memory_policy(*, db: object) -> TianHaiMemoryPolicy:
    return TianHaiMemoryPolicy(db=db)


def _create_service_context_store(*, db: object) -> EntityMemoryStore:
    return EntityMemoryStore(
        config=EntityMemoryConfig(
            db=db,
            mode=LearningMode.AGENTIC,
            namespace=SERVICE_CONTEXT_NAMESPACE,
            enable_agent_tools=False,
        )
    )


def _actor_with_source(
    actor: MemoryWriteActor,
    source_override: str | None,
) -> MemoryWriteActor:
    if source_override is None:
        return actor
    return actor.model_copy(update={"source": source_override})


def _ensure_same_correction_target(
    record: MemoryWriteRecord,
    corrected_payload: MemoryPayload,
) -> None:
    target = record.target
    if target is None:
        raise ValueError("applied memory write correction requires an existing target")
    if target.store != corrected_payload.store:
        raise ValueError("corrected memory payload must target the same store")

    if isinstance(corrected_payload, UserPreferenceMemory):
        if target.user_id != corrected_payload.user_id:
            raise ValueError(
                "user preference correction must target the same user_id"
            )
        return

    if isinstance(corrected_payload, ServiceContextMemory):
        expected_entity_id = _service_entity_id(corrected_payload)
        if target.entity_id != expected_entity_id:
            raise ValueError(
                "service context correction must target the same service_name "
                "and environment"
            )
        if target.target_id != _service_context_learning_id(expected_entity_id):
            raise ValueError("service context correction target id is inconsistent")
        return

    if isinstance(corrected_payload, InvestigationPatternMemory):
        if (
            target.storage_kind != "agno_learning"
            or target.learning_type != INVESTIGATION_PATTERN_LEARNING_TYPE
            or target.namespace != TianHaiMemoryStore.INVESTIGATION_PATTERNS.value
            or target.entity_id != target.target_id
            or target.entity_type != TianHaiMemoryStore.INVESTIGATION_PATTERNS.value
        ):
            raise ValueError(
                "investigation pattern correction must target the existing pattern"
            )
        return

    raise TypeError(f"Unsupported memory payload: {type(corrected_payload)!r}")


def _service_entity_id(payload: ServiceContextMemory) -> str:
    parts = [payload.service_name, payload.environment or "default"]
    normalized = "_".join(_normalize_identifier(part) for part in parts)
    return f"java_service_{normalized}"


def _normalize_identifier(value: str) -> str:
    chars = [ch.lower() if ch.isalnum() else "_" for ch in value.strip()]
    normalized = "_".join(part for part in "".join(chars).split("_") if part)
    return normalized or "unknown"


def _service_context_learning_id(entity_id: str) -> str:
    return f"entity_{SERVICE_CONTEXT_NAMESPACE}_{SERVICE_CONTEXT_ENTITY_TYPE}_{entity_id}"


__all__ = (
    "InvestigationPatternMemory",
    "MemoryPayload",
    "MemoryTargetRef",
    "MemoryWriteActor",
    "MemoryWriteCorrection",
    "MemoryWriteRecord",
    "ServiceContextMemory",
    "TianHaiInvestigationPatternStore",
    "TianHaiMemoryPolicy",
    "UserPreferenceMemory",
    "create_memory_policy",
)
