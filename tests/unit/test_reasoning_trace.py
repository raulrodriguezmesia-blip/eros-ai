"""
Unit tests for ReasoningTrace component.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from eros import (
    ReasoningTrace,
    TraceContext,
    TraceEvent,
    TraceEventType,
    TraceStorage,
    MemoryTraceStorage,
    SQLiteTraceStorage,
    TraceExporter,
    JSONExporter,
    MermaidExporter,
    OpenTelemetryExporter,
    JaegerExporter,
    get_reasoning_trace,
    set_reasoning_trace,
    traced,
)


class TestMemoryTraceStorage:
    """Test MemoryTraceStorage."""
    
    @pytest.fixture
    def storage(self):
        return MemoryTraceStorage(max_traces=5)
    
    @pytest.mark.asyncio
    async def test_save_and_load(self, storage):
        """Test saving and loading a trace."""
        trace = TraceContext(
            trace_id="test-123",
            root_agent_id="agent-1",
            session_id="session-1",
            start_time=datetime.now(UTC),
        )
        trace.add_event(TraceEvent(
            event_id="evt-1",
            event_type=TraceEventType.AGENT_START,
            timestamp=datetime.now(UTC),
            agent_id="agent-1",
        ))
        
        await storage.save(trace)
        loaded = await storage.load("test-123")
        
        assert loaded is not None
        assert loaded.trace_id == "test-123"
        assert len(loaded.events) == 1
    
    @pytest.mark.asyncio
    async def test_load_nonexistent(self, storage):
        """Test loading non-existent trace."""
        result = await storage.load("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_max_traces_limit(self, storage):
        """Test max traces limit removes oldest."""
        for i in range(10):
            trace = TraceContext(
                trace_id=f"trace-{i}",
                root_agent_id="agent-1",
                session_id=f"session-{i}",
                start_time=datetime.now(UTC),
            )
            await storage.save(trace)
        
        # Should only keep max_traces (5)
        all_traces = await storage.query(limit=100)
        assert len(all_traces) == 5
    
    @pytest.mark.asyncio
    async def test_query_by_agent(self, storage):
        """Test query filtering by agent_id."""
        trace1 = TraceContext(
            trace_id="t1", root_agent_id="agent-1", session_id="s1",
            start_time=datetime.now(UTC),
        )
        trace1.add_event(TraceEvent(
            event_id="e1", event_type=TraceEventType.AGENT_START,
            timestamp=datetime.now(UTC), agent_id="agent-1",
        ))
        
        trace2 = TraceContext(
            trace_id="t2", root_agent_id="agent-2", session_id="s2",
            start_time=datetime.now(UTC),
        )
        trace2.add_event(TraceEvent(
            event_id="e2", event_type=TraceEventType.AGENT_START,
            timestamp=datetime.now(UTC), agent_id="agent-2",
        ))
        
        await storage.save(trace1)
        await storage.save(trace2)
        
        results = await storage.query(agent_id="agent-1")
        assert len(results) == 1
        assert results[0].trace_id == "t1"
    
    @pytest.mark.asyncio
    async def test_query_by_session(self, storage):
        """Test query filtering by session_id."""
        trace = TraceContext(
            trace_id="t1", root_agent_id="agent-1", session_id="session-x",
            start_time=datetime.now(UTC),
        )
        await storage.save(trace)
        
        results = await storage.query(session_id="session-x")
        assert len(results) == 1
        
        results = await storage.query(session_id="session-y")
        assert len(results) == 0


class TestSQLiteTraceStorage:
    """Test SQLiteTraceStorage."""
    
    @pytest.fixture
    def storage(self, tmp_path):
        db_path = tmp_path / "test_traces.db"
        return SQLiteTraceStorage(str(db_path))
    
    @pytest.mark.asyncio
    async def test_save_and_load(self, storage):
        """Test saving and loading a trace."""
        trace = TraceContext(
            trace_id="sql-test-1",
            root_agent_id="agent-1",
            session_id="session-1",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )
        trace.add_event(TraceEvent(
            event_id="evt-1",
            event_type=TraceEventType.AGENT_START,
            timestamp=datetime.now(UTC),
            agent_id="agent-1",
        ))
        
        await storage.save(trace)
        loaded = await storage.load("sql-test-1")
        
        assert loaded is not None
        assert loaded.trace_id == "sql-test-1"
        assert len(loaded.events) == 1
    
    @pytest.mark.asyncio
    async def test_query_by_time(self, storage):
        """Test query filtering by time range."""
        now = datetime.now(UTC)
        
        trace = TraceContext(
            trace_id="t1", root_agent_id="a1", session_id="s1",
            start_time=now,
        )
        await storage.save(trace)
        
        results = await storage.query(start_time=now)
        assert len(results) == 1
        
        results = await storage.query(end_time=now)
        assert len(results) == 1


class TestJSONExporter:
    """Test JSONExporter."""
    
    @pytest.fixture
    def exporter(self):
        return JSONExporter()
    
    def test_format_name(self, exporter):
        assert exporter.format_name == "json"
    
    def test_export(self, exporter):
        """Test JSON export."""
        trace = TraceContext(
            trace_id="export-1",
            root_agent_id="agent-1",
            session_id="session-1",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )
        trace.add_event(TraceEvent(
            event_id="evt-1",
            event_type=TraceEventType.AGENT_START,
            timestamp=datetime.now(UTC),
            agent_id="agent-1",
            data={"key": "value"},
        ))
        
        output = exporter.export(trace)
        parsed = json.loads(output)
        
        assert parsed["trace_id"] == "export-1"
        assert parsed["root_agent_id"] == "agent-1"
        assert len(parsed["events"]) == 1
        assert parsed["events"][0]["data"]["key"] == "value"


class TestMermaidExporter:
    """Test MermaidExporter."""
    
    @pytest.fixture
    def exporter(self):
        return MermaidExporter()
    
    def test_format_name(self, exporter):
        assert exporter.format_name == "mermaid"
    
    def test_export(self, exporter):
        """Test Mermaid export."""
        trace = TraceContext(
            trace_id="mermaid-1",
            root_agent_id="agent-1",
            session_id="session-1",
            start_time=datetime.now(UTC),
        )
        trace.add_event(TraceEvent(
            event_id="e1", event_type=TraceEventType.AGENT_START,
            timestamp=datetime.now(UTC), agent_id="agent-1",
        ))
        trace.add_event(TraceEvent(
            event_id="e2", event_type=TraceEventType.DECISION,
            timestamp=datetime.now(UTC), agent_id="agent-1",
            parent_event_id="e1",
        ))
        
        output = exporter.export(trace)
        
        assert "```mermaid" in output
        assert "graph TD" in output
        assert "e1" in output
        assert "e2" in output


class TestOpenTelemetryExporter:
    """Test OpenTelemetryExporter."""
    
    @pytest.fixture
    def exporter(self):
        return OpenTelemetryExporter()
    
    def test_format_name(self, exporter):
        assert exporter.format_name == "opentelemetry"
    
    def test_export(self, exporter):
        """Test OTLP export."""
        trace = TraceContext(
            trace_id="otlp-1",
            root_agent_id="agent-1",
            session_id="session-1",
            start_time=datetime.now(UTC),
        )
        trace.add_event(TraceEvent(
            event_id="evt-1",
            event_type=TraceEventType.AGENT_START,
            timestamp=datetime.now(UTC),
            agent_id="agent-1",
        ))
        
        output = exporter.export(trace)
        parsed = json.loads(output)
        
        assert "spans" in parsed
        assert len(parsed["spans"]) == 1
        assert parsed["spans"][0]["traceId"] == "otlp-1"


class TestJaegerExporter:
    """Test JaegerExporter."""
    
    @pytest.fixture
    def exporter(self):
        return JaegerExporter()
    
    def test_format_name(self, exporter):
        assert exporter.format_name == "jaeger"
    
    def test_export(self, exporter):
        """Test Jaeger export."""
        trace = TraceContext(
            trace_id="jaeger-1",
            root_agent_id="agent-1",
            session_id="session-1",
            start_time=datetime.now(UTC),
        )
        trace.add_event(TraceEvent(
            event_id="evt-1",
            event_type=TraceEventType.AGENT_START,
            timestamp=datetime.now(UTC),
            agent_id="agent-1",
        ))
        
        output = exporter.export(trace)
        parsed = json.loads(output)
        
        assert "spans" in parsed
        assert len(parsed["spans"]) == 1
        assert parsed["spans"][0]["traceID"] == "jaeger-1"


class TestReasoningTrace:
    """Test main ReasoningTrace class."""
    
    @pytest.fixture
    def trace(self):
        return ReasoningTrace()
    
    @pytest.mark.asyncio
    async def test_start_end_trace(self, trace):
        """Test starting and ending a trace."""
        ctx = trace.start_trace("agent-1", session_id="session-1")
        
        assert ctx.trace_id != "disabled"
        assert ctx.root_agent_id == "agent-1"
        assert ctx.session_id == "session-1"
        
        trace.end_trace(ctx)
        
        assert ctx.end_time is not None
        assert ctx.duration_ms() is not None
    
    @pytest.mark.asyncio
    async def test_disabled_trace(self, trace):
        """Test disabled trace returns minimal context."""
        trace._config.enabled = False
        
        ctx = trace.start_trace("agent-1")
        
        assert ctx.trace_id == "disabled"
        assert len(ctx.events) == 0
    
    @pytest.mark.asyncio
    async def test_sampling(self, trace):
        """Test sampling rate."""
        trace._config.sampling_rate = 0.0
        
        ctx = trace.start_trace("agent-1")
        
        assert ctx.trace_id == "sampled_out"
    
    @pytest.mark.asyncio
    async def test_add_event(self, trace):
        """Test adding events to current trace."""
        ctx = trace.start_trace("agent-1")
        
        event = trace.add_event(
            TraceEventType.DECISION,
            agent_id="agent-1",
            data={"decision": "allow"},
        )
        
        assert event is not None
        assert event.event_type == TraceEventType.DECISION
        assert event.data["decision"] == "allow"
        
        # Check it was added to context
        current = trace.get_current_trace()
        assert len(current.events) == 1
    
    @pytest.mark.asyncio
    async def test_depth_limit(self, trace):
        """Test max depth limit."""
        trace._config.max_depth = 2
        ctx = trace.start_trace("agent-1")
        
        trace.add_event(TraceEventType.AGENT_START, agent_id="agent-1")
        trace.add_event(TraceEventType.DECISION, agent_id="agent-1")
        event = trace.add_event(TraceEventType.ERROR, agent_id="agent-1")
        
        # Third event should be rejected
        assert event is None
    
    @pytest.mark.asyncio
    async def test_export(self, trace):
        """Test exporting a trace."""
        ctx = trace.start_trace("agent-1")
        trace.add_event(TraceEventType.DECISION, agent_id="agent-1")
        trace.end_trace(ctx)
        
        # Wait for async save
        await asyncio.sleep(0.1)
        
        json_out = await trace.export(ctx.trace_id, "json")
        assert json_out is not None
        assert "export-1" in json_out or ctx.trace_id in json_out
    
    @pytest.mark.asyncio
    async def test_export_to_file(self, trace, tmp_path):
        """Test exporting trace to file."""
        ctx = trace.start_trace("agent-1")
        trace.end_trace(ctx)
        await asyncio.sleep(0.1)
        
        output_path = tmp_path / "trace.json"
        result = await trace.export_to_file(ctx.trace_id, "json", str(output_path))
        
        assert result is True
        assert output_path.exists()
        
        content = output_path.read_text()
        assert "trace_id" in content
    
    @pytest.mark.asyncio
    async def test_query_traces(self, trace):
        """Test querying traces."""
        ctx = trace.start_trace("agent-1", session_id="query-test")
        trace.end_trace(ctx)
        await asyncio.sleep(0.1)
        
        results = await trace.query_traces(session_id="query-test")
        assert len(results) == 1
        assert results[0].session_id == "query-test"
    
    @pytest.mark.asyncio
    async def test_get_stats(self, trace):
        """Test getting trace statistics."""
        stats = trace.get_stats()
        
        assert "enabled" in stats
        assert "storage" in stats
        assert "export_formats" in stats


class TestTracedDecorator:
    """Test @traced decorator."""
    
    @pytest.mark.asyncio
    async def test_traced_async_function(self):
        """Test decorator on async function."""
        trace = ReasoningTrace()
        trace._config.enabled = True
        
        @traced("test-agent", TraceEventType.AGENT_START)
        async def async_func():
            return "result"
        
        result = await async_func()
        assert result == "result"
    
    def test_traced_sync_function(self):
        """Test decorator on sync function."""
        trace = ReasoningTrace()
        trace._config.enabled = True
        
        @traced("test-agent", TraceEventType.AGENT_START)
        def sync_func():
            return "result"
        
        result = sync_func()
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_traced_exception(self):
        """Test decorator handles exceptions."""
        trace = ReasoningTrace()
        trace._config.enabled = True
        
        @traced("test-agent", TraceEventType.AGENT_START)
        async def failing_func():
            raise ValueError("test error")
        
        with pytest.raises(ValueError, match="test error"):
            await failing_func()


class TestReasoningTraceGlobal:
    """Test global ReasoningTrace instance."""
    
    def test_get_reasoning_trace_singleton(self):
        """Test get_reasoning_trace returns singleton."""
        trace1 = get_reasoning_trace()
        trace2 = get_reasoning_trace()
        assert trace1 is trace2
    
    def test_set_reasoning_trace(self):
        """Test set_reasoning_trace replaces global."""
        original = get_reasoning_trace()
        new_trace = ReasoningTrace()
        set_reasoning_trace(new_trace)
        assert get_reasoning_trace() is new_trace
        set_reasoning_trace(original)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])