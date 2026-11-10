"""
aegis-lite ReasoningTrace
Captures, stores, and exports reasoning traces for explainability (XAI).
Supports multiple export formats per RigorMode.
"""

from __future__ import annotations
import asyncio
import json
import uuid
import gzip
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from contextvars import ContextVar

from .rigor import get_rigor_mode, ReasoningTraceConfig

logger = logging.getLogger(__name__)


# Context variable for current trace
_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar("current_trace", default=None)


class TraceEventType(Enum):
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    DECISION = "decision"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    LLM_CALL = "llm_call"
    LLM_RESPONSE = "llm_response"
    CONFIDENCE_CHECK = "confidence_check"
    FALLBACK = "fallback"
    GUARDRAIL = "guardrail"
    ERROR = "error"
    CUSTOM = "custom"


@dataclass
class TraceEvent:
    event_id: str
    event_type: TraceEventType
    timestamp: datetime
    agent_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceContext:
    trace_id: str
    root_agent_id: str
    session_id: str
    events: List[TraceEvent] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    _depth: int = 0
    _active_spans: Dict[str, datetime] = field(default_factory=dict)
    
    def add_event(self, event: TraceEvent) -> None:
        self.events.append(event)
    
    def get_events(self, event_type: Optional[TraceEventType] = None) -> List[TraceEvent]:
        if event_type:
            return [e for e in self.events if e.event_type == event_type]
        return self.events
    
    def duration_ms(self) -> Optional[float]:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None


