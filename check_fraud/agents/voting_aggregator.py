"""Voting Aggregator - Combines verdicts from all agents."""

from typing import Dict, Any, List
from datetime import datetime
from collections import Counter

from database.models import AgentVerdict, FraudVerdict, RiskLevel, FraudAnalysisResult
from graph.state import FraudDetectionState


class VotingAggregator:
    """
    Aggregates verdicts from all fraud detection agents.
    
    Implements weighted voting with configurable weights per agent
    and consensus-based final decision making.
    """
    
    AGENT_NAME = "voting_aggregator"
    
    DEFAULT_WEIGHTS = {
        "check_analysis_agent": 1.0,
        "transaction_history_agent": 1.0,
        "policy_analysis_agent": 1.2,
        "generic_fraud_agent": 1.5,
    }
    
    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS
    
    def aggregate(self, state: FraudDetectionState) -> Dict[str, Any]:
        """
        Aggregate all agent verdicts into a final decision.
        
        Args:
            state: Current workflow state with all agent verdicts
        
        Returns:
            Updated state with final verdict and voting summary
        """
        verdicts = state.get("agent_verdicts", [])
        
        if not verdicts:
            return self._no_verdicts_result()
        
        voting_summary = self._calculate_voting_summary(verdicts)
        final_verdict, final_confidence = self._determine_final_verdict(verdicts, voting_summary)
        final_risk_level = self._determine_final_risk_level(verdicts, voting_summary)
        consensus_reached = self._check_consensus(verdicts, final_verdict)
        
        all_flags = list(set(state.get("all_flags", [])))
        all_findings = list(set(state.get("all_findings", [])))
        all_recommendations = self._consolidate_recommendations(verdicts, final_verdict)
        
        processing_time = (datetime.now() - state["processing_start_time"]).total_seconds()
        
        return {
            "final_verdict": final_verdict,
            "final_confidence": final_confidence,
            "final_risk_level": final_risk_level,
            "consensus_reached": consensus_reached,
            "voting_summary": voting_summary,
            "all_flags": all_flags,
            "all_findings": all_findings,
            "all_recommendations": all_recommendations,
            "current_step": "voting_complete",
            "processing_time_seconds": processing_time,
        }
    
    def _calculate_voting_summary(self, verdicts: List[AgentVerdict]) -> Dict[str, Any]:
        """Calculate detailed voting summary."""
        vote_counts = Counter()
        weighted_scores = {
            FraudVerdict.FRAUD: 0.0,
            FraudVerdict.NOT_FRAUD: 0.0,
            FraudVerdict.REVIEW: 0.0,
        }
        
        agent_votes = {}
        total_weight = 0.0
        
        for verdict in verdicts:
            weight = self.weights.get(verdict.agent_name, 1.0)
            confidence_adjusted_weight = weight * verdict.confidence
            
            vote_counts[verdict.verdict] += 1
            weighted_scores[verdict.verdict] += confidence_adjusted_weight
            total_weight += confidence_adjusted_weight
            
            agent_votes[verdict.agent_name] = {
                "verdict": verdict.verdict.value,
                "confidence": verdict.confidence,
                "risk_level": verdict.risk_level.value,
                "weight": weight,
                "weighted_score": confidence_adjusted_weight,
            }
        
        if total_weight > 0:
            normalized_scores = {
                k.value: v / total_weight for k, v in weighted_scores.items()
            }
        else:
            normalized_scores = {v.value: 0.0 for v in FraudVerdict}
        
        return {
            "total_agents": len(verdicts),
            "vote_counts": {k.value: v for k, v in vote_counts.items()},
            "weighted_scores": {k.value: v for k, v in weighted_scores.items()},
            "normalized_scores": normalized_scores,
            "agent_votes": agent_votes,
            "total_weight": total_weight,
            "majority_verdict": max(vote_counts, key=vote_counts.get).value if vote_counts else None,
            "weighted_verdict": max(weighted_scores, key=weighted_scores.get).value if weighted_scores else None,
        }
    
    def _determine_final_verdict(
        self,
        verdicts: List[AgentVerdict],
        summary: Dict[str, Any],
    ) -> tuple:
        """Determine final verdict using weighted voting."""
        normalized = summary["normalized_scores"]
        
        fraud_score = normalized.get("fraud", 0)
        not_fraud_score = normalized.get("not_fraud", 0)
        review_score = normalized.get("review", 0)
        
        any_critical_fraud = any(
            v.verdict == FraudVerdict.FRAUD and v.risk_level == RiskLevel.CRITICAL
            for v in verdicts
        )
        
        if any_critical_fraud:
            return FraudVerdict.FRAUD, max(0.85, fraud_score)
        
        if fraud_score > 0.5:
            confidence = 0.6 + (fraud_score - 0.5) * 0.8
            return FraudVerdict.FRAUD, min(confidence, 0.95)
        
        if not_fraud_score > 0.6:
            confidence = 0.6 + (not_fraud_score - 0.6) * 0.8
            return FraudVerdict.NOT_FRAUD, min(confidence, 0.95)
        
        if fraud_score > 0.3 or review_score > 0.3:
            confidence = 0.5 + review_score * 0.3
            return FraudVerdict.REVIEW, min(confidence, 0.85)
        
        return FraudVerdict.NOT_FRAUD, not_fraud_score + 0.3
    
    def _determine_final_risk_level(
        self,
        verdicts: List[AgentVerdict],
        summary: Dict[str, Any],
    ) -> RiskLevel:
        """Determine final risk level."""
        risk_scores = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }
        
        weighted_risk = 0.0
        total_weight = 0.0
        
        for verdict in verdicts:
            weight = self.weights.get(verdict.agent_name, 1.0) * verdict.confidence
            risk_value = risk_scores.get(verdict.risk_level, 2)
            weighted_risk += risk_value * weight
            total_weight += weight
        
        if total_weight > 0:
            avg_risk = weighted_risk / total_weight
        else:
            avg_risk = 2
        
        max_risk = max(verdicts, key=lambda v: risk_scores.get(v.risk_level, 0)).risk_level
        
        if avg_risk >= 3.5 or max_risk == RiskLevel.CRITICAL:
            return RiskLevel.CRITICAL
        elif avg_risk >= 2.5:
            return RiskLevel.HIGH
        elif avg_risk >= 1.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _check_consensus(
        self,
        verdicts: List[AgentVerdict],
        final_verdict: FraudVerdict,
    ) -> bool:
        """Check if agents reached consensus."""
        if len(verdicts) < 2:
            return True
        
        matching = sum(1 for v in verdicts if v.verdict == final_verdict)
        consensus_threshold = 0.6
        
        return matching / len(verdicts) >= consensus_threshold
    
    def _consolidate_recommendations(
        self,
        verdicts: List[AgentVerdict],
        final_verdict: FraudVerdict,
    ) -> List[str]:
        """Consolidate and prioritize recommendations."""
        all_recs = []
        for verdict in verdicts:
            all_recs.extend(verdict.recommendations)
        
        unique_recs = list(dict.fromkeys(all_recs))
        
        priority_keywords = {
            "REJECT": 1,
            "ESCALATE": 2,
            "VERIFY": 3,
            "REVIEW": 4,
            "FLAG": 5,
            "REQUEST": 6,
            "APPROVE": 7,
        }
        
        def get_priority(rec: str) -> int:
            for keyword, priority in priority_keywords.items():
                if keyword in rec.upper():
                    return priority
            return 10
        
        sorted_recs = sorted(unique_recs, key=get_priority)
        
        if final_verdict == FraudVerdict.FRAUD:
            if not any("REJECT" in r.upper() for r in sorted_recs):
                sorted_recs.insert(0, "REJECT: Multiple fraud indicators detected")
        elif final_verdict == FraudVerdict.REVIEW:
            if not any("REVIEW" in r.upper() or "ESCALATE" in r.upper() for r in sorted_recs):
                sorted_recs.insert(0, "REVIEW: Manual verification required before processing")
        
        return sorted_recs[:10]
    
    def _no_verdicts_result(self) -> Dict[str, Any]:
        """Handle case with no verdicts."""
        return {
            "final_verdict": FraudVerdict.REVIEW,
            "final_confidence": 0.0,
            "final_risk_level": RiskLevel.MEDIUM,
            "consensus_reached": False,
            "voting_summary": {
                "total_agents": 0,
                "error": "No agent verdicts available",
            },
            "all_recommendations": ["Manual review required - no automated analysis available"],
            "current_step": "voting_complete_no_verdicts",
        }
    
    def create_analysis_result(
        self,
        state: FraudDetectionState,
    ) -> FraudAnalysisResult:
        """Create final FraudAnalysisResult from state."""
        check = state["check"]
        check_dict = check.model_dump() if hasattr(check, 'model_dump') else dict(check)
        
        return FraudAnalysisResult(
            analysis_id=f"ANALYSIS_{check_dict.get('check_id', 'UNKNOWN')}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            check_id=check_dict.get("check_id", "UNKNOWN"),
            client_id=check_dict.get("client_id", "UNKNOWN"),
            agent_verdicts=state.get("agent_verdicts", []),
            final_verdict=state.get("final_verdict", FraudVerdict.UNKNOWN),
            final_confidence=state.get("final_confidence", 0.0),
            final_risk_level=state.get("final_risk_level", RiskLevel.MEDIUM),
            consensus_reached=state.get("consensus_reached", False),
            voting_summary=state.get("voting_summary", {}),
            analysis_timestamp=datetime.now(),
            processing_time_seconds=state.get("processing_time_seconds", 0.0),
            notes=self._generate_analysis_notes(state),
        )
    
    def _generate_analysis_notes(self, state: FraudDetectionState) -> str:
        """Generate summary notes for the analysis."""
        parts = ["Fraud Analysis Summary"]
        parts.append("=" * 40)
        
        check = state["check"]
        check_dict = check.model_dump() if hasattr(check, 'model_dump') else dict(check)
        parts.append(f"\nCheck: {check_dict.get('check_id')} - ${check_dict.get('amount', 0):,.2f}")
        parts.append(f"Payee: {check_dict.get('payee', 'Unknown')}")
        
        parts.append(f"\nFinal Verdict: {state.get('final_verdict', 'Unknown')}")
        parts.append(f"Confidence: {state.get('final_confidence', 0):.1%}")
        parts.append(f"Risk Level: {state.get('final_risk_level', 'Unknown')}")
        parts.append(f"Consensus: {'Yes' if state.get('consensus_reached') else 'No'}")
        
        summary = state.get("voting_summary", {})
        if summary.get("vote_counts"):
            parts.append(f"\nVoting: {summary['vote_counts']}")
        
        flags = state.get("all_flags", [])
        if flags:
            parts.append(f"\nFlags Raised: {len(flags)}")
            for flag in flags[:5]:
                parts.append(f"  - {flag}")
        
        errors = state.get("processing_errors", [])
        if errors:
            parts.append(f"\nProcessing Errors: {len(errors)}")
        
        return "\n".join(parts)
