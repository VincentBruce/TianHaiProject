from __future__ import annotations

from tianhai.domain.diagnosis import KnowledgeSourceType


TIANHAI_KNOWLEDGE_NAME = "tianhai-knowledge-baseline"
TIANHAI_KNOWLEDGE_VECTOR_DB_NAME = "TianHai Knowledge Baseline"
TIANHAI_KNOWLEDGE_NAMESPACE = "tianhai_knowledge"
TIANHAI_KNOWLEDGE_DOCUMENT_LEARNING_TYPE = "tianhai_knowledge_document"
TIANHAI_KNOWLEDGE_VECTOR_ENTITY_TYPE = "knowledge_document"

TianHaiKnowledgeCorpus = KnowledgeSourceType


__all__ = (
    "TIANHAI_KNOWLEDGE_DOCUMENT_LEARNING_TYPE",
    "TIANHAI_KNOWLEDGE_NAME",
    "TIANHAI_KNOWLEDGE_NAMESPACE",
    "TIANHAI_KNOWLEDGE_VECTOR_DB_NAME",
    "TIANHAI_KNOWLEDGE_VECTOR_ENTITY_TYPE",
    "TianHaiKnowledgeCorpus",
)
