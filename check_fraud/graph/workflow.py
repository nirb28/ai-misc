"""LangGraph workflow for check fraud detection."""

from typing import Dict, Any, Optional
from datetime import datetime
import os

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_groq import ChatGroq

from database.models import Check, Client, FraudAnalysisResult
from database.transaction_db import TransactionDatabase
from database.policy_db import PolicyDatabase
from agents.check_analysis_agent import CheckAnalysisAgent
from agents.transaction_history_agent import TransactionHistoryAgent
from agents.policy_agent import PolicyAnalysisAgent
from agents.generic_fraud_agent import GenericFraudAgent
from agents.voting_aggregator import VotingAggregator
from graph.state import FraudDetectionState, create_initial_state
from config import get_analysis_config, AnalysisConfig, LLMConfig


def create_llm_from_config(llm_config: LLMConfig):
    """Create an LLM instance from configuration."""
    provider = llm_config.provider
    
    if provider == "groq":
        model = llm_config.model or "llama-3.3-70b-versatile"
        api_key = llm_config.api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            return None
        return ChatGroq(
            model=model,
            temperature=llm_config.temperature,
            api_key=api_key,
        )
    elif provider == "openai":
        model = llm_config.model or "gpt-4o"
        api_key = llm_config.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return ChatOpenAI(
            model=model,
            temperature=llm_config.temperature,
            api_key=api_key,
        )
    elif provider == "azure":
        api_key = llm_config.api_key or os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = llm_config.azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment = llm_config.azure_deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        api_version = llm_config.azure_api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        
        if not all([api_key, endpoint, deployment]):
            return None
        
        azure_kwargs: Dict[str, Any] = {
            "azure_deployment": deployment,
            "azure_endpoint": endpoint,
            "api_key": api_key,
            "api_version": api_version,
        }
        # Some Azure deployments (e.g. gpt-5-nano) reject non-default temperatures.
        # Only send temperature when it's explicitly the default (1.0) to avoid 400s.
        if llm_config.temperature is not None and float(llm_config.temperature) == 1.0:
            azure_kwargs["temperature"] = float(llm_config.temperature)

        return AzureChatOpenAI(**azure_kwargs)
    
    return None


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
    use_simulation: bool = True,
) -> FraudAnalysisResult:
    """
    Run fraud detection without the LLM-based generic agent.
    
    Useful for testing or when LLM is not available.
    
    Args:
        check: Check to analyze
        client: Optional client information
        agent_weights: Custom weights for voting
        use_simulation: If True, use simulated analysis. If False, use real LLM for tools.
    
    Returns:
        FraudAnalysisResult with analysis from non-LLM agents
    """
    config = get_analysis_config()
    config.use_simulation = use_simulation
    
    # Create LLM for tools if not using simulation
    llm = None
    if not use_simulation:
        llm = create_llm_from_config(config.llm_config)
    
    transaction_db = TransactionDatabase()
    policy_db = PolicyDatabase()
    
    check_agent = CheckAnalysisAgent(config=config, llm=llm)
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


def run_fraud_detection_with_real_analysis(
    check: Check,
    client: Optional[Client] = None,
    llm_provider: str = "azure",
    llm_model: Optional[str] = None,
    agent_weights: Optional[Dict[str, float]] = None,
) -> FraudAnalysisResult:
    """
    Run fraud detection with real LLM-based analysis (no simulation).
    
    All agents use real LLM models for analysis.
    
    Args:
        check: Check to analyze
        client: Optional client information
        llm_provider: LLM provider ("azure", "groq", "openai")
        llm_model: Specific model to use
        agent_weights: Custom weights for voting
    
    Returns:
        FraudAnalysisResult with real LLM-based analysis
    """
    config = get_analysis_config()
    config.use_simulation = False
    config.llm_config.provider = llm_provider
    if llm_model:
        config.llm_config.model = llm_model
    
    llm = create_llm_from_config(config.llm_config)
    if not llm:
        raise ValueError(f"Could not create LLM for provider: {llm_provider}. Check API keys.")
    
    transaction_db = TransactionDatabase()
    policy_db = PolicyDatabase()
    
    check_agent = CheckAnalysisAgent(config=config, llm=llm)
    transaction_agent = TransactionHistoryAgent(transaction_db)
    policy_agent = PolicyAnalysisAgent(policy_db, transaction_db)
    generic_agent = GenericFraudAgent(llm_config=config.llm_config)
    voting_aggregator = VotingAggregator(agent_weights)
    
    state = create_initial_state(check, client)
    
    check_result = check_agent.analyze(state)
    state = _merge_state(state, check_result)
    
    transaction_result = transaction_agent.analyze(state)
    state = _merge_state(state, transaction_result)
    
    policy_result = policy_agent.analyze(state)
    state = _merge_state(state, policy_result)
    
    generic_result = generic_agent.analyze(state)
    state = _merge_state(state, generic_result)
    
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
