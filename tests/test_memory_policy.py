from pathlib import Path

import pytest

from tianhai.config import TianHaiSettings
from tianhai.memory import (
    InvestigationPatternMemory,
    MemoryWriteActor,
    ServiceContextMemory,
    TianHaiMemoryPolicy,
    TianHaiMemoryStore,
    TianHaiMemoryWriteStatus,
    UserPreferenceMemory,
    create_memory_policy,
)
from tianhai.runtime import create_db


def test_memory_policy_proposes_writes_without_applying_to_memory_store(
    tmp_path: Path,
) -> None:
    policy = _memory_policy(tmp_path)

    record = policy.propose_write(
        UserPreferenceMemory(
            user_id="alice",
            preference="Prefer concise incident summaries.",
            preference_scope="report_style",
            source="user correction",
        ),
        actor=MemoryWriteActor(user_id="alice", agent_id="tianhai-primary-agent"),
    )

    inspected = policy.inspect_write(record.write_id)

    assert inspected.status == TianHaiMemoryWriteStatus.PROPOSED
    assert inspected.target is None
    assert policy.memory_manager.get_user_memories(user_id="alice") == []
    assert policy.list_writes(store=TianHaiMemoryStore.USER_PREFERENCES) == (
        inspected,
    )


def test_memory_policy_applies_store_specific_write_targets(tmp_path: Path) -> None:
    policy = _memory_policy(tmp_path)

    service_write = policy.apply_write(
        policy.propose_write(
            ServiceContextMemory(
                service_name="checkout",
                environment="prod",
                summary="Checkout Java service.",
                facts=(
                    "Uses HikariCP for JDBC pool management.",
                    "Database lock waits are a known timeout symptom.",
                ),
                source="operator supplied service context",
            ),
            actor=MemoryWriteActor(workflow_id="tianhai-incident-diagnosis-workflow"),
        ).write_id
    )
    user_write = policy.apply_write(
        policy.propose_write(
            UserPreferenceMemory(
                user_id="alice",
                preference="Prefer recommended actions before caveats.",
                preference_scope="report_style",
                source="user preference",
            )
        ).write_id
    )
    pattern_write = policy.apply_write(
        policy.propose_write(
            InvestigationPatternMemory(
                pattern_name="SQL timeout triage",
                pattern=(
                    "Check connection pool saturation before changing JDBC "
                    "driver retry settings."
                ),
                applies_to=("java.sql.SQLTimeoutException",),
                evidence=("Repeated checkout incidents resolved after pool sizing.",),
                source_incident_id="inc-sql-timeout",
                source="completed incident review",
            )
        ).write_id
    )

    service_entity = policy.service_context_store.get(
        entity_id=service_write.target.entity_id,
        entity_type=service_write.target.entity_type,
        namespace=service_write.target.namespace,
    )
    user_memories = policy.memory_manager.get_user_memories(user_id="alice")
    pattern = policy.investigation_pattern_store.get(pattern_write.target.target_id)

    assert service_write.status == TianHaiMemoryWriteStatus.APPLIED
    assert service_write.target.storage_kind == "agno_entity_memory"
    assert service_entity is not None
    assert service_entity.name == "checkout"
    assert service_entity.properties["environment"] == "prod"
    assert service_entity.facts[0]["content"] == "Uses HikariCP for JDBC pool management."
    assert user_write.target.storage_kind == "agno_user_memory"
    assert user_memories[0].memory == (
        "User preference (report_style): Prefer recommended actions before caveats."
    )
    assert pattern_write.target.storage_kind == "agno_learning"
    assert pattern is not None
    assert pattern.pattern_name == "SQL timeout triage"


def test_memory_policy_corrects_applied_write_in_same_store_target(
    tmp_path: Path,
) -> None:
    policy = _memory_policy(tmp_path)
    applied = policy.apply_write(
        policy.propose_write(
            UserPreferenceMemory(
                user_id="alice",
                preference="Prefer short reports.",
                preference_scope="report_style",
                source="user preference",
            )
        ).write_id
    )

    corrected = policy.correct_write(
        applied.write_id,
        corrected_payload=UserPreferenceMemory(
            user_id="alice",
            preference="Prefer concise reports with action items.",
            preference_scope="report_style",
            source="user correction",
        ),
        reason="User clarified the preference.",
        corrected_by="alice",
    )

    memory = policy.memory_manager.get_user_memory(
        applied.target.target_id,
        user_id="alice",
    )

    assert corrected.status == TianHaiMemoryWriteStatus.CORRECTED
    assert corrected.target == applied.target
    assert corrected.corrections[0].reason == "User clarified the preference."
    assert memory is not None
    assert memory.memory == (
        "User preference (report_style): Prefer concise reports with action items."
    )


