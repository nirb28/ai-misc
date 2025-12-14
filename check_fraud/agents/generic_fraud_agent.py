"""Generic Fraud Analysis Agent - Advanced LLM-based fraud detection."""

from typing import Dict, Any, Optional
from datetime import datetime
import os
import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_groq import ChatGroq

from database.models import AgentVerdict, FraudVerdict, RiskLevel
from graph.state import FraudDetectionState
from config import get_analysis_config, LLMConfig


GENERIC_FRAUD_ANALYSIS_PROMPT = """You are an expert fraud analyst specializing in check fraud detection. You have extensive experience in identifying fraudulent checks through pattern recognition, behavioral analysis, and holistic assessment of multiple risk factors.

Your task is to analyze the following check and all available evidence to determine if this check is likely fraudulent.

## Check Information
{check_info}

## Client Information
{client_info}

## Physical Check Analysis Results
{check_analysis}

## Transaction History Analysis
{transaction_analysis}

## Policy Violation Summary
{policy_analysis}

## Analysis Instructions

Consider ALL of the following factors in your analysis:

1. **Physical Integrity**: Watermark, signature, MICR line, image quality
2. **Behavioral Patterns**: Does this transaction fit the client's historical behavior?
3. **Amount Analysis**: Is the amount unusual for this client?
4. **Payee Analysis**: Is the payee known, suspicious, or unusual?
5. **Timing & Velocity**: Are there unusual patterns in timing or frequency?
6. **Device/Source**: Was the check deposited through a suspicious channel?
7. **Policy Compliance**: What policies were violated and how severe?
8. **Holistic Assessment**: What does the combination of all factors suggest?

## Red Flags to Consider
- Missing or invalid security features (watermark, signature)
- Amount significantly exceeding historical patterns
- Unknown or suspicious payees (especially "Cash", "Bearer", overseas entities)
- New accounts with large transactions
- Multiple deposits in short time periods
- Deposits from emulators or rooted devices
- Mismatched information (MICR vs stated account)
- Signs of document alteration

## Response Format

Provide your analysis in the following JSON format:
{{
    "verdict": "fraud" | "not_fraud" | "review",
    "confidence": <float between 0.0 and 1.0>,
    "risk_level": "low" | "medium" | "high" | "critical",
    "key_findings": [
        "<finding 1>",
        "<finding 2>",
        ...
    ],
    "risk_factors": [
        {{
            "factor": "<factor name>",
            "severity": "low" | "medium" | "high" | "critical",
            "details": "<explanation>"
        }},
        ...
    ],
    "reasoning": "<detailed explanation of your verdict>",
    "recommendations": [
        "<recommendation 1>",
        "<recommendation 2>",
        ...
    ]
}}

Be thorough but decisive. If there are multiple serious red flags, lean toward fraud. If the check appears legitimate with minor concerns, lean toward not_fraud but note the concerns. Use "review" when evidence is mixed and human judgment is needed.
"""


