"""Sample data for the check fraud detection system."""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import random

from .models import (
    Client,
    Check,
    Transaction,
    FraudPolicy,
    SignatureReference,
    RiskLevel,
)


def create_sample_clients() -> Dict[str, Client]:
    """Create sample client data."""
    clients = {
        "CLIENT001": Client(
            client_id="CLIENT001",
            name="John Smith",
            account_number="1234567890",
            bank_name="First National Bank",
            address="123 Main Street, Springfield, IL 62701",
            phone="555-123-4567",
            email="john.smith@email.com",
            account_opened_date=datetime(2018, 3, 15),
            average_monthly_transactions=8.5,
            average_check_amount=450.00,
            typical_payees=["Electric Company", "Water Utility", "ABC Grocery", "City Rent LLC"],
            risk_score=0.15,
        ),
        "CLIENT002": Client(
            client_id="CLIENT002",
            name="Jane Doe",
            account_number="0987654321",
            bank_name="First National Bank",
            address="456 Oak Avenue, Springfield, IL 62702",
            phone="555-987-6543",
            email="jane.doe@email.com",
            account_opened_date=datetime(2020, 7, 22),
            average_monthly_transactions=5.2,
            average_check_amount=280.00,
            typical_payees=["Gas Company", "Insurance Co", "Local Market"],
            risk_score=0.10,
        ),
        "CLIENT003": Client(
            client_id="CLIENT003",
            name="Robert Johnson",
            account_number="5555666677",
            bank_name="First National Bank",
            address="789 Pine Road, Springfield, IL 62703",
            phone="555-456-7890",
            email="r.johnson@email.com",
            account_opened_date=datetime(2022, 1, 10),
            average_monthly_transactions=3.0,
            average_check_amount=150.00,
            typical_payees=["Phone Company", "Internet Provider"],
            risk_score=0.25,
        ),
        "CLIENT004": Client(
            client_id="CLIENT004",
            name="Suspicious Corp",
            account_number="9999888877",
            bank_name="First National Bank",
            address="999 Shadow Lane, Springfield, IL 62704",
            phone="555-000-0000",
            email="contact@suspicious.com",
            account_opened_date=datetime(2023, 11, 1),
            average_monthly_transactions=1.0,
            average_check_amount=50.00,
            typical_payees=[],
            risk_score=0.75,
        ),
    }
    return clients


def create_sample_transactions(clients: Dict[str, Client]) -> List[Transaction]:
    """Create sample transaction history."""
    transactions = []
    base_date = datetime.now() - timedelta(days=365)
    
    transaction_templates = {
        "CLIENT001": [
            ("Electric Company", 125.50, "utility"),
            ("Water Utility", 45.00, "utility"),
            ("ABC Grocery", 89.99, "retail"),
            ("City Rent LLC", 1200.00, "rent"),
            ("Gas Station Plus", 55.00, "fuel"),
        ],
        "CLIENT002": [
            ("Gas Company", 78.50, "utility"),
            ("Insurance Co", 150.00, "insurance"),
            ("Local Market", 65.00, "retail"),
            ("Phone Bill", 85.00, "utility"),
        ],
        "CLIENT003": [
            ("Phone Company", 95.00, "utility"),
            ("Internet Provider", 79.99, "utility"),
            ("Coffee Shop", 25.00, "retail"),
        ],
        "CLIENT004": [
            ("Unknown Vendor", 50.00, "unknown"),
        ],
    }
    
    tx_id = 1000
    for client_id, templates in transaction_templates.items():
        for month in range(12):
            for payee, base_amount, tx_type in templates:
                amount = base_amount * (1 + random.uniform(-0.1, 0.1))
                tx_date = base_date + timedelta(days=month * 30 + random.randint(0, 28))
                
                transactions.append(Transaction(
                    transaction_id=f"TX{tx_id:06d}",
                    client_id=client_id,
                    check_id=f"CHK{tx_id:06d}",
                    date=tx_date,
                    amount=round(amount, 2),
                    payee=payee,
                    transaction_type=tx_type,
                    status="completed",
                    location="Springfield, IL",
                ))
                tx_id += 1
    
    return transactions


