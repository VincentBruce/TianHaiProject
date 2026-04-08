from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from agno.knowledge.document import Document
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.base import VectorDb
from pydantic import Field, model_validator

from tianhai.domain import (
    KnowledgeEvidence,
    KnowledgeSourceType,
    LogAnalysisRequest,
    LogSource,
)
from tianhai.domain.logs import TianHaiDomainModel
from tianhai.knowledge.types import (
    TIANHAI_KNOWLEDGE_DOCUMENT_LEARNING_TYPE,
    TIANHAI_KNOWLEDGE_NAME,
    TIANHAI_KNOWLEDGE_NAMESPACE,
    TIANHAI_KNOWLEDGE_VECTOR_DB_NAME,
    TIANHAI_KNOWLEDGE_VECTOR_ENTITY_TYPE,
    TianHaiKnowledgeCorpus,
)


DEFAULT_KNOWLEDGE_MAX_RESULTS = 5


class TianHaiKnowledgeDocument(TianHaiDomainModel):
    corpus: TianHaiKnowledgeCorpus
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    document_id: str | None = None
    service_name: str | None = None
    environment: str | None = None
    issue_key: str | None = None
    tags: tuple[str, ...] = ()
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def service_notes_should_identify_service(self) -> TianHaiKnowledgeDocument:
        if (
            self.corpus == TianHaiKnowledgeCorpus.JAVA_SERVICE_NOTES
            and not self.service_name
        ):
            raise ValueError("java service notes require service_name")
        return self

    @property
    def resolved_document_id(self) -> str:
        return self.document_id or _stable_id(
            self.corpus.value,
            self.title,
            self.source_uri,
        )

    def to_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "corpus": self.corpus.value,
            "source_type": self.corpus.value,
            "document_id": self.resolved_document_id,
            "title": self.title,
            "source_uri": self.source_uri,
        }
        if self.service_name:
            metadata["service_name"] = self.service_name
        if self.environment:
            metadata["environment"] = self.environment
        if self.issue_key:
            metadata["issue_key"] = self.issue_key
        if self.tags:
            metadata["tags"] = list(self.tags)
        metadata.update(self.metadata)
        return metadata


class TianHaiKnowledgeQuery(TianHaiDomainModel):
    query: str = Field(min_length=1)
    corpora: tuple[TianHaiKnowledgeCorpus, ...] = ()
    service_name: str | None = None
    environment: str | None = None
    tags: tuple[str, ...] = ()
    max_results: int = Field(default=DEFAULT_KNOWLEDGE_MAX_RESULTS, ge=1, le=20)


