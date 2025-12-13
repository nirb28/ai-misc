"""Database models for the check fraud detection system."""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class FraudVerdict(str, Enum):
    """Possible fraud verdicts."""
    FRAUD = "fraud"
    NOT_FRAUD = "not_fraud"
    REVIEW = "review"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    """Risk level classifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Client(BaseModel):
    """Client/account holder information."""
    client_id: str
    name: str
    account_number: str
    bank_name: str
    address: str
    phone: Optional[str] = None
    email: Optional[str] = None
    account_opened_date: datetime
    average_monthly_transactions: float = 0.0
    average_check_amount: float = 0.0
    typical_payees: List[str] = Field(default_factory=list)
    risk_score: float = 0.0


class Check(BaseModel):
    """Check document information."""
    check_id: str
    check_number: str
    client_id: str
    date: datetime
    amount: float
    amount_written: str
    payee: str
    memo: Optional[str] = None
    bank_name: str
    routing_number: str
    account_number: str
    image_path: Optional[str] = None
    micr_line: Optional[str] = None
    has_watermark: bool = True
    signature_present: bool = True
    metadata: dict = Field(default_factory=dict)


class Transaction(BaseModel):
    """Historical transaction record."""
    transaction_id: str
    client_id: str
    check_id: Optional[str] = None
    date: datetime
    amount: float
    payee: str
    transaction_type: str = "check"
    status: str = "completed"
    location: Optional[str] = None
    notes: Optional[str] = None


class SignatureReference(BaseModel):
    """Reference signature for comparison."""
    signature_id: str
    client_id: str
    signature_image_path: str
    created_date: datetime
    is_primary: bool = True
    confidence_threshold: float = 0.85


class FraudPolicy(BaseModel):
    """Fraud detection policy rule."""
    policy_id: str
    name: str
    description: str
    category: str
    rule_type: str
    conditions: dict
    action: str
    severity: RiskLevel
    is_active: bool = True
    created_date: datetime = Field(default_factory=datetime.now)
    updated_date: datetime = Field(default_factory=datetime.now)


class AgentVerdict(BaseModel):
    """Individual agent's fraud assessment."""
    agent_name: str
    verdict: FraudVerdict
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    reasoning: str
    findings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class FraudAnalysisResult(BaseModel):
    """Complete fraud analysis result."""
    analysis_id: str
    check_id: str
    client_id: str
    agent_verdicts: List[AgentVerdict] = Field(default_factory=list)
    final_verdict: FraudVerdict = FraudVerdict.UNKNOWN
    final_confidence: float = 0.0
    final_risk_level: RiskLevel = RiskLevel.LOW
    consensus_reached: bool = False
    voting_summary: dict = Field(default_factory=dict)
    analysis_timestamp: datetime = Field(default_factory=datetime.now)
    processing_time_seconds: float = 0.0
    notes: Optional[str] = None
