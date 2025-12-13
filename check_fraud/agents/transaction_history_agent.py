"""Transaction History Agent - Analyzes client's check transaction history."""

from typing import Dict, Any, Optional
from datetime import datetime

from database.models import AgentVerdict, FraudVerdict, RiskLevel, Check, Client
from database.transaction_db import TransactionDatabase
from graph.state import FraudDetectionState, TransactionAnalysisResult


class TransactionHistoryAgent:
    """
    Agent responsible for analyzing client's transaction history.
    
    Analyzes:
    - Historical transaction patterns
    - Amount anomalies
    - Payee patterns
    - Transaction velocity
    - Account age and behavior
    """
    
    AGENT_NAME = "transaction_history_agent"
    
    def __init__(self, transaction_db: Optional[TransactionDatabase] = None):
        self.db = transaction_db or TransactionDatabase()
    
    def analyze(self, state: FraudDetectionState) -> Dict[str, Any]:
        """
        Analyze check against client's transaction history.
        
        Args:
            state: Current workflow state
        
        Returns:
            Updated state with transaction analysis results
        """
        check = state["check"]
        check_dict = check.model_dump() if hasattr(check, 'model_dump') else dict(check)
        
        client_id = check_dict.get("client_id", "")
        client = self.db.get_client(client_id)
        
        if not client:
            return self._handle_unknown_client(check_dict)
        
        history_analysis = self.db.analyze_check_against_history(
            check if hasattr(check, 'model_dump') else Check(**check_dict)
        )
        
        stats = history_analysis["transaction_history"]
        amount = check_dict.get("amount", 0)
        payee = check_dict.get("payee", "")
        
        amount_analysis = self._analyze_amount(amount, stats, client)
        payee_analysis = self._analyze_payee(payee, client, history_analysis)
        velocity_analysis = self._analyze_velocity(client_id, history_analysis)
        account_analysis = self._analyze_account(client, amount)
        
        historical_flags = []
        findings = []
        recommendations = []
        
        if amount_analysis["is_anomalous"]:
            historical_flags.append("amount_anomaly")
            findings.append(amount_analysis["details"])
            if amount_analysis["severity"] == "high":
                recommendations.append("Verify transaction with account holder")
        
        if not payee_analysis["is_known"]:
            historical_flags.append("unknown_payee")
            findings.append(f"Payee '{payee}' not in typical payee list")
            if payee_analysis["is_suspicious"]:
                recommendations.append("Verify payee legitimacy")
        
        if velocity_analysis["is_unusual"]:
            historical_flags.append("unusual_velocity")
            findings.append(velocity_analysis["details"])
            recommendations.append("Review recent transaction pattern")
        
        if account_analysis["is_new_account"] and amount > 5000:
            historical_flags.append("new_account_large_transaction")
            findings.append(f"Large transaction (${amount:,.2f}) from account only {account_analysis['age_days']} days old")
            recommendations.append("Enhanced verification for new account")
        
        historical_flags.extend(history_analysis.get("flags", []))
        
        transaction_analysis = TransactionAnalysisResult(
            client_found=True,
            transaction_statistics=stats,
            amount_anomaly_score=history_analysis["amount_anomaly_score"],
            payee_analysis=payee_analysis,
            velocity_analysis=velocity_analysis,
            historical_flags=historical_flags,
        )
        
        verdict = self._determine_verdict(
            transaction_analysis,
            amount_analysis,
            payee_analysis,
            velocity_analysis,
            account_analysis,
            findings,
        )
        
        return {
            "client": client,
            "transaction_analysis": transaction_analysis,
            "agent_verdicts": [verdict],
            "all_flags": historical_flags,
            "all_findings": findings,
            "all_recommendations": recommendations,
            "current_step": "transaction_analysis_complete",
        }
    
    def _handle_unknown_client(self, check_dict: dict) -> Dict[str, Any]:
        """Handle case where client is not found in database."""
        findings = [f"Client ID '{check_dict.get('client_id')}' not found in database"]
        
        transaction_analysis = TransactionAnalysisResult(
            client_found=False,
            transaction_statistics={},
            amount_anomaly_score=0.5,
            payee_analysis={"is_known": False, "is_suspicious": True},
            velocity_analysis={"is_unusual": False},
            historical_flags=["unknown_client"],
        )
        
        verdict = AgentVerdict(
            agent_name=self.AGENT_NAME,
            verdict=FraudVerdict.REVIEW,
            confidence=0.6,
            risk_level=RiskLevel.HIGH,
            reasoning="Client not found in database. Cannot perform historical analysis. Manual verification required.",
            findings=findings,
            recommendations=["Verify client identity", "Check account exists in core banking system"],
            timestamp=datetime.now(),
        )
        
        return {
            "client": None,
            "transaction_analysis": transaction_analysis,
            "agent_verdicts": [verdict],
            "all_flags": ["unknown_client"],
            "all_findings": findings,
            "all_recommendations": ["Verify client identity"],
            "current_step": "transaction_analysis_complete",
        }
    
    def _analyze_amount(self, amount: float, stats: dict, client: Client) -> Dict[str, Any]:
        """Analyze if amount is anomalous for this client."""
        if stats["total_transactions"] == 0:
            return {
                "is_anomalous": True,
                "severity": "medium",
                "details": "No transaction history - cannot establish baseline",
                "z_score": None,
            }
        
        avg = stats["average_amount"]
        std_dev = stats.get("std_dev_amount", avg * 0.3)
        max_historical = stats["max_amount"]
        
        if std_dev > 0:
            z_score = (amount - avg) / std_dev
        else:
            z_score = 0 if amount == avg else 5
        
        percent_of_avg = (amount / avg * 100) if avg > 0 else 0
        exceeds_max = amount > max_historical
        
        if z_score > 4 or percent_of_avg > 1000:
            return {
                "is_anomalous": True,
                "severity": "critical",
                "details": f"Amount ${amount:,.2f} is {percent_of_avg:.0f}% of average (${avg:,.2f}). Z-score: {z_score:.1f}",
                "z_score": z_score,
                "percent_of_average": percent_of_avg,
                "exceeds_historical_max": exceeds_max,
            }
        elif z_score > 3 or percent_of_avg > 500:
            return {
                "is_anomalous": True,
                "severity": "high",
                "details": f"Amount ${amount:,.2f} significantly exceeds average ${avg:,.2f} (Z-score: {z_score:.1f})",
                "z_score": z_score,
                "percent_of_average": percent_of_avg,
                "exceeds_historical_max": exceeds_max,
            }
        elif z_score > 2:
            return {
                "is_anomalous": True,
                "severity": "medium",
                "details": f"Amount ${amount:,.2f} above typical range (avg: ${avg:,.2f})",
                "z_score": z_score,
                "percent_of_average": percent_of_avg,
                "exceeds_historical_max": exceeds_max,
            }
        
        return {
            "is_anomalous": False,
            "severity": "low",
            "details": f"Amount ${amount:,.2f} within normal range (avg: ${avg:,.2f})",
            "z_score": z_score,
            "percent_of_average": percent_of_avg,
            "exceeds_historical_max": exceeds_max,
        }
    
    def _analyze_payee(self, payee: str, client: Client, history: dict) -> Dict[str, Any]:
        """Analyze payee against client's typical payees."""
        is_known = history.get("payee_is_known", False)
        
        suspicious_keywords = [
            "cash", "bearer", "quick cash", "fast money", "wire",
            "overseas", "foreign", "unknown", "anonymous",
        ]
        
        payee_lower = payee.lower()
        is_suspicious = any(kw in payee_lower for kw in suspicious_keywords)
        
        is_self = payee_lower == client.name.lower()
        
        previous_transactions = self.db.get_transactions_by_payee(client.client_id, payee)
        
        return {
            "is_known": is_known,
            "is_suspicious": is_suspicious,
            "is_self_payee": is_self,
            "previous_transactions_count": len(previous_transactions),
            "typical_payees": client.typical_payees,
            "details": self._format_payee_details(payee, is_known, is_suspicious, is_self),
        }
    
    def _format_payee_details(self, payee: str, is_known: bool, is_suspicious: bool, is_self: bool) -> str:
        """Format payee analysis details."""
        parts = [f"Payee: {payee}"]
        
        if is_known:
            parts.append("✓ Known payee from transaction history")
        else:
            parts.append("⚠ New payee - not in typical payee list")
        
        if is_suspicious:
            parts.append("⚠ Payee name contains suspicious keywords")
        
        if is_self:
            parts.append("⚠ Self-payee check detected")
        
        return " | ".join(parts)
    
    def _analyze_velocity(self, client_id: str, history: dict) -> Dict[str, Any]:
        """Analyze transaction velocity."""
        recent_24h = history.get("recent_deposits_24h", 0)
        
        is_unusual = recent_24h > 3
        
        return {
            "is_unusual": is_unusual,
            "deposits_24h": recent_24h,
            "details": f"{recent_24h} deposits in last 24 hours" + (" - unusual activity" if is_unusual else ""),
        }
    
    def _analyze_account(self, client: Client, amount: float) -> Dict[str, Any]:
        """Analyze account characteristics."""
        age_days = (datetime.now() - client.account_opened_date).days
        is_new = age_days < 90
        
        return {
            "age_days": age_days,
            "is_new_account": is_new,
            "risk_score": client.risk_score,
            "average_monthly_transactions": client.average_monthly_transactions,
        }
    
    def _determine_verdict(
        self,
        analysis: TransactionAnalysisResult,
        amount_analysis: dict,
        payee_analysis: dict,
        velocity_analysis: dict,
        account_analysis: dict,
        findings: list,
    ) -> AgentVerdict:
        """Determine verdict based on transaction history analysis."""
        risk_score = 0.0
        
        if amount_analysis["severity"] == "critical":
            risk_score += 0.5
        elif amount_analysis["severity"] == "high":
            risk_score += 0.3
        elif amount_analysis["severity"] == "medium":
            risk_score += 0.15
        
        if payee_analysis["is_suspicious"]:
            risk_score += 0.25
        elif not payee_analysis["is_known"]:
            risk_score += 0.1
        
        if payee_analysis["is_self_payee"]:
            risk_score += 0.15
        
        if velocity_analysis["is_unusual"]:
            risk_score += 0.2
        
        if account_analysis["is_new_account"]:
            risk_score += 0.1
        
        risk_score += account_analysis["risk_score"] * 0.2
        
        risk_score = min(risk_score, 1.0)
        
        if risk_score >= 0.7:
            verdict = FraudVerdict.FRAUD
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 0.5:
            verdict = FraudVerdict.REVIEW
            risk_level = RiskLevel.HIGH
        elif risk_score >= 0.3:
            verdict = FraudVerdict.REVIEW
            risk_level = RiskLevel.MEDIUM
        else:
            verdict = FraudVerdict.NOT_FRAUD
            risk_level = RiskLevel.LOW
        
        confidence = 0.7 + (0.3 * (1 - abs(risk_score - 0.5) * 2))
        
        reasoning = self._generate_reasoning(
            amount_analysis, payee_analysis, velocity_analysis, account_analysis, risk_score
        )
        
        return AgentVerdict(
            agent_name=self.AGENT_NAME,
            verdict=verdict,
            confidence=confidence,
            risk_level=risk_level,
            reasoning=reasoning,
            findings=findings,
            recommendations=self._get_recommendations(analysis["historical_flags"]),
            timestamp=datetime.now(),
        )
    
    def _generate_reasoning(
        self,
        amount: dict,
        payee: dict,
        velocity: dict,
        account: dict,
        risk_score: float,
    ) -> str:
        """Generate reasoning for the verdict."""
        parts = ["Transaction History Analysis:"]
        
        parts.append(f"\nAmount Analysis: {amount['details']}")
        parts.append(f"Payee Analysis: {payee['details']}")
        parts.append(f"Velocity: {velocity['details']}")
        parts.append(f"Account Age: {account['age_days']} days")
        parts.append(f"Client Risk Score: {account['risk_score']:.2f}")
        parts.append(f"\nOverall Historical Risk Score: {risk_score:.1%}")
        
        return "\n".join(parts)
    
    def _get_recommendations(self, flags: list) -> list:
        """Get recommendations based on flags."""
        recommendations = []
        
        if "amount_anomaly" in flags:
            recommendations.append("Contact account holder to verify transaction")
        if "unknown_payee" in flags:
            recommendations.append("Verify payee identity and relationship")
        if "unusual_velocity" in flags:
            recommendations.append("Review all recent transactions for pattern")
        if "new_account_large_transaction" in flags:
            recommendations.append("Apply enhanced due diligence for new account")
        if "self_payee" in flags:
            recommendations.append("Verify purpose of self-payee check")
        
        if not recommendations:
            recommendations.append("Transaction history consistent with client behavior")
        
        return recommendations
