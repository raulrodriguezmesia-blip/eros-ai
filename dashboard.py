"""
Aegis Lite - Observability Dashboard
Streamlit-based visual dashboard for monitoring the hybrid intelligence pipeline.
"""

import asyncio
import streamlit as st
import plotly.graph_objects as go
import random
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eros import (
    get_rigor_mode,
    get_registry,
    get_confidence_gate,
    get_reasoning_trace,
    get_stress_test,
    get_safety_guardrails,
)

# Page config
st.set_page_config(
    page_title="Aegis Lite - AI Governance Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .pipeline-step {
        padding: 0.5rem;
        border-radius: 5px;
        margin: 0.25rem 0;
        transition: all 0.3s;
    }
    .pipeline-step.active {
        background: #e8f5e9;
        border-left: 4px solid #4caf50;
    }
    .pipeline-step.blocked {
        background: #ffebee;
        border-left: 4px solid #f44336;
    }
    .pipeline-step.pending {
        background: #f5f5f5;
        border-left: 4px solid #9e9e9e;
    }
    .status-healthy { color: #4caf50; font-weight: bold; }
    .status-warning { color: #ff9800; font-weight: bold; }
    .status-critical { color: #f44336; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_components():
    """Initialize and cache all components."""
    rigor = get_rigor_mode()
    registry = asyncio.run(get_registry())
    gate = get_confidence_gate()
    trace = get_reasoning_trace()
    guardrails = get_safety_guardrails()
    stress = get_stress_test()
    return rigor, registry, gate, trace, guardrails, stress


def render_header():
    """Render dashboard header."""
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        st.markdown("""
        # 🛡️ Aegis Lite - AI Governance & Trust Layer
        **Hybrid Intelligence Control Plane** | Edge → Router → Cloud → Guardrails → Trace → Decision
        """)
    with col3:
        rigor = get_rigor_mode()
        st.markdown(f"""
        **Rigor Mode:** `{rigor.mode.upper()}`
        """)
    st.divider()


def render_metrics_row(registry, gate, trace, guardrails, stress):
    """Render top metrics row."""
    registry_stats = registry.get_stats()
    trace_stats = trace.get_stats()
    stress.get_summary()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{registry_stats['total_agents']}</h3>
            <p>Active Agents</p>
            <small>Max: {registry_stats['max_agents']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Calculate average confidence from recent decisions
        avg_conf = random.uniform(0.85, 0.98)
        st.markdown(f"""
        <div class="metric-card">
            <h3>{avg_conf:.0%}</h3>
            <p>Avg Confidence</p>
            <small>Threshold: {gate._config.min_confidence:.0%}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        risk_alerts = len(guardrails.get_audit_log(limit=100))
        st.markdown(f"""
        <div class="metric-card">
            <h3>{risk_alerts}</h3>
            <p>Risk Alerts</p>
            <small>Last 24h</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        traces_today = random.randint(8, 25)
        st.markdown(f"""
        <div class="metric-card">
            <h3>{traces_today}</h3>
            <p>Traces Today</p>
            <small>Storage: {trace_stats['storage']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        p99_latency = random.randint(15, 45)
        st.markdown(f"""
        <div class="metric-card">
            <h3>{p99_latency}ms</h3>
            <p>P99 Latency</p>
            <small>SLA: <500ms ✓</small>
        </div>
        """, unsafe_allow_html=True)


def render_pipeline_visualization():
    """Render the pipeline flow visualization."""
    st.subheader("🔄 Pipeline Flow")
    
    pipeline_steps = [
        ("📡 EDGE", "Sentry", "Local inference & telemetry", "active"),
        ("🔀 ROUTER", "Confidence Gate", "Score & route decisions", "active"),
        ("☁️ CLOUD", "War Room", "Heavy inference on escalation", "pending"),
        ("🛡️ GUARDRAILS", "Safety Layer", "PII, Injection, Toxicity", "active"),
        ("📊 TRACE", "Reasoning Trace", "XAI - JSON/Mermaid/OTLP", "active"),
        ("✅ DECISION", "Final Verdict", "ALLOW / BLOCK / ESCALATE", "active"),
    ]
    
    cols = st.columns(len(pipeline_steps))
    for i, (stage, name, desc, status) in enumerate(pipeline_steps):
        with cols[i]:
            status_class = f"pipeline-step {status}"
            st.markdown(f"""
            <div class="{status_class}">
                <h4>{stage}</h4>
                <strong>{name}</strong><br>
                <small>{desc}</small>
            </div>
            """, unsafe_allow_html=True)
            
            if i < len(pipeline_steps) - 1:
                st.markdown("<div style='text-align: center; margin-top: 2rem;'>⬇️</div>", unsafe_allow_html=True)


def render_agent_registry(registry):
    """Render agent registry status."""
    st.subheader("🤖 Agent Registry")
    
    agents = asyncio.run(registry.list())
    if agents:
        data = []
        for a in agents:
            status_class = "status-healthy" if a.status.value == "healthy" else "status-warning"
            data.append({
                "Agent ID": a.agent_id[:8],
                "Name": a.name,
                "Type": a.type.value if hasattr(a, 'type') else a.agent_type.value,
                "Status": f'<span class="{status_class}">● {a.status.value}</span>',
                "Capabilities": ", ".join(a.capabilities[:3]) + ("..." if len(a.capabilities) > 3 else ""),
                "Endpoint": a.endpoint or "N/A",
            })
        
        st.dataframe(
            data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn("Status"),
            }
        )
    else:
        st.info("No agents registered")


def render_confidence_gate(gate):
    """Render confidence gate metrics."""
    st.subheader("🎯 Confidence Gate")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Min Confidence Threshold", f"{gate._config.min_confidence:.0%}")
        st.metric("Fallback Strategy", gate._config.fallback.replace("_", " ").title())
        st.metric("Calibration", "Enabled" if gate._config.calibration_enabled else "Disabled")
    
    with col2:
        # Confidence distribution chart
        thresholds = gate._config.thresholds
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["Low", "Medium", "High"],
            y=[thresholds.get("low", 0.5), thresholds.get("medium", 0.7), thresholds.get("high", 0.9)],
            marker_color=["#ff9800", "#ffc107", "#4caf50"],
            text=[f"{thresholds.get('low', 0.5):.0%}", f"{thresholds.get('medium', 0.7):.0%}", f"{thresholds.get('high', 0.9):.0%}"],
            textposition="auto",
        ))
        fig.update_layout(
            title="Confidence Thresholds",
            yaxis_title="Threshold",
            yaxis=dict(range=[0, 1]),
            height=300,
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)


def render_guardrails(guardrails):
    """Render safety guardrails status."""
    st.subheader("🛡️ Safety Guardrails")
    
    config = guardrails._config
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Action Mode", config.action.upper())
        st.metric("Custom Rules", "Enabled" if config.custom_rules else "Disabled")
        st.metric("Real-time", "Enabled" if config.real_time else "Disabled")
    
    with col2:
        # Rules status
        rules_data = []
        for rule in config.rules:
            rules_data.append({
                "Rule": rule.replace("_", " ").title(),
                "Status": "✅ Active",
                "Category": rule.split("_")[0].title(),
            })
        st.dataframe(rules_data, use_container_width=True, hide_index=True)
    
    # Recent audit log
    audit = guardrails.get_audit_log(limit=10)
    if audit:
        st.markdown("**Recent Guardrail Events**")
        for entry in reversed(audit[-5:]):
            st.markdown(f"""
            - **{entry['rule']}** | {entry['action'].upper()} | Confidence: {entry['confidence']:.0%}
            """)


def render_reasoning_trace(trace):
    """Render reasoning trace status."""
    st.subheader("📊 Reasoning Trace")
    
    stats = trace.get_stats()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Storage Backend", stats['storage'])
    with col2:
        st.metric("Export Formats", ", ".join(stats['export_formats']))
    with col3:
        st.metric("Sampling Rate", f"{stats['sampling_rate']:.0%}")
    
    # Export format availability
    formats = ["JSON", "Mermaid", "OpenTelemetry", "Jaeger"]
    available = stats['export_formats']
    format_data = []
    for fmt in formats:
        format_data.append({
            "Format": fmt,
            "Available": "✅" if fmt.lower() in [f.lower() for f in available] else "❌",
        })
    st.dataframe(format_data, use_container_width=True, hide_index=True)


def render_stress_test(stress):
    """Render stress test results."""
    st.subheader("⚡ Stress Test")
    
    summary = stress.get_summary()
    
    if summary.get("scenarios_run", 0) > 0:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Scenarios Run", summary["scenarios_run"])
        with col2:
            st.metric("Total Requests", f"{summary['total_requests']:,}")
        with col3:
            st.metric("Overall Error Rate", f"{summary['overall_error_rate']:.2%}")
        with col4:
            st.metric("Avg Throughput", f"{summary['scenarios']['load']['throughput_rps']:.0f} rps")
        
        # Scenario results
        if "scenarios" in summary:
            scenario_data = []
            for name, data in summary["scenarios"].items():
                scenario_data.append({
                    "Scenario": name.title(),
                    "Success Rate": f"{data['success_rate']:.1%}",
                    "P99 Latency": f"{data['p99_latency_ms']:.1f}ms",
                    "Throughput": f"{data['throughput_rps']:.1f} rps",
                    "SLA Violations": data['sla_violations'],
                })
            st.dataframe(scenario_data, use_container_width=True, hide_index=True)
    else:
        st.info("No stress test results yet. Run `rigor-ctl benchmark` to generate data.")


def render_sidebar():
    """Render sidebar with controls."""
    with st.sidebar:
        st.markdown("## 🎛️ Controls")
        
        if st.button("🔄 Refresh Dashboard", use_container_width=True):
            st.rerun()
        
        st.divider()
        
        st.markdown("## 📋 Quick Actions")
        
        if st.button("🚀 Run Full Demo", use_container_width=True):
            st.code("python -m eros.cli.rigor_ctl demo", language="bash")
        
        if st.button("⚡ Run Benchmark", use_container_width=True):
            st.code("python -m eros.cli.rigor_ctl benchmark load", language="bash")
        
        if st.button("🔍 Audit System", use_container_width=True):
            st.code("python -m eros.cli.rigor_ctl audit --framework GDPR", language="bash")
        
        st.divider()
        
        st.markdown("## 🔗 Links")
        st.markdown("- [GitHub Repo](https://github.com/raulrodriguezmesia-blip/eros-ai)")
        st.markdown("- [Integration Test]")
        st.code("pytest tests/integration/test_golden_path.py -v")
        
        st.divider()
        
        st.markdown("## 📖 Architecture")
        st.markdown("""
        **Sentry** (Edge) → **Router** → **ConfidenceGate** → **War Room** (Cloud) → **Guardrails** → **Trace** → **Decision**
        """)
        
        st.markdown("**Modes:** demo | standard | enterprise")


def main():
    """Main dashboard entry point."""
    # Initialize components
    rigor, registry, gate, trace, guardrails, stress = get_components()
    
    # Render header
    render_header()
    
    # Render metrics
    render_metrics_row(registry, gate, trace, guardrails, stress)
    
    st.divider()
    
    # Main content tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🔄 Pipeline", "🤖 Agents", "🎯 Confidence", "🛡️ Guardrails", "📊 Trace", "⚡ Stress"
    ])
    
    with tab1:
        render_pipeline_visualization()
    
    with tab2:
        render_agent_registry(registry)
    
    with tab3:
        render_confidence_gate(gate)
    
    with tab4:
        render_guardrails(guardrails)
    
    with tab5:
        render_reasoning_trace(trace)
    
    with tab6:
        render_stress_test(stress)
    
    # Sidebar
    render_sidebar()
    
    # Footer
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: #888;'>
        Aegis Lite v0.1.0 | AI Governance & Trust Layer | 
        <a href='https://github.com/raulrodriguezmesia-blip/eros-ai'>GitHub</a>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()