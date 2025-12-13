"""Signature analysis tool for check fraud detection."""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import random


@dataclass
class SignatureAnalysisResult:
    """Result of signature analysis."""
    signature_present: bool
    signature_valid: bool
    confidence: float
    match_score: Optional[float]
    position_correct: bool
    anomalies: List[str]
    forgery_indicators: List[str]
    details: str


class SignatureAnalyzer:
    """
    Simulated signature analysis for check verification.
    
    In production, this would use:
    - Deep learning signature verification models
    - Stroke pattern analysis
    - Pressure point detection
    - Historical signature comparison
    """
    
    FORGERY_INDICATORS = [
        "tremor_lines",
        "pen_lifts",
        "inconsistent_pressure",
        "unnatural_angles",
        "traced_appearance",
        "size_mismatch",
        "style_deviation",
    ]
    
    def __init__(self):
        self.match_threshold = 0.85
        self.minimum_confidence = 0.7
    
    def analyze(self, check_data: Dict[str, Any]) -> SignatureAnalysisResult:
        """
        Analyze signature on a check.
        
        Args:
            check_data: Dictionary containing check information
        
        Returns:
            SignatureAnalysisResult with analysis details
        """
        signature_present = check_data.get("signature_present", True)
        metadata = check_data.get("metadata", {})
        flags = metadata.get("flags", [])
        
        if not signature_present or "missing_signature" in flags:
            return SignatureAnalysisResult(
                signature_present=False,
                signature_valid=False,
                confidence=0.98,
                match_score=None,
                position_correct=False,
                anomalies=["No signature detected in signature field"],
                forgery_indicators=[],
                details="Check is missing required signature. Cannot process unsigned checks.",
            )
        
        if "altered_amount_suspected" in flags:
            return SignatureAnalysisResult(
                signature_present=True,
                signature_valid=False,
                confidence=0.75,
                match_score=0.45,
                position_correct=True,
                anomalies=[
                    "Signature appears genuine but document may be altered",
                    "Ink consistency varies across document",
                ],
                forgery_indicators=["inconsistent_pressure", "traced_appearance"],
                details="Signature present but document alteration suspected. Manual review required.",
            )
        
        image_quality = metadata.get("image_quality_score", 0.85)
        if image_quality and image_quality < 0.5:
            return SignatureAnalysisResult(
                signature_present=True,
                signature_valid=True,
                confidence=0.55,
                match_score=0.6,
                position_correct=True,
                anomalies=["Low image quality affects signature verification accuracy"],
                forgery_indicators=[],
                details="Signature detected but image quality is insufficient for reliable verification.",
            )
        
        confidence = 0.88 + random.uniform(0, 0.1)
        match_score = 0.90 + random.uniform(0, 0.08)
        
        return SignatureAnalysisResult(
            signature_present=True,
            signature_valid=True,
            confidence=confidence,
            match_score=match_score,
            position_correct=True,
            anomalies=[],
            forgery_indicators=[],
            details=f"Signature verified with {confidence:.1%} confidence. Match score: {match_score:.1%}",
        )
    
    def compare_with_reference(
        self,
        check_signature: SignatureAnalysisResult,
        reference_signatures: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compare check signature against reference signatures.
        
        Args:
            check_signature: Result from analyze()
            reference_signatures: List of reference signature data
        
        Returns:
            Comparison result with best match details
        """
        if not check_signature.signature_present:
            return {
                "match_found": False,
                "best_match_score": 0.0,
                "reference_id": None,
                "details": "No signature to compare",
            }
        
        if not reference_signatures:
            return {
                "match_found": False,
                "best_match_score": 0.0,
                "reference_id": None,
                "details": "No reference signatures available for comparison",
            }
        
        best_match = max(reference_signatures, key=lambda x: x.get("confidence_threshold", 0.85))
        match_score = check_signature.match_score or 0.0
        
        return {
            "match_found": match_score >= self.match_threshold,
            "best_match_score": match_score,
            "reference_id": best_match.get("signature_id"),
            "is_primary_signature": best_match.get("is_primary", True),
            "details": f"Best match with reference {best_match.get('signature_id')}: {match_score:.1%}",
        }
    
    def detect_forgery_indicators(
        self,
        check_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze signature for potential forgery indicators.
        
        Args:
            check_data: Check information
        
        Returns:
            Forgery analysis results
        """
        metadata = check_data.get("metadata", {})
        flags = metadata.get("flags", [])
        
        indicators_found = []
        risk_score = 0.0
        
        if "altered_amount_suspected" in flags:
            indicators_found.extend(["traced_appearance", "inconsistent_pressure"])
            risk_score += 0.4
        
        if metadata.get("image_quality_score", 1.0) < 0.5:
            indicators_found.append("low_quality_obscures_details")
            risk_score += 0.2
        
        if metadata.get("device", "").lower() in ["emulator", "rooted android"]:
            indicators_found.append("suspicious_capture_device")
            risk_score += 0.3
        
        return {
            "forgery_indicators": indicators_found,
            "indicator_count": len(indicators_found),
            "risk_score": min(risk_score, 1.0),
            "recommendation": self._get_forgery_recommendation(risk_score),
            "details": self._format_forgery_details(indicators_found),
        }
    
    def _get_forgery_recommendation(self, risk_score: float) -> str:
        """Get recommendation based on forgery risk score."""
        if risk_score >= 0.7:
            return "reject"
        elif risk_score >= 0.4:
            return "manual_review"
        elif risk_score >= 0.2:
            return "flag_for_review"
        return "approve"
    
    def _format_forgery_details(self, indicators: List[str]) -> str:
        """Format forgery indicators into readable details."""
        if not indicators:
            return "No forgery indicators detected."
        
        indicator_descriptions = {
            "tremor_lines": "Unsteady lines suggesting traced signature",
            "pen_lifts": "Unusual pen lifts indicating hesitation",
            "inconsistent_pressure": "Varying pressure inconsistent with natural signing",
            "unnatural_angles": "Letter angles deviate from reference",
            "traced_appearance": "Signature appears traced or copied",
            "size_mismatch": "Signature size differs from reference",
            "style_deviation": "Writing style differs from known samples",
            "low_quality_obscures_details": "Image quality prevents detailed analysis",
            "suspicious_capture_device": "Signature captured on suspicious device",
        }
        
        details = ["Forgery indicators detected:"]
        for indicator in indicators:
            desc = indicator_descriptions.get(indicator, indicator)
            details.append(f"  - {desc}")
        
        return "\n".join(details)
    
    def get_risk_assessment(self, result: SignatureAnalysisResult) -> Dict[str, Any]:
        """Get risk assessment based on signature analysis."""
        if not result.signature_present:
            return {
                "risk_level": "critical",
                "risk_score": 0.99,
                "recommendation": "reject",
                "reason": "Missing signature - check cannot be processed",
            }
        
        if not result.signature_valid:
            return {
                "risk_level": "high",
                "risk_score": 0.8,
                "recommendation": "reject",
                "reason": "Signature validation failed",
            }
        
        if result.forgery_indicators:
            return {
                "risk_level": "high",
                "risk_score": 0.7,
                "recommendation": "manual_review",
                "reason": f"Forgery indicators: {', '.join(result.forgery_indicators)}",
            }
        
        if result.confidence < self.minimum_confidence:
            return {
                "risk_level": "medium",
                "risk_score": 0.5,
                "recommendation": "manual_review",
                "reason": "Low confidence signature verification",
            }
        
        if result.match_score and result.match_score < self.match_threshold:
            return {
                "risk_level": "medium",
                "risk_score": 0.4,
                "recommendation": "flag_for_review",
                "reason": f"Signature match score below threshold: {result.match_score:.1%}",
            }
        
        return {
            "risk_level": "low",
            "risk_score": 0.1,
            "recommendation": "approve",
            "reason": "Signature verification passed",
        }