def create_sample_checks() -> Tuple[List[Check], List[Check]]:
    """Create sample checks - legitimate and potentially fraudulent."""
    downloaded_sample_image = "sample_checks/downloaded/sample_cheque.jpeg"
    
    legitimate_checks = [
        Check(
            check_id="CHECK001",
            check_number="1001",
            client_id="CLIENT001",
            date=datetime.now() - timedelta(days=5),
            amount=125.50,
            amount_written="One hundred twenty-five and 50/100",
            payee="Electric Company",
            memo="Monthly electric bill",
            bank_name="First National Bank",
            routing_number="071000013",
            account_number="1234567890",
            image_path=downloaded_sample_image,
            micr_line="⑆071000013⑆ ⑈1234567890⑈ 1001",
            has_watermark=True,
            signature_present=True,
            metadata={"source": "branch_deposit", "teller_id": "T001"},
        ),
        Check(
            check_id="CHECK002",
            check_number="1002",
            client_id="CLIENT001",
            date=datetime.now() - timedelta(days=3),
            amount=450.00,
            amount_written="Four hundred fifty and 00/100",
            payee="City Rent LLC",
            memo="December rent",
            bank_name="First National Bank",
            routing_number="071000013",
            account_number="1234567890",
            image_path="sample_checks/legitimate_check_002.png",
            micr_line="⑆071000013⑆ ⑈1234567890⑈ 1002",
            has_watermark=True,
            signature_present=True,
            metadata={"source": "mobile_deposit", "device": "iPhone"},
        ),
        Check(
            check_id="CHECK003",
            check_number="2001",
            client_id="CLIENT002",
            date=datetime.now() - timedelta(days=7),
            amount=150.00,
            amount_written="One hundred fifty and 00/100",
            payee="Insurance Co",
            memo="Auto insurance premium",
            bank_name="First National Bank",
            routing_number="071000013",
            account_number="0987654321",
            image_path="sample_checks/legitimate_check_003.png",
            micr_line="⑆071000013⑆ ⑈0987654321⑈ 2001",
            has_watermark=True,
            signature_present=True,
            metadata={"source": "mail_deposit"},
        ),
    ]
    
    fraudulent_checks = [
        Check(
            check_id="CHECK_FRAUD001",
            check_number="1099",
            client_id="CLIENT001",
            date=datetime.now() - timedelta(days=1),
            amount=9500.00,
            amount_written="Nine thousand five hundred and 00/100",
            payee="Cash",
            memo="",
            bank_name="First National Bank",
            routing_number="071000013",
            account_number="1234567890",
            image_path=downloaded_sample_image,
            micr_line="⑆071000013⑆ ⑈1234567890⑈ 1099",
            has_watermark=False,
            signature_present=True,
            metadata={
                "source": "mobile_deposit",
                "device": "Unknown Android",
                "flags": ["amount_anomaly", "missing_watermark", "unusual_payee"],
            },
        ),
        Check(
            check_id="CHECK_FRAUD002",
            check_number="1003",
            client_id="CLIENT001",
            date=datetime.now(),
            amount=2500.00,
            amount_written="Two thousand five hundred and 00/100",
            payee="John Smith",
            memo="Self",
            bank_name="First National Bank",
            routing_number="071000013",
            account_number="1234567890",
            image_path="sample_checks/suspicious_check_002.png",
            micr_line="⑆071000013⑆ ⑈1234567890⑈ 1003",
            has_watermark=True,
            signature_present=False,
            metadata={
                "source": "atm_deposit",
                "flags": ["missing_signature", "self_payee", "amount_anomaly"],
            },
        ),
        Check(
            check_id="CHECK_FRAUD003",
            check_number="5001",
            client_id="CLIENT003",
            date=datetime.now() - timedelta(days=2),
            amount=15000.00,
            amount_written="Fifteen thousand and 00/100",
            payee="Overseas Trading LLC",
            memo="Investment",
            bank_name="First National Bank",
            routing_number="071000013",
            account_number="5555666677",
            image_path="sample_checks/suspicious_check_003.png",
            micr_line="⑆071000013⑆ ⑈5555666677⑈ 5001",
            has_watermark=True,
            signature_present=True,
            metadata={
                "source": "mobile_deposit",
                "device": "Rooted Android",
                "flags": ["extreme_amount_anomaly", "unknown_payee", "new_account"],
            },
        ),
        Check(
            check_id="CHECK_FRAUD004",
            check_number="9001",
            client_id="CLIENT004",
            date=datetime.now(),
            amount=8750.00,
            amount_written="Eight thousand seven hundred fifty and 00/100",
            payee="Quick Cash Services",
            memo="",
            bank_name="First National Bank",
            routing_number="071000013",
            account_number="9999888877",
            image_path="sample_checks/suspicious_check_004.png",
            micr_line="⑆071000013⑆ ⑈9999888877⑈ 9001",
            has_watermark=False,
            signature_present=True,
            metadata={
                "source": "mobile_deposit",
                "device": "Emulator",
                "flags": [
                    "missing_watermark",
                    "high_risk_client",
                    "suspicious_payee",
                    "amount_anomaly",
                    "emulator_detected",
                ],
            },
        ),
        Check(
            check_id="CHECK_FRAUD005",
            check_number="1004",
            client_id="CLIENT001",
            date=datetime.now() - timedelta(hours=2),
            amount=500.00,
            amount_written="Five hundred and 00/100 DOLLARS",
            payee="ABC Grocery",
            memo="groceries",
            bank_name="First National Bank",
            routing_number="071000013",
            account_number="1234567890",
            image_path="sample_checks/suspicious_check_005.png",
            micr_line="⑆071000013⑆ ⑈1234567890⑈ 1004",
            has_watermark=True,
            signature_present=True,
            metadata={
                "source": "mobile_deposit",
                "flags": ["duplicate_check_number_pattern", "altered_amount_suspected"],
                "image_quality_score": 0.45,
            },
        ),
    ]
    
    return legitimate_checks, fraudulent_checks


