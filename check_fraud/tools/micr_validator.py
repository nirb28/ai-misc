"""MICR line validation tool for check fraud detection."""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import re


@dataclass
class MICRValidationResult:
    """Result of MICR line validation."""
    micr_present: bool
    micr_valid: bool
    routing_number: Optional[str]
    account_number: Optional[str]
    check_number: Optional[str]
    routing_valid: bool
    checksum_valid: bool
    anomalies: List[str]
    details: str


class MICRValidator:
    """
    MICR (Magnetic Ink Character Recognition) line validator.
    
    Validates the MICR line at the bottom of checks containing:
    - Routing number (9 digits)
    - Account number (variable length)
    - Check number
    
    MICR Format: ⑆RRRRRRRRR⑆ ⑈AAAAAAAAAA⑈ CCCC
    Where:
    - ⑆ = Transit symbol
    - R = Routing number
    - ⑈ = On-Us symbol  
    - A = Account number
    - C = Check number
    
    Note: MICR validation uses deterministic rules (checksum, format),
    so simulation vs real mode doesn't change the core logic.
    """
    
    VALID_ROUTING_PREFIXES = [
        "01", "02", "03", "04", "05", "06", "07", "08", "09",
        "10", "11", "12",
        "21", "22", "23", "24", "25", "26", "27", "28", "29",
        "30", "31", "32",
        "61", "62", "63", "64", "65", "66", "67", "68", "69",
        "70", "71", "72",
        "80",
    ]
    
    def __init__(self, use_simulation: bool = True, llm=None):
        """
        Initialize MICR validator.
        
        Args:
            use_simulation: Simulation flag (MICR uses deterministic validation regardless).
            llm: LLM instance (not used for MICR - validation is rule-based).
        """
        self.routing_pattern = re.compile(r'⑆(\d{9})⑆')
        self.account_pattern = re.compile(r'⑈(\d+)⑈')
        self.check_pattern = re.compile(r'(\d{3,6})$')
        self.use_simulation = use_simulation
        self.llm = llm
    
    def validate(self, check_data: Dict[str, Any]) -> MICRValidationResult:
        """
        Validate MICR line from check data.
        
        Args:
            check_data: Dictionary containing check information
        
        Returns:
            MICRValidationResult with validation details
        """
        micr_line = check_data.get("micr_line", "")
        expected_routing = check_data.get("routing_number", "")
        expected_account = check_data.get("account_number", "")
        expected_check = check_data.get("check_number", "")
        
        if not micr_line:
            return MICRValidationResult(
                micr_present=False,
                micr_valid=False,
                routing_number=None,
                account_number=None,
                check_number=None,
                routing_valid=False,
                checksum_valid=False,
                anomalies=["MICR line not detected or not provided"],
                details="Missing MICR line - check may be counterfeit or damaged.",
            )
        
        routing_match = self.routing_pattern.search(micr_line)
        account_match = self.account_pattern.search(micr_line)
        check_match = self.check_pattern.search(micr_line.split()[-1] if micr_line.split() else "")
        
        routing = routing_match.group(1) if routing_match else None
        account = account_match.group(1) if account_match else None
        check_num = check_match.group(1) if check_match else None
        
        anomalies = []
        
        routing_valid = False
        checksum_valid = False
        
        if routing:
            routing_valid = self._validate_routing_number(routing)
            if not routing_valid:
                anomalies.append(f"Invalid routing number checksum: {routing}")
            
            if expected_routing and routing != expected_routing:
                anomalies.append(f"Routing number mismatch: expected {expected_routing}, got {routing}")
        else:
            anomalies.append("Could not extract routing number from MICR line")
        
        if account:
            if expected_account and account != expected_account:
                anomalies.append(f"Account number mismatch: expected {expected_account}, got {account}")
        else:
            anomalies.append("Could not extract account number from MICR line")
        
        if check_num:
            if expected_check and check_num != expected_check:
                anomalies.append(f"Check number mismatch: expected {expected_check}, got {check_num}")
        
        micr_valid = routing_valid and routing is not None and account is not None and len(anomalies) == 0
        
        details = self._format_validation_details(
            routing, account, check_num, routing_valid, anomalies
        )
        
        return MICRValidationResult(
            micr_present=True,
            micr_valid=micr_valid,
            routing_number=routing,
            account_number=account,
            check_number=check_num,
            routing_valid=routing_valid,
            checksum_valid=routing_valid,
            anomalies=anomalies,
            details=details,
        )
    
    def _validate_routing_number(self, routing: str) -> bool:
        """
        Validate routing number using ABA checksum algorithm.
        
        The checksum is: 3(d1 + d4 + d7) + 7(d2 + d5 + d8) + (d3 + d6 + d9) mod 10 = 0
        """
        if len(routing) != 9 or not routing.isdigit():
            return False
        
        prefix = routing[:2]
        if prefix not in self.VALID_ROUTING_PREFIXES:
            return False
        
        digits = [int(d) for d in routing]
        checksum = (
            3 * (digits[0] + digits[3] + digits[6]) +
            7 * (digits[1] + digits[4] + digits[7]) +
            (digits[2] + digits[5] + digits[8])
        )
        
        return checksum % 10 == 0
    
    def _format_validation_details(
        self,
        routing: Optional[str],
        account: Optional[str],
        check_num: Optional[str],
        routing_valid: bool,
        anomalies: List[str],
    ) -> str:
        """Format validation results into readable details."""
        parts = ["MICR Line Validation Results:"]
        
        if routing:
            status = "✓ Valid" if routing_valid else "✗ Invalid"
            parts.append(f"  Routing Number: {routing} ({status})")
        
        if account:
            masked = account[:4] + "*" * (len(account) - 4) if len(account) > 4 else account
            parts.append(f"  Account Number: {masked}")
        
        if check_num:
            parts.append(f"  Check Number: {check_num}")
        
        if anomalies:
            parts.append("\nAnomalies Detected:")
            for anomaly in anomalies:
                parts.append(f"  - {anomaly}")
        else:
            parts.append("\nNo anomalies detected.")
        
        return "\n".join(parts)
    
    def cross_reference_routing(self, routing: str) -> Dict[str, Any]:
        """
        Cross-reference routing number with bank database.
        
        In production, this would query a routing number database.
        """
        known_banks = {
            "071000013": {
                "bank_name": "First National Bank",
                "city": "Springfield",
                "state": "IL",
                "valid": True,
            },
            "021000021": {
                "bank_name": "JPMorgan Chase",
                "city": "New York",
                "state": "NY",
                "valid": True,
            },
            "011000015": {
                "bank_name": "Federal Reserve Bank",
                "city": "Boston",
                "state": "MA",
                "valid": True,
            },
        }
        
        if routing in known_banks:
            return {
                "found": True,
                **known_banks[routing],
            }
        
        if self._validate_routing_number(routing):
            return {
                "found": False,
                "bank_name": "Unknown",
                "valid": True,
                "note": "Routing number has valid checksum but not in local database",
            }
        
        return {
            "found": False,
            "bank_name": None,
            "valid": False,
            "note": "Invalid routing number",
        }
    
    def get_risk_assessment(self, result: MICRValidationResult) -> Dict[str, Any]:
        """Get risk assessment based on MICR validation."""
        if not result.micr_present:
            return {
                "risk_level": "critical",
                "risk_score": 0.95,
                "recommendation": "reject",
                "reason": "Missing MICR line - potential counterfeit",
            }
        
        if not result.routing_valid:
            return {
                "risk_level": "critical",
                "risk_score": 0.9,
                "recommendation": "reject",
                "reason": "Invalid routing number",
            }
        
        if len(result.anomalies) > 2:
            return {
                "risk_level": "high",
                "risk_score": 0.7,
                "recommendation": "manual_review",
                "reason": f"Multiple MICR anomalies: {len(result.anomalies)}",
            }
        
        if result.anomalies:
            return {
                "risk_level": "medium",
                "risk_score": 0.4,
                "recommendation": "flag_for_review",
                "reason": f"MICR anomalies detected: {', '.join(result.anomalies)}",
            }
        
        return {
            "risk_level": "low",
            "risk_score": 0.05,
            "recommendation": "approve",
            "reason": "MICR validation passed",
        }