class GenericFraudAgent:
    """
    Advanced LLM-based fraud detection agent.
    
    Uses a sophisticated prompt to analyze all available evidence
    and provide a holistic fraud assessment.
    """
    
    AGENT_NAME = "generic_fraud_agent"
    
    def __init__(
        self, 
        llm_provider: Optional[str] = None, 
        model: Optional[str] = None,
        llm_config: Optional[LLMConfig] = None,
    ):
        """
        Initialize the generic fraud agent.
        
        Args:
            llm_provider: LLM provider ("groq", "openai", "azure"). If None, uses config.
            model: Model name. If None, uses config or provider default.
            llm_config: Optional LLMConfig object. If provided, overrides other params.
        """
        if llm_config:
            self.llm_config = llm_config
        else:
            config = get_analysis_config()
            self.llm_config = LLMConfig(
                provider=llm_provider or config.llm_config.provider,
                model=model or config.llm_config.model,
                api_key=config.llm_config.api_key,
                azure_endpoint=config.llm_config.azure_endpoint,
                azure_api_version=config.llm_config.azure_api_version,
                azure_deployment=config.llm_config.azure_deployment,
            )
        
        self.llm = self._initialize_llm()
        self.prompt = ChatPromptTemplate.from_template(GENERIC_FRAUD_ANALYSIS_PROMPT)
        self.parser = JsonOutputParser()
    
    def _initialize_llm(self):
        """Initialize the LLM based on provider."""
        provider = self.llm_config.provider
        
        if provider == "groq":
            model = self.llm_config.model or "llama-3.3-70b-versatile"
            api_key = self.llm_config.api_key or os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY environment variable not set")
            return ChatGroq(
                model=model,
                temperature=self.llm_config.temperature,
                api_key=api_key,
            )
        elif provider == "openai":
            model = self.llm_config.model or "gpt-4o"
            api_key = self.llm_config.api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            return ChatOpenAI(
                model=model,
                temperature=self.llm_config.temperature,
                api_key=api_key,
            )
        elif provider == "azure":
            api_key = self.llm_config.api_key or os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = self.llm_config.azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
            deployment = self.llm_config.azure_deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT")
            api_version = self.llm_config.azure_api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            
            if not api_key:
                raise ValueError("AZURE_OPENAI_API_KEY environment variable not set")
            if not endpoint:
                raise ValueError("AZURE_OPENAI_ENDPOINT environment variable not set")
            if not deployment:
                raise ValueError("AZURE_OPENAI_DEPLOYMENT environment variable not set")
            
            azure_kwargs: Dict[str, Any] = {
                "azure_deployment": deployment,
                "azure_endpoint": endpoint,
                "api_key": api_key,
                "api_version": api_version,
            }
            # Some Azure deployments (e.g. gpt-5-nano) reject non-default temperatures.
            # Only send temperature when it's explicitly the default (1.0) to avoid 400s.
            if self.llm_config.temperature is not None and float(self.llm_config.temperature) == 1.0:
                azure_kwargs["temperature"] = float(self.llm_config.temperature)

            return AzureChatOpenAI(**azure_kwargs)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    def analyze(self, state: FraudDetectionState) -> Dict[str, Any]:
        """
        Perform advanced LLM-based fraud analysis.
        
        Args:
            state: Current workflow state with all previous analysis results
        
        Returns:
            Updated state with generic fraud analysis results
        """
        check_info = self._format_check_info(state["check"])
        client_info = self._format_client_info(state.get("client"))
        check_analysis = self._format_check_analysis(state.get("check_analysis"))
        transaction_analysis = self._format_transaction_analysis(state.get("transaction_analysis"))
        policy_analysis = self._format_policy_analysis(state.get("policy_analysis"))
        
        chain = self.prompt | self.llm | self.parser
        
        try:
            result = chain.invoke({
                "check_info": check_info,
                "client_info": client_info,
                "check_analysis": check_analysis,
                "transaction_analysis": transaction_analysis,
                "policy_analysis": policy_analysis,
            })
        except Exception as e:
            return self._handle_llm_error(str(e), state)
        
        verdict = self._create_verdict(result)
        
        return {
            "generic_analysis": result,
            "agent_verdicts": [verdict],
            "all_findings": result.get("key_findings", []),
            "all_recommendations": result.get("recommendations", []),
            "current_step": "generic_analysis_complete",
        }
    
    def _format_check_info(self, check) -> str:
        """Format check information for the prompt."""
        if hasattr(check, 'model_dump'):
            check_dict = check.model_dump()
        else:
            check_dict = dict(check)
        
        return f"""
- Check ID: {check_dict.get('check_id', 'N/A')}
- Check Number: {check_dict.get('check_number', 'N/A')}
- Date: {check_dict.get('date', 'N/A')}
- Amount: ${check_dict.get('amount', 0):,.2f}
- Amount Written: {check_dict.get('amount_written', 'N/A')}
- Payee: {check_dict.get('payee', 'N/A')}
- Memo: {check_dict.get('memo', 'N/A')}
- Bank: {check_dict.get('bank_name', 'N/A')}
- Routing Number: {check_dict.get('routing_number', 'N/A')}
- Account Number: {check_dict.get('account_number', 'N/A')[-4:] if check_dict.get('account_number') else 'N/A'} (last 4)
- Has Watermark: {check_dict.get('has_watermark', 'Unknown')}
- Signature Present: {check_dict.get('signature_present', 'Unknown')}
- Deposit Source: {check_dict.get('metadata', {}).get('source', 'Unknown')}
- Device: {check_dict.get('metadata', {}).get('device', 'Unknown')}
- Existing Flags: {check_dict.get('metadata', {}).get('flags', [])}
"""
    
    def _format_client_info(self, client) -> str:
        """Format client information for the prompt."""
        if not client:
            return "Client information not available."
        
        if hasattr(client, 'model_dump'):
            client_dict = client.model_dump()
        else:
            client_dict = dict(client)
        
        return f"""
- Client ID: {client_dict.get('client_id', 'N/A')}
- Name: {client_dict.get('name', 'N/A')}
- Account Opened: {client_dict.get('account_opened_date', 'N/A')}
- Average Monthly Transactions: {client_dict.get('average_monthly_transactions', 0):.1f}
- Average Check Amount: ${client_dict.get('average_check_amount', 0):,.2f}
- Typical Payees: {', '.join(client_dict.get('typical_payees', [])) or 'None recorded'}
- Client Risk Score: {client_dict.get('risk_score', 0):.2f}
"""
    
    def _format_check_analysis(self, analysis) -> str:
        """Format check analysis results for the prompt."""
        if not analysis:
            return "Physical check analysis not yet performed."
        
        parts = []
        
        wm = analysis.get("watermark_analysis", {})
        parts.append(f"**Watermark**: {'Detected' if wm.get('detected') else 'NOT DETECTED'} "
                    f"(Confidence: {wm.get('confidence', 0):.1%})")
        parts.append(f"  - Risk: {wm.get('risk', {}).get('risk_level', 'unknown')}")
        
        sig = analysis.get("signature_analysis", {})
        parts.append(f"**Signature**: {'Present' if sig.get('present') else 'MISSING'}, "
                    f"{'Valid' if sig.get('valid') else 'Invalid'}")
        parts.append(f"  - Confidence: {sig.get('confidence', 0):.1%}")
        parts.append(f"  - Forgery Indicators: {sig.get('forgery_indicators', [])}")
        
        micr = analysis.get("micr_validation", {})
        parts.append(f"**MICR Line**: {'Valid' if micr.get('valid') else 'INVALID'}")
        parts.append(f"  - Anomalies: {micr.get('anomalies', [])}")
        
        img = analysis.get("image_quality", {})
        parts.append(f"**Image Quality**: {img.get('score', 0):.1%}")
        parts.append(f"  - Manipulation Check: {img.get('manipulation_check', {})}")
        
        parts.append(f"\n**Overall Physical Risk**: {analysis.get('overall_physical_risk', 0):.1%}")
        parts.append(f"**Physical Flags**: {analysis.get('physical_flags', [])}")
        
        return "\n".join(parts)
    
    def _format_transaction_analysis(self, analysis) -> str:
        """Format transaction analysis results for the prompt."""
        if not analysis:
            return "Transaction history analysis not yet performed."
        
        parts = []
        
        parts.append(f"**Client Found**: {analysis.get('client_found', False)}")
        
        stats = analysis.get("transaction_statistics", {})
        if stats:
            parts.append(f"**Transaction Statistics**:")
            parts.append(f"  - Total Transactions: {stats.get('total_transactions', 0)}")
            parts.append(f"  - Average Amount: ${stats.get('average_amount', 0):,.2f}")
            parts.append(f"  - Max Amount: ${stats.get('max_amount', 0):,.2f}")
            parts.append(f"  - Transactions/Month: {stats.get('transactions_per_month', 0):.1f}")
        
        parts.append(f"**Amount Anomaly Score**: {analysis.get('amount_anomaly_score', 0):.1%}")
        
        payee = analysis.get("payee_analysis", {})
        parts.append(f"**Payee Analysis**:")
        parts.append(f"  - Known Payee: {payee.get('is_known', False)}")
        parts.append(f"  - Suspicious: {payee.get('is_suspicious', False)}")
        parts.append(f"  - Self-Payee: {payee.get('is_self_payee', False)}")
        
        velocity = analysis.get("velocity_analysis", {})
        parts.append(f"**Velocity**: {velocity.get('deposits_24h', 0)} deposits in 24h")
        
        parts.append(f"**Historical Flags**: {analysis.get('historical_flags', [])}")
        
        return "\n".join(parts)
    
    def _format_policy_analysis(self, analysis) -> str:
        """Format policy analysis results for the prompt."""
        if not analysis:
            return "Policy analysis not yet performed."
        
        parts = []
        
        parts.append(f"**Policies Evaluated**: {analysis.get('policies_evaluated', 0)}")
        parts.append(f"**Violations Found**: {analysis.get('violation_count', 0)}")
        parts.append(f"**Highest Severity**: {analysis.get('highest_severity', 'none')}")
        
        violations = analysis.get("violations", [])
        if violations:
            parts.append("\n**Violated Policies**:")
            for v in violations:
                parts.append(f"  - [{v.get('severity', {}).value if hasattr(v.get('severity'), 'value') else v.get('severity', 'unknown')}] "
                           f"{v.get('policy_name', 'Unknown')}: {v.get('details', '')}")
        
        parts.append(f"\n**Policy Flags**: {analysis.get('policy_flags', [])}")
        
        return "\n".join(parts)
    
    def _create_verdict(self, result: Dict[str, Any]) -> AgentVerdict:
        """Create AgentVerdict from LLM analysis result."""
        verdict_map = {
            "fraud": FraudVerdict.FRAUD,
            "not_fraud": FraudVerdict.NOT_FRAUD,
            "review": FraudVerdict.REVIEW,
        }
        
        risk_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
        }
        
        verdict = verdict_map.get(result.get("verdict", "review"), FraudVerdict.REVIEW)
        risk_level = risk_map.get(result.get("risk_level", "medium"), RiskLevel.MEDIUM)
        confidence = float(result.get("confidence", 0.5))
        
        risk_factors_text = ""
        if result.get("risk_factors"):
            risk_factors_text = "\n\nRisk Factors:\n" + "\n".join(
                f"- {rf.get('factor', 'Unknown')} ({rf.get('severity', 'unknown')}): {rf.get('details', '')}"
                for rf in result.get("risk_factors", [])
            )
        
        reasoning = result.get("reasoning", "Analysis completed.") + risk_factors_text
        
        return AgentVerdict(
            agent_name=self.AGENT_NAME,
            verdict=verdict,
            confidence=confidence,
            risk_level=risk_level,
            reasoning=reasoning,
            findings=result.get("key_findings", []),
            recommendations=result.get("recommendations", []),
            timestamp=datetime.now(),
        )
    
    def _handle_llm_error(self, error: str, state: FraudDetectionState) -> Dict[str, Any]:
        """Handle LLM errors gracefully."""
        verdict = AgentVerdict(
            agent_name=self.AGENT_NAME,
            verdict=FraudVerdict.REVIEW,
            confidence=0.3,
            risk_level=RiskLevel.MEDIUM,
            reasoning=f"LLM analysis failed: {error}. Manual review required.",
            findings=["LLM analysis could not be completed"],
            recommendations=["Manual review required due to analysis failure"],
            timestamp=datetime.now(),
        )
        
        return {
            "generic_analysis": {"error": error},
            "agent_verdicts": [verdict],
            "processing_errors": [f"GenericFraudAgent LLM error: {error}"],
            "current_step": "generic_analysis_error",
        }
