from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TianHaiDomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)


class LogSeverity(StrEnum):
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"
    UNKNOWN = "UNKNOWN"


class LogSource(TianHaiDomainModel):
    service_name: str = Field(min_length=1)
    environment: str | None = None
    host: str | None = None
    instance_id: str | None = None
    file_path: str | None = None


class LogPosition(TianHaiDomainModel):
    line_number: int | None = Field(default=None, ge=1)
    byte_offset: int | None = Field(default=None, ge=0)


class LogTimeRange(TianHaiDomainModel):
    start: datetime | None = None
    end: datetime | None = None

    @model_validator(mode="after")
    def end_must_not_precede_start(self) -> LogTimeRange:
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError("log time range end must not precede start")
        return self


class JavaStackFrame(TianHaiDomainModel):
    class_name: str = Field(min_length=1)
    method_name: str = Field(min_length=1)
    file_name: str | None = None
    line_number: int | None = Field(default=None, ge=1)
    module_name: str | None = None
    native_method: bool = False


class JavaException(TianHaiDomainModel):
    type_name: str = Field(min_length=1)
    message: str | None = None
    stack_frames: tuple[JavaStackFrame, ...] = ()
    caused_by: JavaException | None = None
    suppressed: tuple[JavaException, ...] = ()


class JavaLogEntry(TianHaiDomainModel):
    message: str
    severity: LogSeverity = LogSeverity.UNKNOWN
    timestamp: datetime | None = None
    logger_name: str | None = None
    thread_name: str | None = None
    source: LogSource | None = None
    position: LogPosition | None = None
    exception: JavaException | None = None
    attributes: dict[str, str] = Field(default_factory=dict)


class JavaLogBatch(TianHaiDomainModel):
    entries: tuple[JavaLogEntry, ...] = ()
    raw_excerpt: str | None = None
    source: LogSource | None = None
    time_range: LogTimeRange | None = None
    correlation_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_entries_or_raw_excerpt(self) -> JavaLogBatch:
        if not self.entries and not self.raw_excerpt:
            raise ValueError("log batch requires entries or raw_excerpt")
        return self
