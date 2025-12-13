"""Policy database for fraud detection rules."""

from typing import List, Optional, Dict, Any
import re
from datetime import datetime

from .models import FraudPolicy, Check, Client, RiskLevel
from .sample_data import create_fraud_policies


class PolicyDatabase:
    """In-memory policy database for fraud detection rules."""
    
    def __init__(self):
        self.policies: Dict[str, FraudPolicy] = {}
        self._load_sample_policies()
    
    def _load_sample_policies(self):
        """Load sample policies into the database."""
        for policy in create_fraud_policies():
            self.policies[policy.policy_id] = policy
    
    def get_policy(self, policy_id: str) -> Optional[FraudPolicy]:
        """Get a policy by ID."""
        return self.policies.get(policy_id)
    
    def get_all_policies(self, active_only: bool = True) -> List[FraudPolicy]:
        """Get all policies, optionally filtered by active status."""
        policies = list(self.policies.values())
        if active_only:
            policies = [p for p in policies if p.is_active]
        return policies
    
    def get_policies_by_category(self, category: str) -> List[FraudPolicy]:
        """Get policies by category."""
        return [
            p for p in self.policies.values()
            if p.category == category and p.is_active
        ]
    
    def evaluate_check(
        self,
        check: Check,
        client: Optional[Client] = None,
        transaction_stats: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Evaluate a check against all active policies."""
        violations = []
        
        for policy in self.get_all_policies(active_only=True):
            result = self._evaluate_policy(policy, check, client, transaction_stats)
            if result["violated"]:
                violations.append({
                    "policy_id": policy.policy_id,
                    "policy_name": policy.name,
                    "description": policy.description,
                    "category": policy.category,
                    "severity": policy.severity,
                    "action": policy.action,
                    "details": result.get("details", ""),
                })
        
        return violations
    
    def _evaluate_policy(
        self,
        policy: FraudPolicy,
        check: Check,
        client: Optional[Client],
        stats: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate a single policy against a check."""
        conditions = policy.conditions
        
        if policy.rule_type == "boolean":
            return self._evaluate_boolean(conditions, check)
        
        elif policy.rule_type == "threshold":
            return self._evaluate_threshold(conditions, check, client, stats)
        
        elif policy.rule_type == "pattern":
            return self._evaluate_pattern(conditions, check)
        
        elif policy.rule_type == "compound":
            return self._evaluate_compound(conditions, check, client, stats)
        
        elif policy.rule_type == "list_check":
            return self._evaluate_list_check(conditions, check, client)
        
        elif policy.rule_type == "comparison":
            return self._evaluate_comparison(conditions, check, client)
        
        elif policy.rule_type == "velocity":
            return {"violated": False, "details": "Velocity checks require transaction history"}
        
        elif policy.rule_type == "validation":
            return self._evaluate_validation(conditions, check)
        
        return {"violated": False}
    
    def _get_field_value(self, field: str, check: Check, client: Optional[Client] = None) -> Any:
        """Get a field value from check or client."""
        if field.startswith("metadata."):
            key = field.replace("metadata.", "")
            return check.metadata.get(key)
        
        if field.startswith("client.") and client:
            key = field.replace("client.", "")
            return getattr(client, key, None)
        
        if field == "account_age_days" and client:
            return (datetime.now() - client.account_opened_date).days
        
        return getattr(check, field, None)
    
    def _evaluate_boolean(self, conditions: dict, check: Check) -> Dict[str, Any]:
        """Evaluate boolean condition."""
        field = conditions.get("field")
        expected = conditions.get("value")
        actual = self._get_field_value(field, check)
        
        violated = actual == expected
        return {
            "violated": violated,
            "details": f"{field} is {actual}" if violated else "",
        }
    
    def _evaluate_threshold(
        self,
        conditions: dict,
        check: Check,
        client: Optional[Client],
        stats: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate threshold condition."""
        field = conditions.get("field")
        operator = conditions.get("operator")
        threshold = conditions.get("threshold")
        
        value = self._get_field_value(field, check, client)
        if value is None:
            return {"violated": False}
        
        if operator == "exceeds_average_by_percent" and stats:
            avg = stats.get("average_amount", 0)
            if avg > 0:
                percent_over = ((value - avg) / avg) * 100
                violated = percent_over > threshold
                return {
                    "violated": violated,
                    "details": f"Amount ${value} exceeds average ${avg:.2f} by {percent_over:.1f}%" if violated else "",
                }
        
        elif operator == "less_than":
            violated = value < threshold
            return {
                "violated": violated,
                "details": f"{field} ({value}) is less than {threshold}" if violated else "",
            }
        
        elif operator == "greater_than":
            violated = value > threshold
            return {
                "violated": violated,
                "details": f"{field} ({value}) exceeds {threshold}" if violated else "",
            }
        
        return {"violated": False}
    
    def _evaluate_pattern(self, conditions: dict, check: Check) -> Dict[str, Any]:
        """Evaluate pattern matching condition."""
        field = conditions.get("field")
        pattern = conditions.get("pattern")
        case_insensitive = conditions.get("case_insensitive", False)
        
        value = self._get_field_value(field, check)
        if value is None:
            return {"violated": False}
        
        flags = re.IGNORECASE if case_insensitive else 0
        violated = bool(re.search(pattern, str(value), flags))
        
        return {
            "violated": violated,
            "details": f"{field} matches suspicious pattern: {value}" if violated else "",
        }
    
    def _evaluate_compound(
        self,
        conditions: dict,
        check: Check,
        client: Optional[Client],
        stats: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate compound (AND/OR) conditions."""
        all_conditions = conditions.get("all", [])
        any_conditions = conditions.get("any", [])
        
        if all_conditions:
            results = []
            for cond in all_conditions:
                result = self._evaluate_single_condition(cond, check, client, stats)
                results.append(result)
            
            violated = all(r["violated"] for r in results)
            details = "; ".join(r["details"] for r in results if r["violated"])
            return {"violated": violated, "details": details}
        
        if any_conditions:
            results = []
            for cond in any_conditions:
                result = self._evaluate_single_condition(cond, check, client, stats)
                results.append(result)
            
            violated = any(r["violated"] for r in results)
            details = "; ".join(r["details"] for r in results if r["violated"])
            return {"violated": violated, "details": details}
        
        return {"violated": False}
    
    def _evaluate_single_condition(
        self,
        condition: dict,
        check: Check,
        client: Optional[Client],
        stats: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate a single condition within a compound rule."""
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")
        
        actual = self._get_field_value(field, check, client)
        if actual is None:
            return {"violated": False, "details": ""}
        
        if operator == "less_than":
            violated = actual < value
        elif operator == "greater_than":
            violated = actual > value
        elif operator == "equals":
            violated = actual == value
        elif operator == "is_round_number":
            precision = condition.get("precision", 100)
            violated = actual % precision == 0
        else:
            violated = False
        
        return {
            "violated": violated,
            "details": f"{field}: {actual} {operator} {value}" if violated else "",
        }
    
    def _evaluate_list_check(
        self,
        conditions: dict,
        check: Check,
        client: Optional[Client],
    ) -> Dict[str, Any]:
        """Evaluate list membership condition."""
        field = conditions.get("field")
        operator = conditions.get("operator")
        reference = conditions.get("reference")
        
        value = self._get_field_value(field, check)
        if value is None:
            return {"violated": False}
        
        ref_list = []
        if reference and client:
            ref_field = reference.replace("client.", "")
            ref_list = getattr(client, ref_field, [])
        
        value_lower = str(value).lower()
        ref_list_lower = [str(r).lower() for r in ref_list]
        
        if operator == "not_in":
            violated = value_lower not in ref_list_lower
        elif operator == "in":
            violated = value_lower in ref_list_lower
        else:
            violated = False
        
        return {
            "violated": violated,
            "details": f"Payee '{value}' not in typical payees" if violated else "",
        }
    
    def _evaluate_comparison(
        self,
        conditions: dict,
        check: Check,
        client: Optional[Client],
    ) -> Dict[str, Any]:
        """Evaluate field comparison condition."""
        field = conditions.get("field")
        operator = conditions.get("operator")
        reference = conditions.get("reference")
        
        value = self._get_field_value(field, check)
        ref_value = self._get_field_value(reference, check, client)
        
        if value is None or ref_value is None:
            return {"violated": False}
        
        if operator == "equals":
            violated = str(value).lower() == str(ref_value).lower()
        elif operator == "not_equals":
            violated = str(value).lower() != str(ref_value).lower()
        else:
            violated = False
        
        return {
            "violated": violated,
            "details": f"Check payee '{value}' matches account holder name" if violated else "",
        }
    
    def _evaluate_validation(self, conditions: dict, check: Check) -> Dict[str, Any]:
        """Evaluate validation rules like amount matching."""
        fields = conditions.get("fields", [])
        operator = conditions.get("operator")
        
        if operator == "must_match" and len(fields) == 2:
            return {"violated": False, "details": "Amount validation requires OCR comparison"}
        
        return {"violated": False}
    
    def get_policy_summary(self) -> Dict[str, Any]:
        """Get a summary of all policies."""
        policies = self.get_all_policies()
        
        by_category = {}
        by_severity = {}
        
        for policy in policies:
            by_category[policy.category] = by_category.get(policy.category, 0) + 1
            by_severity[policy.severity.value] = by_severity.get(policy.severity.value, 0) + 1
        
        return {
            "total_policies": len(policies),
            "by_category": by_category,
            "by_severity": by_severity,
            "categories": list(by_category.keys()),
        }
    
    def get_policies_as_text(self) -> str:
        """Get all policies formatted as text for LLM consumption."""
        policies = self.get_all_policies()
        
        text_parts = ["# Fraud Detection Policies\n"]
        
        for policy in policies:
            text_parts.append(f"\n## {policy.name} ({policy.policy_id})")
            text_parts.append(f"**Category:** {policy.category}")
            text_parts.append(f"**Severity:** {policy.severity.value}")
            text_parts.append(f"**Description:** {policy.description}")
            text_parts.append(f"**Action:** {policy.action}")
            text_parts.append(f"**Conditions:** {policy.conditions}")
            text_parts.append("")
        
        return "\n".join(text_parts)