class TraceStorage(ABC):
    """Abstract trace storage backend."""
    
    @abstractmethod
    async def save(self, trace: TraceContext) -> None:
        pass
    
    @abstractmethod
    async def load(self, trace_id: str) -> Optional[TraceContext]:
        pass
    
    @abstractmethod
    async def query(
        self,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[TraceContext]:
        pass


class MemoryTraceStorage(TraceStorage):
    """In-memory trace storage for demo mode."""
    
    def __init__(self, max_traces: int = 1000):
        self._traces: Dict[str, TraceContext] = {}
        self._max_traces = max_traces
    
    async def save(self, trace: TraceContext) -> None:
        self._traces[trace.trace_id] = trace
        if len(self._traces) > self._max_traces:
            # Remove oldest
            oldest = min(self._traces.values(), key=lambda t: t.start_time)
            del self._traces[oldest.trace_id]
    
    async def load(self, trace_id: str) -> Optional[TraceContext]:
        return self._traces.get(trace_id)
    
    async def query(
        self,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[TraceContext]:
        results = list(self._traces.values())
        
        if agent_id:
            results = [t for t in results if any(e.agent_id == agent_id for e in t.events)]
        if session_id:
            results = [t for t in results if t.session_id == session_id]
        if start_time:
            results = [t for t in results if t.start_time >= start_time]
        if end_time:
            results = [t for t in results if t.start_time <= end_time]
        
        results.sort(key=lambda t: t.start_time, reverse=True)
        return results[:limit]


class SQLiteTraceStorage(TraceStorage):
    """SQLite trace storage for standard mode."""
    
    def __init__(self, db_path: str = "traces.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    root_agent_id TEXT,
                    session_id TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    metadata TEXT,
                    events TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON traces(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON traces(root_agent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_time ON traces(start_time)")
    
    async def save(self, trace: TraceContext) -> None:
        import sqlite3
        import json
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    trace.trace_id,
                    trace.root_agent_id,
                    trace.session_id,
                    trace.start_time.isoformat(),
                    trace.end_time.isoformat() if trace.end_time else None,
                    json.dumps(trace.metadata),
                    json.dumps([asdict(e) for e in trace.events], default=str),
                ),
            )
    
    async def load(self, trace_id: str) -> Optional[TraceContext]:
        import sqlite3
        import json
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM traces WHERE trace_id = ?", (trace_id,)).fetchone()
            if not row:
                return None
            
            event_dicts = json.loads(row["events"])
            events = []
            for e in event_dicts:
                e_copy = e.copy()
                if "event_type" in e_copy and isinstance(e_copy["event_type"], str):
                    e_copy["event_type"] = TraceEventType(e_copy["event_type"])
                events.append(TraceEvent(**e_copy))
            
            return TraceContext(
                trace_id=row["trace_id"],
                root_agent_id=row["root_agent_id"],
                session_id=row["session_id"],
                events=events,
                start_time=datetime.fromisoformat(row["start_time"]),
                end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
                metadata=json.loads(row["metadata"]),
            )
    
    async def query(
        self,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[TraceContext]:
        import sqlite3
        import json
        
        query = "SELECT * FROM traces WHERE 1=1"
        params = []
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if agent_id:
            query += " AND root_agent_id = ?"
            params.append(agent_id)
        if start_time:
            query += " AND start_time >= ?"
            params.append(start_time.isoformat())
        if end_time:
            query += " AND start_time <= ?"
            params.append(end_time.isoformat())
        
        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        
        results = []
        for row in rows:
            events = [TraceEvent(**json.loads(e)) for e in json.loads(row["events"])]
            results.append(TraceContext(
                trace_id=row["trace_id"],
                root_agent_id=row["root_agent_id"],
                session_id=row["session_id"],
                events=events,
                start_time=datetime.fromisoformat(row["start_time"]),
                end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
                metadata=json.loads(row["metadata"]),
            ))
        return results


class TraceExporter(ABC):
    """Abstract trace exporter."""
    
    @abstractmethod
    def export(self, trace: TraceContext) -> str:
        pass
    
    @property
    @abstractmethod
    def format_name(self) -> str:
        pass


class JSONExporter(TraceExporter):
    @property
    def format_name(self) -> str:
        return "json"
    
    def export(self, trace: TraceContext) -> str:
        data = {
            "trace_id": trace.trace_id,
            "root_agent_id": trace.root_agent_id,
            "session_id": trace.session_id,
            "start_time": trace.start_time.isoformat(),
            "end_time": trace.end_time.isoformat() if trace.end_time else None,
            "duration_ms": trace.duration_ms(),
            "metadata": trace.metadata,
            "events": [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type.value,
                    "timestamp": e.timestamp.isoformat(),
                    "agent_id": e.agent_id,
                    "parent_event_id": e.parent_event_id,
                    "data": e.data,
                    "duration_ms": e.duration_ms,
                    "metadata": e.metadata,
                }
                for e in trace.events
            ],
        }
        return json.dumps(data, indent=2)


class MermaidExporter(TraceExporter):
    @property
    def format_name(self) -> str:
        return "mermaid"
    
    def export(self, trace: TraceContext) -> str:
        lines = ["```mermaid", "graph TD"]
        
        # Add nodes
        for i, event in enumerate(trace.events):
            node_id = f"E{i}"
            label = f"{event.event_type.value}\\n{event.agent_id or 'system'}"
            if event.duration_ms:
                label += f" ({event.duration_ms:.1f}ms)"
            lines.append(f'    {node_id}["{label}"]')
            
            if event.parent_event_id:
                # Find parent index
                for j, pe in enumerate(trace.events):
                    if pe.event_id == event.parent_event_id:
                        lines.append(f"    E{j} --> {node_id}")
                        break
            elif i > 0:
                lines.append(f"    E{i-1} --> {node_id}")
        
        lines.append("```")
        return "\n".join(lines)


class OpenTelemetryExporter(TraceExporter):
    @property
    def format_name(self) -> str:
        return "opentelemetry"
    
    def export(self, trace: TraceContext) -> str:
        # Simplified OTLP JSON format
        spans = []
        for i, event in enumerate(trace.events):
            span = {
                "traceId": trace.trace_id,
                "spanId": event.event_id,
                "parentSpanId": event.parent_event_id,
                "name": event.event_type.value,
                "startTimeUnixNano": int(event.timestamp.timestamp() * 1e9),
                "endTimeUnixNano": int((event.timestamp.timestamp() * 1e9) + (event.duration_ms or 0) * 1e6),
                "attributes": {
                    "agent.id": event.agent_id or "unknown",
                    **event.data,
                    **event.metadata,
                },
            }
            spans.append(span)
        
        return json.dumps({"spans": spans}, indent=2)


class JaegerExporter(TraceExporter):
    @property
    def format_name(self) -> str:
        return "jaeger"
    
    def export(self, trace: TraceContext) -> str:
        # Simplified Jaeger format
        spans = []
        for event in trace.events:
            span = {
                "traceID": trace.trace_id,
                "spanID": event.event_id,
                "operationName": event.event_type.value,
                "references": [{"refType": "CHILD_OF", "traceID": trace.trace_id, "spanID": event.parent_event_id}] if event.parent_event_id else [],
                "startTime": int(event.timestamp.timestamp() * 1e6),
                "duration": int((event.duration_ms or 0) * 1000),
                "tags": [
                    {"key": "agent.id", "value": event.agent_id or "unknown", "type": "string"},
                    *[{"key": k, "value": str(v), "type": "string"} for k, v in event.data.items()],
                    *[{"key": k, "value": str(v), "type": "string"} for k, v in event.metadata.items()],
                ],
                "logs": [],
            }
            spans.append(span)
        
        return json.dumps({"spans": spans}, indent=2)


class ReasoningTrace:
    """
    Main reasoning trace manager.
    Captures execution traces and exports in multiple formats.
    Configuration driven by RigorMode.
    """
    
    def __init__(self, config: Optional[ReasoningTraceConfig] = None):
        self._config = config or get_rigor_mode().get_reasoning_trace_config()
        self._storage = self._create_storage()
        self._exporters = self._create_exporters()
        self._sampling_rate = self._config.sampling_rate
        self._lock = asyncio.Lock()
        self._active_traces: Dict[str, TraceContext] = {}
        
        if not self._config.enabled:
            logger.info("ReasoningTrace disabled by configuration")
    
    def _create_storage(self) -> TraceStorage:
        storage_type = self._config.storage
        if storage_type == "memory":
            return MemoryTraceStorage()
        elif storage_type == "sqlite":
            return SQLiteTraceStorage()
        elif storage_type == "postgresql":
            # Would implement PostgreSQL storage
            return MemoryTraceStorage()  # Fallback
        return MemoryTraceStorage()
    
    def _create_exporters(self) -> Dict[str, TraceExporter]:
        exporters = {}
        for fmt in self._config.export_formats:
            if fmt == "json":
                exporters[fmt] = JSONExporter()
            elif fmt == "mermaid":
                exporters[fmt] = MermaidExporter()
            elif fmt == "opentelemetry":
                exporters[fmt] = OpenTelemetryExporter()
            elif fmt == "jaeger":
                exporters[fmt] = JaegerExporter()
        return exporters
    
    def start_trace(
        self,
        root_agent_id: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceContext:
        """Start a new reasoning trace."""
        if not self._config.enabled:
            return TraceContext(
                trace_id="disabled",
                root_agent_id=root_agent_id,
                session_id=session_id or str(uuid.uuid4()),
            )
        
        # Sampling
        import random
        if random.random() > self._sampling_rate:
            return TraceContext(
                trace_id="sampled_out",
                root_agent_id=root_agent_id,
                session_id=session_id or str(uuid.uuid4()),
            )
        
        trace_id = str(uuid.uuid4())
        trace = TraceContext(
            trace_id=trace_id,
            root_agent_id=root_agent_id,
            session_id=session_id or str(uuid.uuid4()),
            metadata=metadata or {},
        )
        
        _current_trace.set(trace)
        self._active_traces[trace_id] = trace
        
        logger.debug(f"Started trace: {trace_id} (agent={root_agent_id})")
        return trace
    
    def end_trace(self, trace: TraceContext) -> None:
        """End a reasoning trace and persist it."""
        if trace.trace_id in ("disabled", "sampled_out"):
            return
        
        trace.end_time = datetime.now(UTC)
        _current_trace.set(None)
        self._active_traces.pop(trace.trace_id, None)
        
        # Persist asynchronously
        asyncio.create_task(self._storage.save(trace))
        
        logger.debug(f"Ended trace: {trace.trace_id} (duration={trace.duration_ms():.1f}ms)")
    
    def get_current_trace(self) -> Optional[TraceContext]:
        """Get the currently active trace from context."""
        return _current_trace.get()
    
    def add_event(
        self,
        event_type: TraceEventType,
        agent_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        parent_event_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[TraceEvent]:
        """Add an event to the current trace."""
        trace = self.get_current_trace()
        if not trace or trace.trace_id in ("disabled", "sampled_out"):
            return None
        
        # Check depth limit
        if trace._depth >= self._config.max_depth:
            logger.warning(f"Trace depth limit reached: {self._config.max_depth}")
            return None
        
        event = TraceEvent(
            event_id=str(uuid.uuid4())[:12],
            event_type=event_type,
            timestamp=datetime.now(UTC),
            agent_id=agent_id or trace.root_agent_id,
            parent_event_id=parent_event_id,
            data=data or {},
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
        
        trace.add_event(event)
        return event
    
    async def export(self, trace_id: str, format: str) -> Optional[str]:
        """Export a trace in the specified format."""
        trace = await self._storage.load(trace_id)
        if not trace:
            return None
        
        exporter = self._exporters.get(format)
        if not exporter:
            raise ValueError(f"Unsupported export format: {format}")
        
        return exporter.export(trace)
    
    async def export_to_file(self, trace_id: str, format: str, path: str) -> bool:
        """Export trace to file with optional compression."""
        content = await self.export(trace_id, format)
        if not content:
            return False
        
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        if self._config.compression and path.endswith(".gz"):
            with gzip.open(path_obj, "wt", encoding="utf-8") as f:
                f.write(content)
        else:
            path_obj.write_text(content, encoding="utf-8")
        
        return True
    
    async def query_traces(
        self,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[TraceContext]:
        """Query stored traces."""
        return await self._storage.query(agent_id, session_id, start_time, end_time, limit)
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "enabled": self._config.enabled,
            "storage": self._config.storage,
            "max_depth": self._config.max_depth,
            "sampling_rate": self._sampling_rate,
            "export_formats": list(self._exporters.keys()),
            "active_traces": len(self._active_traces),
            "compression": self._config.compression,
            "pii_redaction": self._config.pii_redaction,
        }


# Global trace instance
_trace: Optional[ReasoningTrace] = None


def get_reasoning_trace(config: Optional[ReasoningTraceConfig] = None) -> ReasoningTrace:
    """Get or create the global ReasoningTrace instance."""
    global _trace
    if _trace is None:
        _trace = ReasoningTrace(config)
    return _trace


def set_reasoning_trace(trace: ReasoningTrace) -> None:
    """Set the global ReasoningTrace instance (for testing)."""
    global _trace
    _trace = trace


# Convenience decorators
def traced(agent_id: str, event_type: TraceEventType = TraceEventType.AGENT_START):
    """Decorator to automatically trace function execution."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            trace = get_reasoning_trace()
            ctx = trace.start_trace(agent_id)
            start = datetime.now(UTC)
            
            event_id = trace.add_event(event_type, agent_id=agent_id, data={"function": func.__name__})
            
            try:
                result = await func(*args, **kwargs)
                duration = (datetime.now(UTC) - start).total_seconds() * 1000
                trace.add_event(
                    TraceEventType.AGENT_END,
                    agent_id=agent_id,
                    data={"function": func.__name__, "success": True},
                    parent_event_id=event_id.event_id if event_id else None,
                    duration_ms=duration,
                )
                trace.end_trace(ctx)
                return result
            except Exception as e:
                duration = (datetime.now(UTC) - start).total_seconds() * 1000
                trace.add_event(
                    TraceEventType.ERROR,
                    agent_id=agent_id,
                    data={"function": func.__name__, "error": str(e)},
                    parent_event_id=event_id.event_id if event_id else None,
                    duration_ms=duration,
                )
                trace.end_trace(ctx)
                raise
        
        def sync_wrapper(*args, **kwargs):
            trace = get_reasoning_trace()
            ctx = trace.start_trace(agent_id)
            start = datetime.now(UTC)
            
            event_id = trace.add_event(event_type, agent_id=agent_id, data={"function": func.__name__})
            
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now(UTC) - start).total_seconds() * 1000
                trace.add_event(
                    TraceEventType.AGENT_END,
                    agent_id=agent_id,
                    data={"function": func.__name__, "success": True},
                    parent_event_id=event_id.event_id if event_id else None,
                    duration_ms=duration,
                )
                trace.end_trace(ctx)
                return result
            except Exception as e:
                duration = (datetime.now(UTC) - start).total_seconds() * 1000
                trace.add_event(
                    TraceEventType.ERROR,
                    agent_id=agent_id,
                    data={"function": func.__name__, "error": str(e)},
                    parent_event_id=event_id.event_id if event_id else None,
                    duration_ms=duration,
                )
                trace.end_trace(ctx)
                raise
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator