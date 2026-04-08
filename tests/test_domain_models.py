from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tianhai.domain import (
    JavaException,
    JavaLogBatch,
    JavaLogEntry,
    JavaStackFrame,
    LogSeverity,
    LogSource,
    LogTimeRange,
)


def test_java_log_entry_keeps_exception_structure_typed() -> None:
    frame = JavaStackFrame(
        class_name="com.example.orders.OrderService",
        method_name="submit",
        file_name="OrderService.java",
        line_number=42,
    )
    cause = JavaException(type_name="java.sql.SQLTimeoutException")
    exception = JavaException(
        type_name="java.lang.RuntimeException",
        message="submit failed",
        stack_frames=(frame,),
        caused_by=cause,
    )

    entry = JavaLogEntry(
        timestamp=datetime(2026, 4, 8, 1, 2, 3, tzinfo=UTC),
        severity=LogSeverity.ERROR,
        logger_name="com.example.orders.OrderService",
        thread_name="http-nio-8080-exec-4",
        message="submit failed",
        source=LogSource(service_name="orders"),
        exception=exception,
    )

    assert entry.exception is not None
    assert entry.exception.caused_by == cause
    assert entry.exception.stack_frames[0].line_number == 42


def test_log_time_range_rejects_inverted_ranges() -> None:
    with pytest.raises(ValidationError):
        LogTimeRange(
            start=datetime(2026, 4, 8, 2, 0, tzinfo=UTC),
            end=datetime(2026, 4, 8, 1, 0, tzinfo=UTC),
        )


def test_log_batch_requires_entries_or_raw_excerpt() -> None:
    with pytest.raises(ValidationError):
        JavaLogBatch()

    batch = JavaLogBatch(raw_excerpt="2026-04-08 ERROR submit failed")

    assert batch.raw_excerpt is not None
