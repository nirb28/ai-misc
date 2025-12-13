"""LangGraph workflow for check fraud detection."""

from typing import Dict, Any, Optional
from datetime import datetime
import os

from langgraph.graph import StateGraph, END

from database.models import Check, Client, FraudAnalysisResult
from database.transaction_db import TransactionDatabase
from database.policy_db import PolicyDatabase
from agents.check_analysis_agent import CheckAnalysisAgent
from agents.transaction_history_agent import TransactionHistoryAgent
from agents.policy_agent import PolicyAnalysisAgent
from agents.generic_fraud_agent import GenericFraudAgent
from agents.voting_aggregator import VotingAggregator
from graph.state import FraudDetectionState, create_initial_state


def create_fraud_detection_workflow(
    llm_provider: str = "groq",
    llm_model: Optional[str] = None,
    agent_weights: Optional[Dict[str, float]] = None,
) -> StateGraph:
    """
    Create the LangGraph workflow for fraud detection.
    
    The workflow runs multiple specialized agents in parallel where possible,
    then aggregates their verdicts through a voting mechanism.
    
    Args:
        llm_provider: LLM provider for generic fraud agent ("groq" or "openai")
        llm_model: Specific model to use (optional)
        agent_weights: Custom weights for voting aggregation
    
    Returns:
        Compiled StateGraph workflow
    """
    transaction_db = TransactionDatabase()
    policy_db = PolicyDatabase()
    
    check_agent = CheckAnalysisAgent()
    transaction_agent = TransactionHistoryAgent(transaction_db)
    policy_agent = PolicyAnalysisAgent(policy_db, transaction_db)
    generic_agent = GenericFraudAgent(llm_provider, llm_model)
    voting_aggregator = VotingAggregator(agent_weights)
    
    def check_analysis_node(state: FraudDetectionState) -> Dict[str, Any]:
        """Node for physical check analysis."""
        try:
            return check_agent.analyze(state)
        except Exception as e:
            return {
                "processing_errors": [f"Check analysis error: {str(e)}"],
                "current_step": "check_analysis_error",
            }
    
    def transaction_analysis_node(state: FraudDetectionState) -> Dict[str, Any]:
        """Node for transaction history analysis."""
        try:
            return transaction_agent.analyze(state)
        except Exception as e:
            return {
                "processing_errors": [f"Transaction analysis error: {str(e)}"],
                "current_step": "transaction_analysis_error",
            }
    
    def policy_analysis_node(state: FraudDetectionState) -> Dict[str, Any]:
        """Node for policy-based analysis."""
        try:
            return policy_agent.analyze(state)
        except Exception as e:
            return {
                "processing_errors": [f"Policy analysis error: {str(e)}"],
                "current_step": "policy_analysis_error",
            }
    
    def generic_analysis_node(state: FraudDetectionState) -> Dict[str, Any]:
        """Node for LLM-based generic fraud analysis."""
        try:
            return generic_agent.analyze(state)
        except Exception as e:
            return {
                "processing_errors": [f"Generic analysis error: {str(e)}"],
                "current_step": "generic_analysis_error",
            }
    
    def voting_node(state: FraudDetectionState) -> Dict[str, Any]:
        """Node for aggregating verdicts and making final decision."""
        try:
            return voting_aggregator.aggregate(state)
        except Exception as e:
            return {
                "processing_errors": [f"Voting aggregation error: {str(e)}"],
                "current_step": "voting_error",
            }
    
    workflow = StateGraph(FraudDetectionState)
    
    workflow.add_node("check_analysis", check_analysis_node)
    workflow.add_node("transaction_analysis", transaction_analysis_node)
    workflow.add_node("policy_analysis", policy_analysis_node)
    workflow.add_node("generic_analysis", generic_analysis_node)
    workflow.add_node("voting", voting_node)
    
    workflow.set_entry_point("check_analysis")
    
    workflow.add_edge("check_analysis", "transaction_analysis")
    workflow.add_edge("transaction_analysis", "policy_analysis")
    workflow.add_edge("policy_analysis", "generic_analysis")
    workflow.add_edge("generic_analysis", "voting")
    workflow.add_edge("voting", END)
    
    return workflow.compile()


