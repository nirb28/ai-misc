"""Policy Analysis Agent - Applies documented fraud detection policies."""

from typing import Dict, Any, Optional, List
from datetime import datetime

from database.models import AgentVerdict, FraudVerdict, RiskLevel, Check, Client
from database.policy_db import PolicyDatabase
from database.transaction_db import TransactionDatabase
from graph.state import FraudDetectionState, PolicyAnalysisResult


class PolicyAnalysisAgent:
    """
    Agent responsible for policy-based fraud analysis.
    
    Applies documented bank policies and rules to detect fraud:
    - Amount thresholds
    - Physical verification rules
    - Payee analysis rules
    - Velocity checks
    - Device/source analysis
    """
    
    AGENT_NAME = "policy_analysis_agent"
    
    def __init__(
        self,
        policy_db: Optional[PolicyDatabase] = None,
        transaction_db: Optional[TransactionDatabase] = None,
    ):
        self.policy_db = policy_db or PolicyDatabase()
        self.transaction_db = transaction_db or TransactionDatabase()
    
    def analyze(self, state: FraudDetectionState) -> Dict[str, Any]:
        """
        Evaluate check against all active fraud policies.
        
        Args:
            state: Current workflow state
        
        Returns:
            Updated state with policy analysis results
        """
        check = state["check"]
        client = state.get("client")
        
        check_dict = check.model_dump() if hasattr(check, 'model_dump') else dict(check)
        client_obj = client if client else self.transaction_db.get_client(check_dict.get("client_id", ""))
        
        stats = None
        if client_obj:
            stats = self.transaction_db.get_transaction_statistics(client_obj.client_id)
        
        violations = self.policy_db.evaluate_check(
            check if hasattr(check, 'model_dump') else Check(**check_dict),
            client_obj,
            stats,
        )
        
        policy_flags = []
        findings = []
        recommendations = []
        
        severity_order = {
            RiskLevel.CRITICAL: 4,
            RiskLevel.HIGH: 3,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 1,
        }
        
        highest_severity = RiskLevel.LOW
        
        for violation in violations:
            policy_flags.append(f"policy_{violation['policy_id']}")
            findings.append(f"[{violation['severity'].value.upper()}] {violation['policy_name']}: {violation['details']}")
            
            if violation['action'] == 'reject':
                recommendations.append(f"REJECT per policy {violation['policy_id']}: {violation['policy_name']}")
            elif violation['action'] == 'flag_as_suspicious':
                recommendations.append(f"FLAG as suspicious per {violation['policy_id']}")
            else:
                recommendations.append(f"REVIEW per policy {violation['policy_id']}")
            
            if severity_order.get(violation['severity'], 0) > severity_order.get(highest_severity, 0):
                highest_severity = violation['severity']
        
        policy_analysis = PolicyAnalysisResult(
            policies_evaluated=len(self.policy_db.get_all_policies()),
            violations=violations,
            violation_count=len(violations),
            highest_severity=highest_severity.value if violations else "none",
            policy_flags=policy_flags,
        )
        
        verdict = self._determine_verdict(policy_analysis, violations, findings)
        
        return {
            "policy_analysis": policy_analysis,
            "agent_verdicts": [verdict],
            "all_flags": policy_flags,
            "all_findings": findings,
            "all_recommendations": recommendations,
            "current_step": "policy_analysis_complete",
        }
    
    def _determine_verdict(
        self,
        analysis: PolicyAnalysisResult,
        violations: List[Dict[str, Any]],
        findings: list,
    ) -> AgentVerdict:
        """Determine verdict based on policy violations."""
        if not violations:
            return AgentVerdict(
                agent_name=self.AGENT_NAME,
                verdict=FraudVerdict.NOT_FRAUD,
                confidence=0.85,
                risk_level=RiskLevel.LOW,
                reasoning=f"Check passed all {analysis['policies_evaluated']} active fraud detection policies.",
                findings=["No policy violations detected"],
                recommendations=["Approve - compliant with all policies"],
                timestamp=datetime.now(),
            )
        
        critical_count = sum(1 for v in violations if v['severity'] == RiskLevel.CRITICAL)
        high_count = sum(1 for v in violations if v['severity'] == RiskLevel.HIGH)
        medium_count = sum(1 for v in violations if v['severity'] == RiskLevel.MEDIUM)
        
        reject_actions = sum(1 for v in violations if v['action'] == 'reject')
        
        if reject_actions > 0 or critical_count > 0:
            verdict = FraudVerdict.FRAUD
            risk_level = RiskLevel.CRITICAL
            confidence = 0.9 + (0.02 * critical_count)
        elif high_count >= 2 or (high_count >= 1 and medium_count >= 2):
            verdict = FraudVerdict.FRAUD
            risk_level = RiskLevel.HIGH
            confidence = 0.75 + (0.05 * high_count)
        elif high_count >= 1:
            verdict = FraudVerdict.REVIEW
            risk_level = RiskLevel.HIGH
            confidence = 0.7
        elif medium_count >= 2:
            verdict = FraudVerdict.REVIEW
            risk_level = RiskLevel.MEDIUM
            confidence = 0.65
        else:
            verdict = FraudVerdict.REVIEW
            risk_level = RiskLevel.LOW
            confidence = 0.6
        
        confidence = min(confidence, 0.98)
        
        reasoning = self._generate_reasoning(analysis, violations, critical_count, high_count, medium_count)
        
        return AgentVerdict(
            agent_name=self.AGENT_NAME,
            verdict=verdict,
            confidence=confidence,
            risk_level=risk_level,
            reasoning=reasoning,
            findings=findings,
            recommendations=self._get_recommendations(violations),
            timestamp=datetime.now(),
        )
    
    def _generate_reasoning(
        self,
        analysis: PolicyAnalysisResult,
        violations: list,
        critical: int,
        high: int,
        medium: int,
    ) -> str:
        """Generate reasoning for the verdict."""
        parts = ["Policy-Based Analysis Results:"]
        parts.append(f"\nPolicies Evaluated: {analysis['policies_evaluated']}")
        parts.append(f"Violations Found: {len(violations)}")
        
        if violations:
            parts.append(f"\nViolation Breakdown:")
            parts.append(f"  - Critical: {critical}")
            parts.append(f"  - High: {high}")
            parts.append(f"  - Medium: {medium}")
            parts.append(f"  - Low: {len(violations) - critical - high - medium}")
            
            parts.append(f"\nViolated Policies:")
            for v in violations[:5]:
                parts.append(f"  • {v['policy_name']} ({v['severity'].value})")
            
            if len(violations) > 5:
                parts.append(f"  ... and {len(violations) - 5} more")
        
        return "\n".join(parts)
    
    def _get_recommendations(self, violations: list) -> list:
        """Get recommendations based on violations."""
        recommendations = []
        
        has_reject = any(v['action'] == 'reject' for v in violations)
        has_critical = any(v['severity'] == RiskLevel.CRITICAL for v in violations)
        
        if has_reject:
            recommendations.append("REJECT: Policy mandates rejection")
        elif has_critical:
            recommendations.append("ESCALATE: Critical policy violation requires senior review")
        
        categories = set(v['category'] for v in violations)
        
        if 'physical_verification' in categories:
            recommendations.append("Verify physical check authenticity")
        if 'amount_analysis' in categories:
            recommendations.append("Verify transaction amount with account holder")
        if 'payee_analysis' in categories:
            recommendations.append("Verify payee identity and legitimacy")
        if 'device_analysis' in categories:
            recommendations.append("Investigate deposit device/method")
        if 'velocity_analysis' in categories:
            recommendations.append("Review recent transaction pattern")
        
        return recommendations if recommendations else ["Review flagged items before approval"]
    
    def get_applicable_policies(self, check: Check) -> List[Dict[str, Any]]:
        """Get list of policies that would apply to this check."""
        check_dict = check.model_dump() if hasattr(check, 'model_dump') else dict(check)
        
        applicable = []
        for policy in self.policy_db.get_all_policies():
            applicable.append({
                "policy_id": policy.policy_id,
                "name": policy.name,
                "category": policy.category,
                "severity": policy.severity.value,
                "description": policy.description,
            })
        
        return applicable
    
    def get_policy_documentation(self) -> str:
        """Get formatted policy documentation for LLM consumption."""
        return self.policy_db.get_policies_as_text()