class TianHaiKnowledgeRetrievalResult(TianHaiDomainModel):
    query: TianHaiKnowledgeQuery
    evidence: tuple[KnowledgeEvidence, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class _StoredKnowledgeDocument:
    learning_id: str
    content_hash: str
    document: Document


class TianHaiKnowledgeVectorDb(VectorDb):
    """Minimal Agno VectorDb baseline backed by TianHai's Agno database."""

    def __init__(
        self,
        *,
        db: object,
        name: str = TIANHAI_KNOWLEDGE_VECTOR_DB_NAME,
    ) -> None:
        self.db = db
        super().__init__(name=name, description="TianHai durable knowledge baseline.")

    def create(self) -> None:
        return None

    async def async_create(self) -> None:
        self.create()

    def exists(self) -> bool:
        return all(
            hasattr(self.db, method)
            for method in ("upsert_learning", "get_learnings", "delete_learning")
        )

    async def async_exists(self) -> bool:
        return self.exists()

    def name_exists(self, name: str) -> bool:
        return any(record.document.name == name for record in self._records())

    def async_name_exists(self, name: str) -> bool:
        return self.name_exists(name)

    def id_exists(self, id: str) -> bool:
        return any(
            record.document.id == id or record.learning_id == id
            for record in self._records()
        )

    def content_hash_exists(self, content_hash: str) -> bool:
        return bool(
            self.db.get_learnings(
                learning_type=TIANHAI_KNOWLEDGE_DOCUMENT_LEARNING_TYPE,
                namespace=TIANHAI_KNOWLEDGE_NAMESPACE,
                entity_id=content_hash,
                entity_type=TIANHAI_KNOWLEDGE_VECTOR_ENTITY_TYPE,
                limit=1,
            )
        )

    def insert(
        self,
        content_hash: str,
        documents: list[Document],
        filters: dict[str, Any] | None = None,
    ) -> None:
        self._write_documents(content_hash, documents, filters=filters)

    async def async_insert(
        self,
        content_hash: str,
        documents: list[Document],
        filters: dict[str, Any] | None = None,
    ) -> None:
        self.insert(content_hash, documents, filters=filters)

    def upsert_available(self) -> bool:
        return True

    def upsert(
        self,
        content_hash: str,
        documents: list[Document],
        filters: dict[str, Any] | None = None,
    ) -> None:
        self._delete_records(
            record
            for record in self._records(content_hash=content_hash)
        )
        self._write_documents(content_hash, documents, filters=filters)

    async def async_upsert(
        self,
        content_hash: str,
        documents: list[Document],
        filters: dict[str, Any] | None = None,
    ) -> None:
        self.upsert(content_hash, documents, filters=filters)

    def search(
        self,
        query: str,
        limit: int = DEFAULT_KNOWLEDGE_MAX_RESULTS,
        filters: Any | None = None,
    ) -> list[Document]:
        query_tokens = _tokenize(query)
        scored_documents: list[tuple[float, Document]] = []

        for record in self._records():
            document = record.document
            if not _matches_filters(document.meta_data, filters):
                continue

            score = _score_document(document, query_tokens, query)
            if score > 0 or not query_tokens:
                document.reranking_score = score
                scored_documents.append((score, document))

        scored_documents.sort(
            key=lambda item: (
                item[0],
                item[1].meta_data.get("title") or item[1].name or "",
            ),
            reverse=True,
        )
        return [document for _, document in scored_documents[:limit]]

    async def async_search(
        self,
        query: str,
        limit: int = DEFAULT_KNOWLEDGE_MAX_RESULTS,
        filters: Any | None = None,
    ) -> list[Document]:
        return self.search(query, limit=limit, filters=filters)

    def drop(self) -> None:
        self.delete()

    async def async_drop(self) -> None:
        self.drop()

    def delete(self) -> bool:
        return self._delete_records(self._records())

    def delete_by_id(self, id: str) -> bool:
        return self._delete_records(
            record
            for record in self._records()
            if record.document.id == id or record.learning_id == id
        )

    def delete_by_name(self, name: str) -> bool:
        return self._delete_records(
            record for record in self._records() if record.document.name == name
        )

    def delete_by_metadata(self, metadata: dict[str, Any]) -> bool:
        return self._delete_records(
            record
            for record in self._records()
            if _metadata_contains(record.document.meta_data, metadata)
        )

    def update_metadata(self, content_id: str, metadata: dict[str, Any]) -> None:
        for record in self._records():
            if record.document.content_id != content_id:
                continue
            document = record.document
            document.meta_data.update(metadata)
            self._write_record(record.content_hash, record.learning_id, document)

    def delete_by_content_id(self, content_id: str) -> bool:
        return self._delete_records(
            record
            for record in self._records()
            if record.document.content_id == content_id
        )

    def get_supported_search_types(self) -> list[str]:
        return ["keyword"]

    def _write_documents(
        self,
        content_hash: str,
        documents: list[Document],
        *,
        filters: dict[str, Any] | None,
    ) -> None:
        for index, document in enumerate(documents):
            document_id = document.id or _stable_id(
                content_hash,
                str(index),
                document.content,
            )
            document.id = document_id
            metadata = {**(filters or {}), **document.meta_data}
            document.meta_data = metadata
            learning_id = _learning_id(content_hash, index)
            self._write_record(content_hash, learning_id, document)

    def _write_record(
        self,
        content_hash: str,
        learning_id: str,
        document: Document,
    ) -> None:
        content = {
            "content_hash": content_hash,
            "document": _document_to_dict(document),
        }
        metadata = {
            "content_hash": content_hash,
            "document_id": document.id,
            **document.meta_data,
        }
        self.db.upsert_learning(
            id=learning_id,
            learning_type=TIANHAI_KNOWLEDGE_DOCUMENT_LEARNING_TYPE,
            content=content,
            namespace=TIANHAI_KNOWLEDGE_NAMESPACE,
            entity_id=content_hash,
            entity_type=TIANHAI_KNOWLEDGE_VECTOR_ENTITY_TYPE,
            metadata=metadata,
        )

    def _records(
        self,
        *,
        content_hash: str | None = None,
        limit: int = 1000,
    ) -> tuple[_StoredKnowledgeDocument, ...]:
        records = self.db.get_learnings(
            learning_type=TIANHAI_KNOWLEDGE_DOCUMENT_LEARNING_TYPE,
            namespace=TIANHAI_KNOWLEDGE_NAMESPACE,
            entity_id=content_hash,
            entity_type=(
                TIANHAI_KNOWLEDGE_VECTOR_ENTITY_TYPE if content_hash else None
            ),
            limit=limit,
        )
        parsed: list[_StoredKnowledgeDocument] = []
        for record in records:
            content = record.get("content") if isinstance(record, dict) else None
            if not isinstance(content, dict):
                continue
            document_data = content.get("document")
            if not isinstance(document_data, dict):
                continue
            parsed.append(
                _StoredKnowledgeDocument(
                    learning_id=record["learning_id"],
                    content_hash=content["content_hash"],
                    document=Document.from_dict(document_data),
                )
            )
        return tuple(parsed)

    def _delete_records(
        self,
        records: Iterable[_StoredKnowledgeDocument],
    ) -> bool:
        deleted = False
        for record in tuple(records):
            deleted = self.db.delete_learning(record.learning_id) or deleted
        return deleted


class TianHaiKnowledgeBase:
    """TianHai knowledge retrieval service, separated from user memory."""

    def __init__(
        self,
        *,
        db: object,
        knowledge: Knowledge | None = None,
        max_results: int = DEFAULT_KNOWLEDGE_MAX_RESULTS,
    ) -> None:
        self.db = db
        self.max_results = max_results
        self.knowledge = knowledge or Knowledge(
            name=TIANHAI_KNOWLEDGE_NAME,
            description=(
                "TianHai durable runbook and documentation knowledge baseline."
            ),
            vector_db=TianHaiKnowledgeVectorDb(db=db),
            contents_db=db,
            max_results=max_results,
            isolate_vector_search=True,
        )

    def add_document(
        self,
        document: TianHaiKnowledgeDocument,
        *,
        upsert: bool = True,
        skip_if_exists: bool = False,
    ) -> None:
        self.knowledge.insert(
            name=document.title,
            description=f"{document.corpus.value}: {document.title}",
            text_content=document.body,
            metadata=document.to_metadata(),
            upsert=upsert,
            skip_if_exists=skip_if_exists,
        )

    def search(
        self,
        query: TianHaiKnowledgeQuery,
    ) -> TianHaiKnowledgeRetrievalResult:
        filters = _filters_from_query(query)
        documents = self.knowledge.search(
            query=query.query,
            max_results=query.max_results,
            filters=filters or None,
        )
        evidence = tuple(_knowledge_evidence_from_document(document) for document in documents)
        limitations = ()
        if not evidence:
            limitations = (
                "No TianHai durable knowledge matched the current query.",
            )
        return TianHaiKnowledgeRetrievalResult(
            query=query,
            evidence=evidence,
            limitations=limitations,
        )

    def retrieve_for_log_analysis(
        self,
        request: LogAnalysisRequest,
        *,
        max_results: int | None = None,
    ) -> TianHaiKnowledgeRetrievalResult:
        query = TianHaiKnowledgeQuery(
            query=_knowledge_query_text(request),
            max_results=max_results or self.max_results,
        )
        return self.search(query)


def create_knowledge_base(
    *,
    db: object,
    max_results: int = DEFAULT_KNOWLEDGE_MAX_RESULTS,
) -> TianHaiKnowledgeBase:
    return TianHaiKnowledgeBase(db=db, max_results=max_results)


def _filters_from_query(query: TianHaiKnowledgeQuery) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if query.corpora:
        filters["corpus"] = [corpus.value for corpus in query.corpora]
    if query.service_name:
        filters["service_name"] = query.service_name
    if query.environment:
        filters["environment"] = query.environment
    if query.tags:
        filters["tags"] = list(query.tags)
    return filters


def _knowledge_evidence_from_document(document: Document) -> KnowledgeEvidence:
    metadata = document.meta_data
    source_type = KnowledgeSourceType(
        metadata.get("source_type") or metadata.get("corpus")
    )
    document_id = metadata.get("document_id") or document.id
    return KnowledgeEvidence(
        id=f"kb-{document_id}",
        summary=_summary(document.content),
        source_type=source_type,
        title=metadata.get("title") or document.name or "Untitled knowledge",
        excerpt=_excerpt(document.content),
        source_uri=metadata.get("source_uri"),
        document_id=document_id,
        service_name=metadata.get("service_name"),
        environment=metadata.get("environment"),
        score=document.reranking_score,
        metadata=_string_metadata(metadata),
    )


def _knowledge_query_text(request: LogAnalysisRequest) -> str:
    parts = [request.question]
    source = _request_source(request)
    if source is not None:
        parts.append(source.service_name)
        if source.environment:
            parts.append(source.environment)
    if request.service_context:
        parts.append(request.service_context)
    if request.log_batch.raw_excerpt:
        parts.append(request.log_batch.raw_excerpt[:1000])
    for entry in request.log_batch.entries:
        parts.append(entry.message)
        if entry.exception is not None:
            parts.append(entry.exception.type_name)
            if entry.exception.message:
                parts.append(entry.exception.message)
    return "\n".join(parts)


def _request_source(request: LogAnalysisRequest) -> LogSource | None:
    if request.log_batch.source is not None:
        return request.log_batch.source
    for entry in request.log_batch.entries:
        if entry.source is not None:
            return entry.source
    return None


def _matches_filters(metadata: dict[str, Any], filters: Any | None) -> bool:
    if not filters:
        return True
    if isinstance(filters, dict):
        return all(
            _matches_filter_value(metadata.get(key.split(".")[-1]), expected)
            for key, expected in filters.items()
        )
    if isinstance(filters, list):
        for filter_item in filters:
            key = getattr(filter_item, "key", None)
            value = getattr(filter_item, "value", None)
            if key is not None and not _matches_filter_value(
                metadata.get(str(key).split(".")[-1]),
                value,
            ):
                return False
        return True
    return True


def _matches_filter_value(actual: Any, expected: Any) -> bool:
    if expected is None:
        return True
    if isinstance(expected, (list, tuple, set, frozenset)):
        return any(_matches_filter_value(actual, item) for item in expected)
    if isinstance(actual, (list, tuple, set, frozenset)):
        return any(_matches_filter_value(item, expected) for item in actual)
    if actual is None:
        return False
    return str(actual).casefold() == str(expected).casefold()


def _metadata_contains(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(
        _matches_filter_value(actual.get(key), value)
        for key, value in expected.items()
    )


def _score_document(
    document: Document,
    query_tokens: set[str],
    query: str,
) -> float:
    haystack = " ".join(
        [
            document.content,
            document.name or "",
            " ".join(str(value) for value in document.meta_data.values()),
        ]
    )
    haystack_tokens = _tokenize(haystack)
    overlap = query_tokens & haystack_tokens
    score = float(len(overlap))
    if query.strip() and query.casefold() in haystack.casefold():
        score += 2.0
    return score


def _tokenize(value: str) -> set[str]:
    normalized = "".join(ch.casefold() if ch.isalnum() else " " for ch in value)
    return {token for token in normalized.split() if len(token) > 1}


def _summary(content: str) -> str:
    first_line = next(
        (line.strip() for line in content.splitlines() if line.strip()),
        content.strip(),
    )
    return _truncate(first_line, 240) or "Knowledge evidence matched the query."


def _excerpt(content: str) -> str:
    return _truncate(" ".join(content.split()), 500)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def _string_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    return {
        key: ", ".join(str(item) for item in value)
        if isinstance(value, (list, tuple))
        else str(value)
        for key, value in metadata.items()
        if value is not None and key not in {"linked_to"}
    }


def _document_to_dict(document: Document) -> dict[str, Any]:
    return {
        "content": document.content,
        "id": document.id,
        "name": document.name,
        "meta_data": document.meta_data,
        "reranking_score": document.reranking_score,
        "content_id": document.content_id,
        "content_origin": document.content_origin,
        "size": document.size,
    }


def _learning_id(content_hash: str, index: int) -> str:
    return f"{TIANHAI_KNOWLEDGE_DOCUMENT_LEARNING_TYPE}:{content_hash}:{index}"


def _stable_id(*parts: str) -> str:
    digest = sha256("::".join(parts).encode("utf-8")).hexdigest()[:16]
    return digest


__all__ = (
    "DEFAULT_KNOWLEDGE_MAX_RESULTS",
    "TianHaiKnowledgeBase",
    "TianHaiKnowledgeDocument",
    "TianHaiKnowledgeQuery",
    "TianHaiKnowledgeRetrievalResult",
    "TianHaiKnowledgeVectorDb",
    "create_knowledge_base",
)