def test_memory_policy_rejects_user_preference_correction_for_different_user(
    tmp_path: Path,
) -> None:
    policy = _memory_policy(tmp_path)
    applied = policy.apply_write(
        policy.propose_write(
            UserPreferenceMemory(
                user_id="alice",
                preference="Prefer short reports.",
                preference_scope="report_style",
                source="user preference",
            )
        ).write_id
    )

    with pytest.raises(ValueError, match="same user_id"):
        policy.correct_write(
            applied.write_id,
            corrected_payload=UserPreferenceMemory(
                user_id="bob",
                preference="Prefer verbose reports.",
                preference_scope="report_style",
                source="invalid user correction",
            ),
            reason="Invalid correction attempted against another user.",
        )

    assert policy.inspect_write(applied.write_id).status == (
        TianHaiMemoryWriteStatus.APPLIED
    )
    assert policy.memory_manager.get_user_memories(user_id="bob") == []
    alice_memory = policy.memory_manager.get_user_memory(
        applied.target.target_id,
        user_id="alice",
    )
    assert alice_memory is not None
    assert alice_memory.memory == "User preference (report_style): Prefer short reports."


def test_memory_policy_correction_replaces_service_context_snapshot(
    tmp_path: Path,
) -> None:
    policy = _memory_policy(tmp_path)
    applied = policy.apply_write(
        policy.propose_write(
            ServiceContextMemory(
                service_name="checkout",
                facts=("Uses an unknown JDBC pool.",),
                source="operator note",
            )
        ).write_id
    )

    corrected = policy.correct_write(
        applied.write_id,
        corrected_payload=ServiceContextMemory(
            service_name="checkout",
            facts=("Uses HikariCP for JDBC pool management.",),
            source="operator correction",
        ),
        reason="Operator corrected the JDBC pool detail.",
    )
    service_entity = policy.service_context_store.get(
        entity_id=applied.target.entity_id,
        entity_type=applied.target.entity_type,
        namespace=applied.target.namespace,
    )

    assert corrected.status == TianHaiMemoryWriteStatus.CORRECTED
    assert service_entity is not None
    assert service_entity.facts == [
        {"id": "fact-1", "content": "Uses HikariCP for JDBC pool management."}
    ]


@pytest.mark.parametrize(
    "corrected_payload",
    (
        ServiceContextMemory(
            service_name="billing",
            environment="prod",
            facts=("Uses HikariCP for JDBC pool management.",),
            source="invalid service correction",
        ),
        ServiceContextMemory(
            service_name="checkout",
            environment="staging",
            facts=("Uses HikariCP for JDBC pool management.",),
            source="invalid environment correction",
        ),
    ),
)
def test_memory_policy_rejects_service_context_correction_for_different_target(
    tmp_path: Path,
    corrected_payload: ServiceContextMemory,
) -> None:
    policy = _memory_policy(tmp_path)
    applied = policy.apply_write(
        policy.propose_write(
            ServiceContextMemory(
                service_name="checkout",
                environment="prod",
                facts=("Uses an unknown JDBC pool.",),
                source="operator note",
            )
        ).write_id
    )

    with pytest.raises(ValueError, match="same service_name and environment"):
        policy.correct_write(
            applied.write_id,
            corrected_payload=corrected_payload,
            reason="Invalid correction attempted against another service target.",
        )

    service_entity = policy.service_context_store.get(
        entity_id=applied.target.entity_id,
        entity_type=applied.target.entity_type,
        namespace=applied.target.namespace,
    )

    assert policy.inspect_write(applied.write_id).status == (
        TianHaiMemoryWriteStatus.APPLIED
    )
    assert service_entity is not None
    assert service_entity.name == "checkout"
    assert service_entity.properties["environment"] == "prod"
    assert service_entity.facts == [
        {"id": "fact-1", "content": "Uses an unknown JDBC pool."}
    ]


def test_memory_policy_rejects_proposed_write_without_store_write(
    tmp_path: Path,
) -> None:
    policy = _memory_policy(tmp_path)
    proposed = policy.propose_write(
        UserPreferenceMemory(
            user_id="alice",
            preference="Remember this one-off debugging note.",
            preference_scope="debugging",
            source="operator rejected",
        )
    )

    rejected = policy.reject_write(
        proposed.write_id,
        reason="One-off debugging note is not durable user preference.",
    )

    assert rejected.status == TianHaiMemoryWriteStatus.REJECTED
    assert rejected.rejection_reason == (
        "One-off debugging note is not durable user preference."
    )
    assert policy.memory_manager.get_user_memories(user_id="alice") == []
    with pytest.raises(ValueError):
        policy.apply_write(proposed.write_id)


def test_memory_policy_rejects_cross_store_correction(tmp_path: Path) -> None:
    policy = _memory_policy(tmp_path)
    applied = policy.apply_write(
        policy.propose_write(
            UserPreferenceMemory(
                user_id="alice",
                preference="Prefer concise reports.",
                preference_scope="report_style",
                source="user preference",
            )
        ).write_id
    )

    with pytest.raises(ValueError, match="same store"):
        policy.correct_write(
            applied.write_id,
            corrected_payload=ServiceContextMemory(
                service_name="checkout",
                facts=("Uses HikariCP.",),
                source="invalid correction",
            ),
            reason="Invalid cross-store correction.",
        )


def _memory_policy(tmp_path: Path) -> TianHaiMemoryPolicy:
    db = create_db(TianHaiSettings(sqlite_db_file=str(tmp_path / "memory.db")))
    return create_memory_policy(db=db)
