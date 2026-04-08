from __future__ import annotations

from enum import StrEnum


SERVICE_CONTEXT_NAMESPACE = "tianhai_service_context"
SERVICE_CONTEXT_ENTITY_TYPE = "java_service"
INVESTIGATION_PATTERN_LEARNING_TYPE = "tianhai_investigation_pattern"
TIANHAI_MEMORY_WRITE_JOURNAL_TYPE = "tianhai_memory_write_record"
TIANHAI_MEMORY_WRITE_NAMESPACE = "tianhai_memory_policy"
TIANHAI_MEMORY_WRITE_ENTITY_TYPE = "memory_write"


class TianHaiMemoryStore(StrEnum):
    SERVICE_CONTEXT = "service_context"
    USER_PREFERENCES = "user_preferences"
    INVESTIGATION_PATTERNS = "investigation_patterns"


class TianHaiMemoryWriteStatus(StrEnum):
    PROPOSED = "proposed"
    APPLIED = "applied"
    REJECTED = "rejected"
    CORRECTED = "corrected"


__all__ = (
    "INVESTIGATION_PATTERN_LEARNING_TYPE",
    "SERVICE_CONTEXT_ENTITY_TYPE",
    "SERVICE_CONTEXT_NAMESPACE",
    "TIANHAI_MEMORY_WRITE_ENTITY_TYPE",
    "TIANHAI_MEMORY_WRITE_JOURNAL_TYPE",
    "TIANHAI_MEMORY_WRITE_NAMESPACE",
    "TianHaiMemoryStore",
    "TianHaiMemoryWriteStatus",
)
