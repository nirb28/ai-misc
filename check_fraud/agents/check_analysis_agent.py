"""Check Analysis Agent - Analyzes physical check characteristics."""

from typing import Dict, Any
from datetime import datetime

from database.models import AgentVerdict, FraudVerdict, RiskLevel, Check
from tools import WatermarkDetector, SignatureAnalyzer, MICRValidator, ImageQualityAnalyzer
from graph.state import FraudDetectionState, CheckAnalysisResult


class CheckAnalysisAgent:
    """
    Agent responsible for analyzing physical check characteristics.
    
    Analyzes:
    - Watermark presence and authenticity
    - Signature validity and comparison
    - MICR line validation
    - Image quality assessment
    """
    
    AGENT_NAME = "check_analysis_agent"
    
    def __init__(self):
        self.watermark_detector = WatermarkDetector()
        self.signature_analyzer = SignatureAnalyzer()
        self.micr_validator = MICRValidator()
        self.image_analyzer = ImageQualityAnalyzer()
    
    def analyze(self, state: FraudDetectionState) -> Dict[str, Any]:
        """
        Perform comprehensive physical check analysis.
        
        Args:
            state: Current workflow state containing check data
        
        Returns:
            Updated state with check analysis results
        """
        check = state["check"]
        check_dict = check.model_dump() if hasattr(check, 'model_dump') else check
        
        watermark_result = self.watermark_detector.analyze(check_dict)
        watermark_risk = self.watermark_detector.get_risk_assessment(watermark_result)
        
        signature_result = self.signature_analyzer.analyze(check_dict)
        signature_risk = self.signature_analyzer.get_risk_assessment(signature_result)
        forgery_analysis = self.signature_analyzer.detect_forgery_indicators(check_dict)
        
        micr_result = self.micr_validator.validate(check_dict)
        micr_risk = self.micr_validator.get_risk_assessment(micr_result)
        
        image_result = self.image_analyzer.analyze(check_dict)
        image_risk = self.image_analyzer.get_risk_assessment(image_result)
        manipulation_check = self.image_analyzer.check_for_manipulation(check_dict)
        
        physical_flags = []
        findings = []
        recommendations = []
        
        if not watermark_result.watermark_detected:
            physical_flags.append("missing_watermark")
            findings.append("Check is missing bank watermark")
            recommendations.append("Reject check - missing security feature")
        
        if not signature_result.signature_present:
            physical_flags.append("missing_signature")
            findings.append("Check is missing required signature")
            recommendations.append("Reject check - unsigned")
        elif signature_result.forgery_indicators:
            physical_flags.append("forgery_indicators")
            findings.append(f"Forgery indicators detected: {', '.join(signature_result.forgery_indicators)}")
            recommendations.append("Manual signature verification required")
        
        if not micr_result.micr_valid:
            physical_flags.append("invalid_micr")
            findings.append(f"MICR validation failed: {', '.join(micr_result.anomalies)}")
            recommendations.append("Verify routing and account numbers manually")
        
        if image_result.overall_score < 0.6:
            physical_flags.append("low_image_quality")
            findings.append(f"Image quality score: {image_result.overall_score:.1%}")
            recommendations.append("Request higher quality image if possible")
        
        if manipulation_check["manipulation_detected"]:
            physical_flags.append("manipulation_suspected")
            findings.extend(manipulation_check["indicators"])
            recommendations.append("Detailed forensic analysis recommended")
        
        risk_scores = [
            watermark_risk["risk_score"],
            signature_risk["risk_score"],
            micr_risk["risk_score"],
            image_risk["risk_score"],
        ]
        overall_risk = max(risk_scores)
        
        if manipulation_check["manipulation_detected"]:
            overall_risk = max(overall_risk, manipulation_check["confidence"])
        
        check_analysis = CheckAnalysisResult(
            watermark_analysis={
                "detected": watermark_result.watermark_detected,
                "confidence": watermark_result.confidence,
                "type": watermark_result.watermark_type,
                "risk": watermark_risk,
                "details": watermark_result.details,
            },
            signature_analysis={
                "present": signature_result.signature_present,
                "valid": signature_result.signature_valid,
                "confidence": signature_result.confidence,
                "match_score": signature_result.match_score,
                "forgery_indicators": signature_result.forgery_indicators,
                "risk": signature_risk,
                "details": signature_result.details,
            },
            micr_validation={
                "present": micr_result.micr_present,
                "valid": micr_result.micr_valid,
                "routing_number": micr_result.routing_number,
                "routing_valid": micr_result.routing_valid,
                "anomalies": micr_result.anomalies,
                "risk": micr_risk,
                "details": micr_result.details,
            },
            image_quality={
                "score": image_result.overall_score,
                "adequate": image_result.resolution_adequate,
                "issues": image_result.issues,
                "manipulation_check": manipulation_check,
                "risk": image_risk,
                "details": image_result.details,
            },
            overall_physical_risk=overall_risk,
            physical_flags=physical_flags,
        )
        
        verdict = self._determine_verdict(check_analysis, findings)
        
        return {
            "check_analysis": check_analysis,
            "agent_verdicts": [verdict],
            "all_flags": physical_flags,
            "all_findings": findings,
            "all_recommendations": recommendations,
            "current_step": "check_analysis_complete",
        }
    
    def _determine_verdict(
        self,
        analysis: CheckAnalysisResult,
        findings: list,
    ) -> AgentVerdict:
        """Determine verdict based on physical analysis."""
        risk = analysis["overall_physical_risk"]
        flags = analysis["physical_flags"]
        
        critical_flags = {"missing_signature", "invalid_micr", "manipulation_suspected"}
        high_risk_flags = {"missing_watermark", "forgery_indicators"}
        
        has_critical = bool(critical_flags & set(flags))
        has_high_risk = bool(high_risk_flags & set(flags))
        
        if has_critical or risk >= 0.8:
            verdict = FraudVerdict.FRAUD
            confidence = min(0.95, risk + 0.1)
            risk_level = RiskLevel.CRITICAL
        elif has_high_risk or risk >= 0.6:
            verdict = FraudVerdict.REVIEW
            confidence = risk
            risk_level = RiskLevel.HIGH
        elif risk >= 0.4:
            verdict = FraudVerdict.REVIEW
            confidence = risk
            risk_level = RiskLevel.MEDIUM
        else:
            verdict = FraudVerdict.NOT_FRAUD
            confidence = 1.0 - risk
            risk_level = RiskLevel.LOW
        
        reasoning = self._generate_reasoning(analysis, flags)
        
        return AgentVerdict(
            agent_name=self.AGENT_NAME,
            verdict=verdict,
            confidence=confidence,
            risk_level=risk_level,
            reasoning=reasoning,
            findings=findings,
            recommendations=self._get_recommendations(flags),
            timestamp=datetime.now(),
        )
    
    def _generate_reasoning(self, analysis: CheckAnalysisResult, flags: list) -> str:
        """Generate human-readable reasoning for the verdict."""
        parts = ["Physical Check Analysis Summary:"]
        
        wm = analysis["watermark_analysis"]
        if wm["detected"]:
            parts.append(f"✓ Watermark detected ({wm['confidence']:.1%} confidence)")
        else:
            parts.append("✗ Watermark NOT detected - critical security concern")
        
        sig = analysis["signature_analysis"]
        if sig["present"] and sig["valid"]:
            parts.append(f"✓ Signature valid ({sig['confidence']:.1%} confidence)")
        elif sig["present"]:
            parts.append("⚠ Signature present but validation concerns")
        else:
            parts.append("✗ Signature MISSING - check cannot be processed")
        
        micr = analysis["micr_validation"]
        if micr["valid"]:
            parts.append("✓ MICR line valid")
        else:
            parts.append(f"✗ MICR validation failed: {', '.join(micr['anomalies'][:2])}")
        
        img = analysis["image_quality"]
        parts.append(f"Image quality: {img['score']:.1%}")
        
        if flags:
            parts.append(f"\nFlags raised: {', '.join(flags)}")
        
        parts.append(f"\nOverall physical risk score: {analysis['overall_physical_risk']:.1%}")
        
        return "\n".join(parts)
    
    def _get_recommendations(self, flags: list) -> list:
        """Get recommendations based on flags."""
        recommendations = []
        
        if "missing_signature" in flags:
            recommendations.append("REJECT: Check must be signed")
        if "missing_watermark" in flags:
            recommendations.append("REJECT: Missing watermark indicates potential counterfeit")
        if "invalid_micr" in flags:
            recommendations.append("VERIFY: Contact issuing bank to verify account")
        if "manipulation_suspected" in flags:
            recommendations.append("ESCALATE: Forensic analysis required")
        if "low_image_quality" in flags:
            recommendations.append("REQUEST: Higher quality image needed")
        if "forgery_indicators" in flags:
            recommendations.append("REVIEW: Compare with reference signatures on file")
        
        if not recommendations:
            recommendations.append("APPROVE: Physical verification passed")
        
        return recommendations
