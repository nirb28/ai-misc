"""Streamlit UI for Check Fraud Detection System."""

import streamlit as st
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import FraudVerdict, RiskLevel, Check
from database.sample_data import initialize_sample_data
from graph.workflow import run_fraud_detection, run_fraud_detection_without_llm


st.set_page_config(
    page_title="Check Fraud Detection",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .fraud-verdict {
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        font-size: 24px;
        font-weight: bold;
        margin: 20px 0;
    }
    .verdict-fraud {
        background-color: #ffcccc;
        border: 2px solid #ff0000;
        color: #cc0000;
    }
    .verdict-not-fraud {
        background-color: #ccffcc;
        border: 2px solid #00cc00;
        color: #006600;
    }
    .verdict-review {
        background-color: #ffffcc;
        border: 2px solid #cccc00;
        color: #666600;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 8px;
        margin: 5px 0;
    }
    .agent-card {
        border: 1px solid #ddd;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_sample_data():
    """Load and cache sample data."""
    return initialize_sample_data()


def get_verdict_style(verdict: FraudVerdict) -> str:
    """Get CSS class for verdict."""
    if verdict == FraudVerdict.FRAUD:
        return "verdict-fraud"
    elif verdict == FraudVerdict.NOT_FRAUD:
        return "verdict-not-fraud"
    else:
        return "verdict-review"


def get_risk_color(risk_level: RiskLevel) -> str:
    """Get color for risk level."""
    colors = {
        RiskLevel.LOW: "green",
        RiskLevel.MEDIUM: "orange",
        RiskLevel.HIGH: "red",
        RiskLevel.CRITICAL: "darkred",
    }
    return colors.get(risk_level, "gray")


def display_check_details(check: Check, client=None):
    """Display check details in a formatted way."""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 Check Information")
        check_dict = check.model_dump() if hasattr(check, 'model_dump') else dict(check)
        
        st.write(f"**Check ID:** {check_dict.get('check_id', 'N/A')}")
        st.write(f"**Check Number:** {check_dict.get('check_number', 'N/A')}")
        st.write(f"**Date:** {check_dict.get('date', 'N/A')}")
        st.write(f"**Amount:** ${check_dict.get('amount', 0):,.2f}")
        st.write(f"**Amount Written:** {check_dict.get('amount_written', 'N/A')}")
        st.write(f"**Payee:** {check_dict.get('payee', 'N/A')}")
        st.write(f"**Memo:** {check_dict.get('memo', 'N/A')}")
        
        metadata = check_dict.get('metadata', {})
        if metadata.get('flags'):
            st.warning(f"⚠️ Pre-existing flags: {', '.join(metadata['flags'])}")
    
    with col2:
        st.subheader("🏦 Bank & Account")
        st.write(f"**Bank:** {check_dict.get('bank_name', 'N/A')}")
        st.write(f"**Routing:** {check_dict.get('routing_number', 'N/A')}")
        account = check_dict.get('account_number', '')
        st.write(f"**Account:** {'*' * (len(account)-4) + account[-4:] if len(account) > 4 else account}")
        
        st.write(f"**Has Watermark:** {'✅' if check_dict.get('has_watermark') else '❌'}")
        st.write(f"**Signature Present:** {'✅' if check_dict.get('signature_present') else '❌'}")
        
        if metadata.get('source'):
            st.write(f"**Deposit Source:** {metadata['source']}")
        if metadata.get('device'):
            st.write(f"**Device:** {metadata['device']}")
    
    if client:
        st.subheader("👤 Client Information")
        client_dict = client.model_dump() if hasattr(client, 'model_dump') else dict(client)
        
        col3, col4 = st.columns(2)
        with col3:
            st.write(f"**Name:** {client_dict.get('name', 'N/A')}")
            st.write(f"**Client ID:** {client_dict.get('client_id', 'N/A')}")
            st.write(f"**Account Opened:** {client_dict.get('account_opened_date', 'N/A')}")
        with col4:
            st.write(f"**Avg Monthly Transactions:** {client_dict.get('average_monthly_transactions', 0):.1f}")
            st.write(f"**Avg Check Amount:** ${client_dict.get('average_check_amount', 0):,.2f}")
            st.write(f"**Risk Score:** {client_dict.get('risk_score', 0):.2f}")


def display_analysis_result(result):
    """Display the fraud analysis result."""
    verdict_class = get_verdict_style(result.final_verdict)
    verdict_emoji = {
        FraudVerdict.FRAUD: "🚨",
        FraudVerdict.NOT_FRAUD: "✅",
        FraudVerdict.REVIEW: "⚠️",
    }
    
    st.markdown(f"""
    <div class="fraud-verdict {verdict_class}">
        {verdict_emoji.get(result.final_verdict, '❓')} 
        VERDICT: {result.final_verdict.value.upper()}
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Confidence", f"{result.final_confidence:.1%}")
    with col2:
        risk_color = get_risk_color(result.final_risk_level)
        st.metric("Risk Level", result.final_risk_level.value.upper())
    with col3:
        st.metric("Consensus", "Yes" if result.consensus_reached else "No")
    with col4:
        st.metric("Processing Time", f"{result.processing_time_seconds:.2f}s")
    
    st.subheader("🗳️ Voting Summary")
    
    if result.voting_summary and result.voting_summary.get("agent_votes"):
        cols = st.columns(len(result.voting_summary["agent_votes"]))
        
        for idx, (agent, vote) in enumerate(result.voting_summary["agent_votes"].items()):
            with cols[idx]:
                agent_name = agent.replace("_agent", "").replace("_", " ").title()
                verdict_color = {
                    "fraud": "🔴",
                    "not_fraud": "🟢",
                    "review": "🟡",
                }.get(vote["verdict"], "⚪")
                
                st.markdown(f"""
                <div class="agent-card">
                    <strong>{agent_name}</strong><br>
                    {verdict_color} {vote['verdict'].upper()}<br>
                    Confidence: {vote['confidence']:.1%}<br>
                    Risk: {vote['risk_level']}
                </div>
                """, unsafe_allow_html=True)
    
    with st.expander("📊 Agent Details", expanded=False):
        for verdict in result.agent_verdicts:
            st.markdown(f"### {verdict.agent_name.replace('_', ' ').title()}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Verdict:** {verdict.verdict.value}")
            with col2:
                st.write(f"**Confidence:** {verdict.confidence:.1%}")
            with col3:
                st.write(f"**Risk:** {verdict.risk_level.value}")
            
            st.write("**Reasoning:**")
            st.text(verdict.reasoning[:500] + "..." if len(verdict.reasoning) > 500 else verdict.reasoning)
            
            if verdict.findings:
                st.write("**Findings:**")
                for finding in verdict.findings[:5]:
                    st.write(f"- {finding}")
            
            if verdict.recommendations:
                st.write("**Recommendations:**")
                for rec in verdict.recommendations[:3]:
                    st.write(f"- {rec}")
            
            st.divider()
    
    with st.expander("📋 All Findings & Recommendations", expanded=False):
        if result.notes:
            st.text(result.notes)


def main():
    """Main Streamlit application."""
    st.title("🔍 Check Fraud Detection System")
    st.markdown("*LangGraph-based Multi-Agent Fraud Analysis*")
    
    sample_data = load_sample_data()
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        use_llm = st.checkbox("Use LLM Analysis", value=False, 
                              help="Enable LLM-based generic fraud agent (requires API key)")
        
        if use_llm:
            llm_provider = st.selectbox("LLM Provider", ["groq", "openai"])
            
            if llm_provider == "groq":
                api_key = st.text_input("Groq API Key", type="password")
                if api_key:
                    import os
                    os.environ["GROQ_API_KEY"] = api_key
            else:
                api_key = st.text_input("OpenAI API Key", type="password")
                if api_key:
                    import os
                    os.environ["OPENAI_API_KEY"] = api_key
        else:
            llm_provider = None
        
        st.divider()
        
        st.header("📝 Select Check")
        
        check_category = st.radio(
            "Category",
            ["Legitimate Checks", "Suspicious Checks", "All Checks"]
        )
        
        if check_category == "Legitimate Checks":
            checks = sample_data["legitimate_checks"]
        elif check_category == "Suspicious Checks":
            checks = sample_data["fraudulent_checks"]
        else:
            checks = sample_data["all_checks"]
        
        check_options = {
            f"{c.check_id} - ${c.amount:,.2f} ({c.payee})": c 
            for c in checks
        }
        
        selected_check_name = st.selectbox(
            "Select Check",
            list(check_options.keys())
        )
        
        selected_check = check_options[selected_check_name]
        
        st.divider()
        st.markdown("### Quick Info")
        st.write(f"**Amount:** ${selected_check.amount:,.2f}")
        st.write(f"**Payee:** {selected_check.payee}")
        
        metadata = selected_check.metadata if hasattr(selected_check, 'metadata') else {}
        if metadata.get('flags'):
            st.warning(f"Flags: {len(metadata['flags'])}")
    
    tab1, tab2, tab3 = st.tabs(["🔍 Analysis", "📄 Check Details", "📚 Policies"])
    
    with tab1:
        client = sample_data["clients"].get(selected_check.client_id)
        
        st.subheader(f"Analyzing: {selected_check.check_id}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"💰 Amount: ${selected_check.amount:,.2f}")
        with col2:
            st.info(f"👤 Payee: {selected_check.payee}")
        with col3:
            st.info(f"🏦 Client: {client.name if client else 'Unknown'}")
        
        if st.button("🚀 Run Fraud Analysis", type="primary", use_container_width=True):
            with st.spinner("Running fraud detection workflow..."):
                try:
                    start_time = datetime.now()
                    
                    if use_llm and llm_provider:
                        result = run_fraud_detection(
                            selected_check,
                            client,
                            llm_provider=llm_provider,
                        )
                    else:
                        result = run_fraud_detection_without_llm(
                            selected_check,
                            client,
                        )
                    
                    st.session_state['analysis_result'] = result
                    st.success(f"Analysis completed in {(datetime.now() - start_time).total_seconds():.2f} seconds")
                    
                except Exception as e:
                    st.error(f"Error during analysis: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
        
        if 'analysis_result' in st.session_state:
            display_analysis_result(st.session_state['analysis_result'])
    
    with tab2:
        client = sample_data["clients"].get(selected_check.client_id)
        display_check_details(selected_check, client)
    
    with tab3:
        st.subheader("📚 Fraud Detection Policies")
        
        from database.policy_db import PolicyDatabase
        policy_db = PolicyDatabase()
        
        summary = policy_db.get_policy_summary()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Policies", summary["total_policies"])
        with col2:
            st.write("**Categories:**", ", ".join(summary["categories"]))
        
        st.divider()
        
        for policy in policy_db.get_all_policies():
            severity_colors = {
                RiskLevel.LOW: "🟢",
                RiskLevel.MEDIUM: "🟡",
                RiskLevel.HIGH: "🟠",
                RiskLevel.CRITICAL: "🔴",
            }
            
            with st.expander(f"{severity_colors.get(policy.severity, '⚪')} {policy.name} ({policy.policy_id})"):
                st.write(f"**Description:** {policy.description}")
                st.write(f"**Category:** {policy.category}")
                st.write(f"**Severity:** {policy.severity.value}")
                st.write(f"**Action:** {policy.action}")
                st.json(policy.conditions)


if __name__ == "__main__":
    main()
