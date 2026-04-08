from pathlib import Path

from agno.knowledge.knowledge import Knowledge

from tianhai.config import TianHaiSettings
from tianhai.domain import JavaLogBatch, KnowledgeSourceType, LogAnalysisRequest, LogSource
from tianhai.knowledge import (
    TIANHAI_KNOWLEDGE_DOCUMENT_LEARNING_TYPE,
    TIANHAI_KNOWLEDGE_NAMESPACE,
    TianHaiKnowledgeBase,
    TianHaiKnowledgeCorpus,
    TianHaiKnowledgeDocument,
    TianHaiKnowledgeQuery,
    TianHaiKnowledgeVectorDb,
    create_knowledge_base,
)
from tianhai.memory import TIANHAI_MEMORY_WRITE_JOURNAL_TYPE, create_memory_policy
from tianhai.runtime import create_db


def test_knowledge_baseline_uses_agno_knowledge_separate_from_memory(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    knowledge_base = create_knowledge_base(db=db)
    memory_policy = create_memory_policy(db=db)

    knowledge_base.add_document(
        TianHaiKnowledgeDocument(
            corpus=TianHaiKnowledgeCorpus.JAVA_SERVICE_NOTES,
            title="Checkout JDBC pool notes",
            body="Checkout uses HikariCP; SQL timeouts often follow pool saturation.",
            source_uri="runbooks/checkout.md",
            service_name="checkout",
            environment="prod",
            tags=("jdbc", "hikaricp"),
        )
    )

    result = knowledge_base.search(
        TianHaiKnowledgeQuery(
            query="checkout HikariCP SQL timeout",
            service_name="checkout",
            environment="prod",
        )
    )
    stored_records = db.get_learnings(
        learning_type=TIANHAI_KNOWLEDGE_DOCUMENT_LEARNING_TYPE,
        namespace=TIANHAI_KNOWLEDGE_NAMESPACE,
    )

    assert isinstance(knowledge_base, TianHaiKnowledgeBase)
    assert isinstance(knowledge_base.knowledge, Knowledge)
    assert isinstance(knowledge_base.knowledge.vector_db, TianHaiKnowledgeVectorDb)
    assert result.evidence[0].source_type == KnowledgeSourceType.JAVA_SERVICE_NOTES
    assert result.evidence[0].service_name == "checkout"
    assert stored_records
    assert memory_policy.list_writes() == ()
    assert db.get_learnings(
        learning_type=TIANHAI_MEMORY_WRITE_JOURNAL_TYPE,
    ) == []


def test_knowledge_retrieval_filters_supported_phase6_corpora(
    tmp_path: Path,
) -> None:
    knowledge_base = create_knowledge_base(db=_db(tmp_path))
    knowledge_base.add_document(
        TianHaiKnowledgeDocument(
            corpus=TianHaiKnowledgeCorpus.JAVA_SERVICE_NOTES,
            title="Checkout service notes",
            body="Checkout uses HikariCP and emits SQLTimeoutException on saturation.",
            source_uri="runbooks/checkout.md",
            service_name="checkout",
        )
    )
    knowledge_base.add_document(
        TianHaiKnowledgeDocument(
            corpus=TianHaiKnowledgeCorpus.KNOWN_ISSUES,
            title="Known issue KI-42",
            body="SQLTimeoutException KI-42 is mitigated by reviewing lock waits.",
            source_uri="known-issues/KI-42.md",
            issue_key="KI-42",
        )
    )
    knowledge_base.add_document(
        TianHaiKnowledgeDocument(
            corpus=TianHaiKnowledgeCorpus.AGNO_DOCUMENTATION,
            title="Agno Knowledge overview",
            body="Agno Knowledge is configured with Knowledge, vector_db, and contents_db.",
            source_uri="/Users/lisztf./Documents/Agno AgentOS/docs.agno.com/knowledge/overview.html",
            tags=("agno", "knowledge"),
        )
    )

    known_issue = knowledge_base.search(
        TianHaiKnowledgeQuery(
            query="SQLTimeoutException KI-42",
            corpora=(TianHaiKnowledgeCorpus.KNOWN_ISSUES,),
        )
    )
    checkout_note = knowledge_base.search(
        TianHaiKnowledgeQuery(
            query="HikariCP",
            service_name="checkout",
        )
    )
    agno_doc = knowledge_base.search(
        TianHaiKnowledgeQuery(
            query="Knowledge vector_db contents_db",
            corpora=(TianHaiKnowledgeCorpus.AGNO_DOCUMENTATION,),
        )
    )

    assert known_issue.evidence[0].source_type == KnowledgeSourceType.KNOWN_ISSUES
    assert known_issue.evidence[0].title == "Known issue KI-42"
    assert checkout_note.evidence[0].source_type == (
        KnowledgeSourceType.JAVA_SERVICE_NOTES
    )
    assert checkout_note.evidence[0].service_name == "checkout"
    assert agno_doc.evidence[0].source_type == KnowledgeSourceType.AGNO_DOCUMENTATION
    assert "docs.agno.com" in agno_doc.evidence[0].source_uri


def test_knowledge_retrieval_for_log_analysis_returns_evidence(
    tmp_path: Path,
) -> None:
    knowledge_base = create_knowledge_base(db=_db(tmp_path))
    knowledge_base.add_document(
        TianHaiKnowledgeDocument(
            corpus=TianHaiKnowledgeCorpus.JAVA_SERVICE_NOTES,
            title="Checkout timeout runbook",
            body=(
                "For checkout SQLTimeoutException, inspect HikariCP active "
                "connections before changing JDBC retry behavior."
            ),
            source_uri="runbooks/checkout-timeout.md",
            service_name="checkout",
        )
    )

    result = knowledge_base.retrieve_for_log_analysis(
        LogAnalysisRequest(
            question="Why is checkout failing?",
            log_batch=JavaLogBatch(
                raw_excerpt="ERROR java.sql.SQLTimeoutException",
                source=LogSource(service_name="checkout"),
            ),
        )
    )

    assert result.evidence[0].id.startswith("kb-")
    assert result.evidence[0].title == "Checkout timeout runbook"
    assert result.evidence[0].source_type == KnowledgeSourceType.JAVA_SERVICE_NOTES


def _db(tmp_path: Path) -> object:
    return create_db(TianHaiSettings(sqlite_db_file=str(tmp_path / "knowledge.db")))
