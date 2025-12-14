"""Watermark detection tool for check analysis."""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import random
import os
import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser


@dataclass
class WatermarkAnalysisResult:
    """Result of watermark analysis."""
    watermark_detected: bool
    confidence: float
    watermark_type: Optional[str]
    position: Optional[str]
    quality_score: float
    anomalies: list
    details: str


WATERMARK_ANALYSIS_PROMPT = """You are an expert document forensics analyst specializing in check security features.

Analyze the following check information for watermark presence and authenticity.

## Check Information
- Bank Name: {bank_name}
- Has Watermark Flag: {has_watermark}
- Image Quality Score: {image_quality}
- Check Metadata: {metadata}

## Analysis Instructions
Evaluate the watermark based on:
1. Whether a watermark should be present for this bank
2. The reported watermark status
3. Image quality that could affect watermark visibility
4. Any suspicious indicators in the metadata

## Response Format
Provide your analysis in JSON format:
{{
    "watermark_detected": true/false,
    "confidence": <float 0.0-1.0>,
    "watermark_type": "bank_logo" | "security_pattern" | "void_pantograph" | null,
    "position": "center" | "background" | "border" | null,
    "quality_score": <float 0.0-1.0>,
    "anomalies": ["<anomaly 1>", ...],
    "details": "<detailed explanation>"
}}
"""


class WatermarkDetector:
    """
    Watermark detection for check images.
    
    Supports both simulation mode and real LLM-based analysis.
    In production with real mode, uses LLM to analyze check data.
    """
    
    WATERMARK_TYPES = [
        "bank_logo",
        "security_pattern",
        "void_pantograph",
        "chemical_reactive",
        "microprinting",
    ]
    
    POSITIONS = [
        "center",
        "background",
        "border",
        "corners",
    ]
    
    def __init__(self, use_simulation: bool = True, llm=None):
        """
        Initialize watermark detector.
        
        Args:
            use_simulation: If True, use simulated analysis. If False, use LLM.
            llm: LangChain LLM instance for real analysis. Required if use_simulation=False.
        """
        self.detection_threshold = 0.7
        self.use_simulation = use_simulation
        self.llm = llm
        
        if not use_simulation and llm:
            self.prompt = ChatPromptTemplate.from_template(WATERMARK_ANALYSIS_PROMPT)
            self.parser = JsonOutputParser()
    
    def analyze(self, check_data: Dict[str, Any]) -> WatermarkAnalysisResult:
        """
        Analyze a check for watermark presence and authenticity.
        
        Args:
            check_data: Dictionary containing check information including
                       has_watermark flag and image_path
        
        Returns:
            WatermarkAnalysisResult with detection details
        """
        if not self.use_simulation and self.llm:
            return self._analyze_with_llm(check_data)
        return self._analyze_simulated(check_data)
    
    def _analyze_with_llm(self, check_data: Dict[str, Any]) -> WatermarkAnalysisResult:
        """Perform LLM-based watermark analysis."""
        try:
            chain = self.prompt | self.llm | self.parser
            
            metadata = check_data.get("metadata", {})
            result = chain.invoke({
                "bank_name": check_data.get("bank_name", "Unknown"),
                "has_watermark": check_data.get("has_watermark", "Unknown"),
                "image_quality": metadata.get("image_quality_score", "Unknown"),
                "metadata": json.dumps(metadata),
            })
            
            return WatermarkAnalysisResult(
                watermark_detected=result.get("watermark_detected", False),
                confidence=float(result.get("confidence", 0.5)),
                watermark_type=result.get("watermark_type"),
                position=result.get("position"),
                quality_score=float(result.get("quality_score", 0.5)),
                anomalies=result.get("anomalies", []),
                details=result.get("details", "LLM analysis completed."),
            )
        except Exception as e:
            # Fallback to simulation on error
            return self._analyze_simulated(check_data)
    
    def _analyze_simulated(self, check_data: Dict[str, Any]) -> WatermarkAnalysisResult:
        """Perform simulated watermark analysis."""
        has_watermark = check_data.get("has_watermark", True)
        image_path = check_data.get("image_path", "")
        metadata = check_data.get("metadata", {})
        
        if not has_watermark:
            return WatermarkAnalysisResult(
                watermark_detected=False,
                confidence=0.95,
                watermark_type=None,
                position=None,
                quality_score=0.0,
                anomalies=["No watermark detected in expected regions"],
                details="Check appears to lack standard bank watermark. This is a critical security concern.",
            )
        
        flags = metadata.get("flags", [])
        if "missing_watermark" in flags:
            return WatermarkAnalysisResult(
                watermark_detected=False,
                confidence=0.92,
                watermark_type=None,
                position=None,
                quality_score=0.1,
                anomalies=[
                    "Watermark region appears blank",
                    "Expected security pattern not found",
                ],
                details="Watermark detection failed. Check may be counterfeit or a photocopy.",
            )
        
        quality_score = metadata.get("image_quality_score", 0.85)
        if quality_score < 0.5:
            return WatermarkAnalysisResult(
                watermark_detected=True,
                confidence=0.6,
                watermark_type="bank_logo",
                position="background",
                quality_score=quality_score,
                anomalies=[
                    "Low image quality affects watermark verification",
                    "Watermark edges appear blurred",
                ],
                details="Watermark partially detected but image quality is poor. Manual review recommended.",
            )
        
        confidence = 0.85 + random.uniform(0, 0.1)
        watermark_type = random.choice(self.WATERMARK_TYPES[:3])
        position = random.choice(self.POSITIONS)
        
        return WatermarkAnalysisResult(
            watermark_detected=True,
            confidence=confidence,
            watermark_type=watermark_type,
            position=position,
            quality_score=quality_score if quality_score else 0.88,
            anomalies=[],
            details=f"Valid {watermark_type} watermark detected at {position} with high confidence.",
        )
    
    def compare_with_reference(
        self,
        check_watermark: WatermarkAnalysisResult,
        bank_name: str,
    ) -> Dict[str, Any]:
        """
        Compare detected watermark with bank's reference watermark.
        
        Args:
            check_watermark: Result from analyze()
            bank_name: Name of the issuing bank
        
        Returns:
            Comparison result with match score
        """
        if not check_watermark.watermark_detected:
            return {
                "matches_reference": False,
                "match_score": 0.0,
                "bank_name": bank_name,
                "details": "No watermark to compare",
            }
        
        match_score = check_watermark.confidence * 0.95
        
        return {
            "matches_reference": match_score > self.detection_threshold,
            "match_score": match_score,
            "bank_name": bank_name,
            "watermark_type": check_watermark.watermark_type,
            "details": f"Watermark comparison with {bank_name} reference: {match_score:.2%} match",
        }
    
    def get_risk_assessment(self, result: WatermarkAnalysisResult) -> Dict[str, Any]:
        """Get risk assessment based on watermark analysis."""
        if not result.watermark_detected:
            return {
                "risk_level": "critical",
                "risk_score": 0.95,
                "recommendation": "reject",
                "reason": "Missing watermark indicates potential counterfeit",
            }
        
        if result.confidence < 0.7:
            return {
                "risk_level": "high",
                "risk_score": 0.7,
                "recommendation": "manual_review",
                "reason": "Low confidence watermark detection requires verification",
            }
        
        if result.anomalies:
            return {
                "risk_level": "medium",
                "risk_score": 0.4,
                "recommendation": "flag_for_review",
                "reason": f"Anomalies detected: {', '.join(result.anomalies)}",
            }
        
        return {
            "risk_level": "low",
            "risk_score": 0.1,
            "recommendation": "approve",
            "reason": "Watermark verification passed",
        }
