"""
Check Fraud Detection System

A LangGraph-based agentic solution for detecting check fraud using
multiple specialized agents and a voting mechanism.

Agents:
- CheckAnalysisAgent: Physical check analysis (watermark, signature, MICR)
- TransactionHistoryAgent: Historical transaction pattern analysis
- PolicyAnalysisAgent: Rule-based policy compliance checking
- GenericFraudAgent: LLM-based holistic fraud assessment
- VotingAggregator: Consensus-based final decision

Usage:
    from check_fraud import run_fraud_detection, run_fraud_detection_without_llm
    from check_fraud.database import initialize_sample_data
    
    # Load sample data
    data = initialize_sample_data()
    check = data["all_checks"][0]
    client = data["clients"].get(check.client_id)
    
    # Run analysis (without LLM)
    result = run_fraud_detection_without_llm(check, client)
    print(f"Verdict: {result.final_verdict}")
    
    # Run analysis (with LLM - requires API key)
    result = run_fraud_detection(check, client, llm_provider="groq")
"""

from graph.workflow import (
    run_fraud_detection,
    run_fraud_detection_without_llm,
    create_fraud_detection_workflow,
)
from database.sample_data import initialize_sample_data
from database.models import (
    Check,
    Client,
    FraudVerdict,
    RiskLevel,
    FraudAnalysisResult,
)

__version__ = "1.0.0"
__all__ = [
    "run_fraud_detection",
    "run_fraud_detection_without_llm",
    "create_fraud_detection_workflow",
    "initialize_sample_data",
    "Check",
    "Client",
    "FraudVerdict",
    "RiskLevel",
    "FraudAnalysisResult",
]