def create_fraud_policies() -> List[FraudPolicy]:
    """Create sample fraud detection policies."""
    policies = [
        FraudPolicy(
            policy_id="POL001",
            name="High Amount Threshold",
            description="Flag checks exceeding client's typical transaction amount by more than 500%",
            category="amount_analysis",
            rule_type="threshold",
            conditions={
                "field": "amount",
                "operator": "exceeds_average_by_percent",
                "threshold": 500,
            },
            action="flag_for_review",
            severity=RiskLevel.HIGH,
        ),
        FraudPolicy(
            policy_id="POL002",
            name="Missing Watermark Detection",
            description="Flag checks without proper bank watermark",
            category="physical_verification",
            rule_type="boolean",
            conditions={
                "field": "has_watermark",
                "operator": "equals",
                "value": False,
            },
            action="flag_as_suspicious",
            severity=RiskLevel.CRITICAL,
        ),
        FraudPolicy(
            policy_id="POL003",
            name="Missing Signature",
            description="Flag checks without a valid signature",
            category="physical_verification",
            rule_type="boolean",
            conditions={
                "field": "signature_present",
                "operator": "equals",
                "value": False,
            },
            action="reject",
            severity=RiskLevel.CRITICAL,
        ),
        FraudPolicy(
            policy_id="POL004",
            name="Cash Payee Alert",
            description="Flag checks made payable to 'Cash'",
            category="payee_analysis",
            rule_type="pattern",
            conditions={
                "field": "payee",
                "operator": "matches",
                "pattern": "^(cash|bearer)$",
                "case_insensitive": True,
            },
            action="flag_for_review",
            severity=RiskLevel.HIGH,
        ),
        FraudPolicy(
            policy_id="POL005",
            name="New Account Large Transaction",
            description="Flag large transactions from accounts less than 90 days old",
            category="account_analysis",
            rule_type="compound",
            conditions={
                "all": [
                    {"field": "account_age_days", "operator": "less_than", "value": 90},
                    {"field": "amount", "operator": "greater_than", "value": 5000},
                ]
            },
            action="flag_for_review",
            severity=RiskLevel.HIGH,
        ),
        FraudPolicy(
            policy_id="POL006",
            name="Unusual Payee Detection",
            description="Flag checks to payees not in client's typical payee list",
            category="payee_analysis",
            rule_type="list_check",
            conditions={
                "field": "payee",
                "operator": "not_in",
                "reference": "client.typical_payees",
            },
            action="flag_for_review",
            severity=RiskLevel.MEDIUM,
        ),
        FraudPolicy(
            policy_id="POL007",
            name="Self-Payee Check",
            description="Flag checks where payee matches account holder name",
            category="payee_analysis",
            rule_type="comparison",
            conditions={
                "field": "payee",
                "operator": "equals",
                "reference": "client.name",
            },
            action="flag_for_review",
            severity=RiskLevel.MEDIUM,
        ),
        FraudPolicy(
            policy_id="POL008",
            name="Rapid Succession Deposits",
            description="Flag multiple check deposits within 24 hours",
            category="velocity_analysis",
            rule_type="velocity",
            conditions={
                "event": "check_deposit",
                "time_window_hours": 24,
                "max_count": 3,
            },
            action="flag_for_review",
            severity=RiskLevel.MEDIUM,
        ),
        FraudPolicy(
            policy_id="POL009",
            name="Round Amount Suspicion",
            description="Flag large round-number amounts (potential structuring)",
            category="amount_analysis",
            rule_type="compound",
            conditions={
                "all": [
                    {"field": "amount", "operator": "greater_than", "value": 1000},
                    {"field": "amount", "operator": "is_round_number", "precision": 100},
                ]
            },
            action="flag_for_review",
            severity=RiskLevel.LOW,
        ),
        FraudPolicy(
            policy_id="POL010",
            name="Mobile Deposit Image Quality",
            description="Flag mobile deposits with low image quality scores",
            category="image_analysis",
            rule_type="threshold",
            conditions={
                "field": "metadata.image_quality_score",
                "operator": "less_than",
                "threshold": 0.6,
            },
            action="flag_for_review",
            severity=RiskLevel.MEDIUM,
        ),
        FraudPolicy(
            policy_id="POL011",
            name="Emulator Detection",
            description="Reject deposits from detected emulator devices",
            category="device_analysis",
            rule_type="pattern",
            conditions={
                "field": "metadata.device",
                "operator": "matches",
                "pattern": "(emulator|rooted|jailbroken)",
                "case_insensitive": True,
            },
            action="reject",
            severity=RiskLevel.CRITICAL,
        ),
        FraudPolicy(
            policy_id="POL012",
            name="Amount Mismatch Detection",
            description="Flag checks where numeric and written amounts may not match",
            category="amount_analysis",
            rule_type="validation",
            conditions={
                "fields": ["amount", "amount_written"],
                "operator": "must_match",
            },
            action="flag_for_review",
            severity=RiskLevel.HIGH,
        ),
    ]
    return policies


