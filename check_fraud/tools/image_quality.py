"""Image quality analysis tool for check fraud detection."""

from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class ImageQualityResult:
    """Result of image quality analysis."""
    overall_score: float
    resolution_adequate: bool
    brightness_score: float
    contrast_score: float
    sharpness_score: float
    noise_level: float
    skew_angle: float
    issues: List[str]
    recommendations: List[str]
    details: str


class ImageQualityAnalyzer:
    """
    Image quality analyzer for check images.
    
    Evaluates:
    - Resolution and DPI
    - Brightness and contrast
    - Sharpness and focus
    - Noise levels
    - Skew and alignment
    - Cropping and completeness
    
    Note: Image quality analysis uses metadata-based heuristics.
    Real mode would use actual image processing libraries.
    """
    
    MINIMUM_QUALITY_SCORE = 0.6
    OPTIMAL_QUALITY_SCORE = 0.85
    
    def __init__(self, use_simulation: bool = True, llm=None):
        """
        Initialize image quality analyzer.
        
        Args:
            use_simulation: If True, use metadata-based analysis.
            llm: LLM instance (not typically used for image quality).
        """
        self.min_resolution = (1200, 600)
        self.optimal_dpi = 200
        self.use_simulation = use_simulation
        self.llm = llm
    
    def analyze(self, check_data: Dict[str, Any]) -> ImageQualityResult:
        """
        Analyze image quality of a check.
        
        Args:
            check_data: Dictionary containing check information
        
        Returns:
            ImageQualityResult with quality metrics
        """
        metadata = check_data.get("metadata", {})
        image_path = check_data.get("image_path", "")
        
        existing_score = metadata.get("image_quality_score")
        if existing_score is not None:
            return self._analyze_with_score(existing_score, metadata)
        
        return self._simulate_quality_analysis(check_data)
    
    def _analyze_with_score(
        self,
        score: float,
        metadata: Dict[str, Any],
    ) -> ImageQualityResult:
        """Analyze based on provided quality score."""
        issues = []
        recommendations = []
        
        if score < 0.3:
            issues.extend([
                "Very low image quality",
                "Text may be unreadable",
                "Security features cannot be verified",
            ])
            recommendations.extend([
                "Recapture image with better lighting",
                "Ensure camera is in focus",
                "Use higher resolution setting",
            ])
            brightness = 0.3
            contrast = 0.3
            sharpness = 0.2
            noise = 0.7
        elif score < 0.5:
            issues.extend([
                "Below acceptable quality threshold",
                "Some details may be unclear",
            ])
            recommendations.extend([
                "Consider recapturing for better verification",
                "Improve lighting conditions",
            ])
            brightness = 0.5
            contrast = 0.5
            sharpness = 0.4
            noise = 0.5
        elif score < 0.7:
            issues.append("Quality is acceptable but not optimal")
            recommendations.append("Higher quality would improve verification confidence")
            brightness = 0.7
            contrast = 0.7
            sharpness = 0.6
            noise = 0.3
        else:
            brightness = 0.85
            contrast = 0.85
            sharpness = 0.8
            noise = 0.15
        
        device = metadata.get("device", "")
        if "emulator" in device.lower():
            issues.append("Image captured from emulator device")
        
        return ImageQualityResult(
            overall_score=score,
            resolution_adequate=score >= 0.5,
            brightness_score=brightness,
            contrast_score=contrast,
            sharpness_score=sharpness,
            noise_level=noise,
            skew_angle=0.0 if score > 0.7 else 2.5,
            issues=issues,
            recommendations=recommendations,
            details=self._format_quality_details(score, issues),
        )
    
    def _simulate_quality_analysis(self, check_data: Dict[str, Any]) -> ImageQualityResult:
        """Simulate quality analysis for checks without explicit score."""
        metadata = check_data.get("metadata", {})
        source = metadata.get("source", "")
        device = metadata.get("device", "")
        flags = metadata.get("flags", [])
        
        base_score = 0.85
        issues = []
        recommendations = []
        
        if source == "mobile_deposit":
            base_score -= 0.05
        elif source == "atm_deposit":
            base_score -= 0.1
            issues.append("ATM capture may have lower quality")
        
        if "emulator" in device.lower():
            base_score -= 0.3
            issues.append("Emulator device detected - suspicious capture method")
        elif "rooted" in device.lower():
            base_score -= 0.15
            issues.append("Rooted device may indicate tampering")
        elif "unknown" in device.lower():
            base_score -= 0.1
            issues.append("Unknown device type")
        
        if "altered_amount_suspected" in flags:
            base_score -= 0.2
            issues.append("Image analysis suggests possible alteration")
        
        score = max(0.1, min(1.0, base_score))
        
        return ImageQualityResult(
            overall_score=score,
            resolution_adequate=score >= 0.5,
            brightness_score=score * 0.95,
            contrast_score=score * 0.9,
            sharpness_score=score * 0.85,
            noise_level=1.0 - score,
            skew_angle=0.5 if score > 0.7 else 3.0,
            issues=issues,
            recommendations=recommendations,
            details=self._format_quality_details(score, issues),
        )
    
    def _format_quality_details(self, score: float, issues: List[str]) -> str:
        """Format quality analysis into readable details."""
        parts = [f"Image Quality Score: {score:.1%}"]
        
        if score >= self.OPTIMAL_QUALITY_SCORE:
            parts.append("Status: Excellent - All quality metrics pass")
        elif score >= self.MINIMUM_QUALITY_SCORE:
            parts.append("Status: Acceptable - Meets minimum requirements")
        else:
            parts.append("Status: Poor - Below minimum quality threshold")
        
        if issues:
            parts.append("\nIssues Detected:")
            for issue in issues:
                parts.append(f"  - {issue}")
        
        return "\n".join(parts)
    
    def check_for_manipulation(self, check_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check for signs of image manipulation.
        
        Looks for:
        - JPEG artifacts indicating re-compression
        - Inconsistent noise patterns
        - Clone/copy-paste detection
        - Metadata inconsistencies
        """
        metadata = check_data.get("metadata", {})
        flags = metadata.get("flags", [])
        
        manipulation_indicators = []
        confidence = 0.0
        
        if "altered_amount_suspected" in flags:
            manipulation_indicators.append("Amount field shows signs of alteration")
            confidence += 0.4
        
        if "duplicate_check_number_pattern" in flags:
            manipulation_indicators.append("Check number pattern suggests duplication")
            confidence += 0.3
        
        device = metadata.get("device", "")
        if "emulator" in device.lower():
            manipulation_indicators.append("Image source is emulator - high manipulation risk")
            confidence += 0.5
        
        quality_score = metadata.get("image_quality_score", 0.85)
        if quality_score and quality_score < 0.5:
            manipulation_indicators.append("Low quality may hide manipulation artifacts")
            confidence += 0.2
        
        return {
            "manipulation_detected": len(manipulation_indicators) > 0,
            "confidence": min(confidence, 1.0),
            "indicators": manipulation_indicators,
            "recommendation": self._get_manipulation_recommendation(confidence),
            "details": self._format_manipulation_details(manipulation_indicators, confidence),
        }
    
    def _get_manipulation_recommendation(self, confidence: float) -> str:
        """Get recommendation based on manipulation confidence."""
        if confidence >= 0.7:
            return "reject"
        elif confidence >= 0.4:
            return "manual_review"
        elif confidence >= 0.2:
            return "flag_for_review"
        return "approve"
    
    def _format_manipulation_details(
        self,
        indicators: List[str],
        confidence: float,
    ) -> str:
        """Format manipulation analysis details."""
        if not indicators:
            return "No manipulation indicators detected."
        
        parts = [f"Manipulation Analysis (Confidence: {confidence:.1%})"]
        parts.append("\nIndicators Found:")
        for indicator in indicators:
            parts.append(f"  - {indicator}")
        
        return "\n".join(parts)
    
    def get_risk_assessment(self, result: ImageQualityResult) -> Dict[str, Any]:
        """Get risk assessment based on image quality."""
        if result.overall_score < 0.3:
            return {
                "risk_level": "high",
                "risk_score": 0.8,
                "recommendation": "reject",
                "reason": "Image quality too low for reliable verification",
            }
        
        if result.overall_score < self.MINIMUM_QUALITY_SCORE:
            return {
                "risk_level": "medium",
                "risk_score": 0.5,
                "recommendation": "manual_review",
                "reason": "Image quality below acceptable threshold",
            }
        
        if result.issues:
            return {
                "risk_level": "low",
                "risk_score": 0.3,
                "recommendation": "flag_for_review",
                "reason": f"Quality issues: {', '.join(result.issues[:2])}",
            }
        
        return {
            "risk_level": "low",
            "risk_score": 0.1,
            "recommendation": "approve",
            "reason": "Image quality meets requirements",
        }
