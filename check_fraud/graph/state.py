"""State definition for the fraud detection workflow."""

from typing import TypedDict, List, Optional, Dict, Any, Annotated
from datetime import datetime
import operator

from database.models import (
    Check,
    Client,
    AgentVerdict,
    FraudVerdict,
    RiskLevel,
    FraudAnalysisResult,
)


class CheckAnalysisResult(TypedDict):
    """Results from check physical analysis."""
    watermark_analysis: Dict[str, Any]
    signature_analysis: Dict[str, Any]
    micr_validation: Dict[str, Any]
    image_quality: Dict[str, Any]
    overall_physical_risk: float
    physical_flags: List[str]


class TransactionAnalysisResult(TypedDict):
    """Results from transaction history analysis."""
    client_found: bool
    transaction_statistics: Dict[str, Any]
    amount_anomaly_score: float
    payee_analysis: Dict[str, Any]
    velocity_analysis: Dict[str, Any]
    historical_flags: List[str]


class PolicyAnalysisResult(TypedDict):
    """Results from policy-based analysis."""
    policies_evaluated: int
    violations: List[Dict[str, Any]]
    violation_count: int
    highest_severity: str
    policy_flags: List[str]


def merge_verdicts(existing: List[AgentVerdict], new: List[AgentVerdict]) -> List[AgentVerdict]:
    """Merge agent verdicts, avoiding duplicates."""
    existing_agents = {v.agent_name for v in existing}
    merged = list(existing)
    for verdict in new:
        if verdict.agent_name not in existing_agents:
            merged.append(verdict)
            existing_agents.add(verdict.agent_name)
    return merged


class FraudDetectionState(TypedDict):
    """
    State for the fraud detection workflow.
    
    This state is passed through all nodes in the LangGraph workflow,
    accumulating analysis results from each agent.
    """
    check: Check
    client: Optional[Client]
    
    check_analysis: Optional[CheckAnalysisResult]
    transaction_analysis: Optional[TransactionAnalysisResult]
    policy_analysis: Optional[PolicyAnalysisResult]
    generic_analysis: Optional[Dict[str, Any]]
    
    agent_verdicts: Annotated[List[AgentVerdict], merge_verdicts]
    
    final_verdict: Optional[FraudVerdict]
    final_confidence: float
    final_risk_level: Optional[RiskLevel]
    consensus_reached: bool
    voting_summary: Dict[str, Any]
    
    all_flags: List[str]
    all_findings: List[str]
    all_recommendations: List[str]
    
    processing_start_time: datetime
    processing_errors: List[str]
    current_step: str


def create_initial_state(check: Check, client: Optional[Client] = None) -> FraudDetectionState:
    """Create initial state for fraud detection workflow."""
    return FraudDetectionState(
        check=check,
        client=client,
        check_analysis=None,
        transaction_analysis=None,
        policy_analysis=None,
        generic_analysis=None,
        agent_verdicts=[],
        final_verdict=None,
        final_confidence=0.0,
        final_risk_level=None,
        consensus_reached=False,
        voting_summary={},
        all_flags=[],
        all_findings=[],
        all_recommendations=[],
        processing_start_time=datetime.now(),
        processing_errors=[],
        current_step="initialized",
    )