def create_signature_references() -> List[SignatureReference]:
    """Create sample signature references."""
    references = [
        SignatureReference(
            signature_id="SIG001",
            client_id="CLIENT001",
            signature_image_path="signatures/client001_primary.png",
            created_date=datetime(2018, 3, 15),
            is_primary=True,
            confidence_threshold=0.85,
        ),
        SignatureReference(
            signature_id="SIG002",
            client_id="CLIENT001",
            signature_image_path="signatures/client001_secondary.png",
            created_date=datetime(2020, 6, 10),
            is_primary=False,
            confidence_threshold=0.80,
        ),
        SignatureReference(
            signature_id="SIG003",
            client_id="CLIENT002",
            signature_image_path="signatures/client002_primary.png",
            created_date=datetime(2020, 7, 22),
            is_primary=True,
            confidence_threshold=0.85,
        ),
        SignatureReference(
            signature_id="SIG004",
            client_id="CLIENT003",
            signature_image_path="signatures/client003_primary.png",
            created_date=datetime(2022, 1, 10),
            is_primary=True,
            confidence_threshold=0.85,
        ),
    ]
    return references


def initialize_sample_data() -> dict:
    """Initialize all sample data and return as a dictionary."""
    clients = create_sample_clients()
    transactions = create_sample_transactions(clients)
    legitimate_checks, fraudulent_checks = create_sample_checks()
    policies = create_fraud_policies()
    signatures = create_signature_references()
    
    return {
        "clients": clients,
        "transactions": transactions,
        "legitimate_checks": legitimate_checks,
        "fraudulent_checks": fraudulent_checks,
        "all_checks": legitimate_checks + fraudulent_checks,
        "policies": policies,
        "signatures": signatures,
    }