def run_fraud_detection(
    check: Check,
    client: Optional[Client] = None,
    llm_provider: str = "groq",
    llm_model: Optional[str] = None,
    agent_weights: Optional[Dict[str, float]] = None,
) -> FraudAnalysisResult:
    """
    Run the complete fraud detection workflow on a check.
    
    Args:
        check: Check to analyze
        client: Optional client information (will be looked up if not provided)
        llm_provider: LLM provider for generic fraud agent
        llm_model: Specific model to use
        agent_weights: Custom weights for voting
    
    Returns:
        FraudAnalysisResult with complete analysis
    """
    workflow = create_fraud_detection_workflow(llm_provider, llm_model, agent_weights)
    
    initial_state = create_initial_state(check, client)
    
    final_state = workflow.invoke(initial_state)
    
    aggregator = VotingAggregator(agent_weights)
    result = aggregator.create_analysis_result(final_state)
    
    return result


def _merge_state(base_state: dict, new_result: dict) -> dict:
    """Merge new result into base state, properly accumulating lists."""
    merged = {**base_state}
    
    for key, value in new_result.items():
        if key in merged and isinstance(merged[key], list) and isinstance(value, list):
            existing_items = set()
            for item in merged[key]:
                if hasattr(item, 'agent_name'):
                    existing_items.add(item.agent_name)
                else:
                    existing_items.add(str(item))
            
            for item in value:
                if hasattr(item, 'agent_name'):
                    if item.agent_name not in existing_items:
                        merged[key].append(item)
                        existing_items.add(item.agent_name)
                elif str(item) not in existing_items:
                    merged[key].append(item)
                    existing_items.add(str(item))
        else:
            merged[key] = value
    
    return merged


def run_fraud_detection_without_llm(
    check: Check,
    client: Optional[Client] = None,
    agent_weights: Optional[Dict[str, float]] = None,
) -> FraudAnalysisResult:
    """
    Run fraud detection without the LLM-based generic agent.
    
    Useful for testing or when LLM is not available.
    
    Args:
        check: Check to analyze
        client: Optional client information
        agent_weights: Custom weights for voting
    
    Returns:
        FraudAnalysisResult with analysis from non-LLM agents
    """
    transaction_db = TransactionDatabase()
    policy_db = PolicyDatabase()
    
    check_agent = CheckAnalysisAgent()
    transaction_agent = TransactionHistoryAgent(transaction_db)
    policy_agent = PolicyAnalysisAgent(policy_db, transaction_db)
    voting_aggregator = VotingAggregator(agent_weights)
    
    state = create_initial_state(check, client)
    
    check_result = check_agent.analyze(state)
    state = _merge_state(state, check_result)
    
    transaction_result = transaction_agent.analyze(state)
    state = _merge_state(state, transaction_result)
    
    policy_result = policy_agent.analyze(state)
    state = _merge_state(state, policy_result)
    
    voting_result = voting_aggregator.aggregate(state)
    state = _merge_state(state, voting_result)
    
    return voting_aggregator.create_analysis_result(state)


async def run_fraud_detection_async(
    check: Check,
    client: Optional[Client] = None,
    llm_provider: str = "groq",
    llm_model: Optional[str] = None,
    agent_weights: Optional[Dict[str, float]] = None,
) -> FraudAnalysisResult:
    """
    Async version of fraud detection workflow.
    
    Args:
        check: Check to analyze
        client: Optional client information
        llm_provider: LLM provider for generic fraud agent
        llm_model: Specific model to use
        agent_weights: Custom weights for voting
    
    Returns:
        FraudAnalysisResult with complete analysis
    """
    workflow = create_fraud_detection_workflow(llm_provider, llm_model, agent_weights)
    
    initial_state = create_initial_state(check, client)
    
    final_state = await workflow.ainvoke(initial_state)
    
    aggregator = VotingAggregator(agent_weights)
    result = aggregator.create_analysis_result(final_state)
    
    return result
