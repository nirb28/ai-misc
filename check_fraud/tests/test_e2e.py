"""End-to-end tests for the check fraud detection system."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import Check, Client, FraudVerdict, RiskLevel
from database.sample_data import initialize_sample_data
from database.transaction_db import TransactionDatabase
from database.policy_db import PolicyDatabase
from graph.workflow import run_fraud_detection_without_llm
from tools import WatermarkDetector, SignatureAnalyzer, MICRValidator, ImageQualityAnalyzer


@pytest.fixture
def sample_data():
    """Load sample data for tests."""
    return initialize_sample_data()


class TestEndToEndScenarios:
    """End-to-end test scenarios simulating real-world fraud cases."""
    
    def test_scenario_legitimate_utility_payment(self, sample_data):
        """
        Scenario: Regular customer pays monthly utility bill.
        Expected: NOT_FRAUD with LOW risk.
        """
        check = sample_data["legitimate_checks"][0]
        client = sample_data["clients"]["CLIENT001"]
        
        result = run_fraud_detection_without_llm(check, client)
        
        assert result.final_verdict == FraudVerdict.NOT_FRAUD
        assert result.final_risk_level == RiskLevel.LOW
        assert result.consensus_reached == True
        
        print(f"\n✅ Legitimate utility payment: {result.final_verdict.value}")
        print(f"   Confidence: {result.final_confidence:.1%}")
    
    def test_scenario_counterfeit_check_no_watermark(self, sample_data):
        """
        Scenario: Counterfeit check without bank watermark.
        Expected: FRAUD with CRITICAL risk.
        """
        check = sample_data["fraudulent_checks"][0]
        client = sample_data["clients"].get(check.client_id)
        
        result = run_fraud_detection_without_llm(check, client)
        
        assert result.final_verdict in [FraudVerdict.FRAUD, FraudVerdict.REVIEW]
        assert result.final_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        
        has_watermark_flag = any(
            "watermark" in str(v.findings).lower() or "watermark" in str(v.reasoning).lower()
            for v in result.agent_verdicts
        )
        assert has_watermark_flag
        
        print(f"\n🚨 Counterfeit check (no watermark): {result.final_verdict.value}")
        print(f"   Risk Level: {result.final_risk_level.value}")
    
    def test_scenario_forged_signature(self, sample_data):
        """
        Scenario: Check with missing/forged signature.
        Expected: FRAUD or REVIEW with HIGH/CRITICAL risk.
        """
        check = None
        for c in sample_data["fraudulent_checks"]:
            if not c.signature_present:
                check = c
                break
        
        if check is None:
            pytest.skip("No unsigned check in sample data")
        
        client = sample_data["clients"].get(check.client_id)
        result = run_fraud_detection_without_llm(check, client)
        
        assert result.final_verdict in [FraudVerdict.FRAUD, FraudVerdict.REVIEW]
        assert result.final_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        
        print(f"\n🚨 Forged/missing signature: {result.final_verdict.value}")
        print(f"   Risk Level: {result.final_risk_level.value}")
    
    def test_scenario_account_takeover_unusual_amount(self, sample_data):
        """
        Scenario: Account takeover - check amount far exceeds normal pattern.
        Expected: FRAUD or REVIEW due to amount anomaly.
        """
        check = sample_data["fraudulent_checks"][2]
        client = sample_data["clients"].get(check.client_id)
        
        result = run_fraud_detection_without_llm(check, client)
        
        assert result.final_verdict in [FraudVerdict.FRAUD, FraudVerdict.REVIEW]
        
        has_amount_flag = any(
            "amount" in flag.lower() for flag in 
            (result.voting_summary.get("agent_votes", {}).get("transaction_history_agent", {}).get("findings", []) or [])
        )
        
        print(f"\n🚨 Account takeover (unusual amount): {result.final_verdict.value}")
        print(f"   Amount: ${check.amount:,.2f}")
        print(f"   Risk Level: {result.final_risk_level.value}")
    
    def test_scenario_new_account_fraud(self, sample_data):
        """
        Scenario: New account with suspicious large transaction.
        Expected: FRAUD or REVIEW with elevated risk.
        """
        check = sample_data["fraudulent_checks"][3]
        client = sample_data["clients"]["CLIENT004"]
        
        result = run_fraud_detection_without_llm(check, client)
        
        assert result.final_verdict in [FraudVerdict.FRAUD, FraudVerdict.REVIEW]
        assert result.final_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        
        print(f"\n🚨 New account fraud: {result.final_verdict.value}")
        print(f"   Client Risk Score: {client.risk_score}")
        print(f"   Risk Level: {result.final_risk_level.value}")
    
    def test_scenario_mobile_deposit_from_emulator(self, sample_data):
        """
        Scenario: Mobile deposit from detected emulator device.
        Expected: FRAUD or REVIEW due to suspicious device.
        """
        check = None
        for c in sample_data["fraudulent_checks"]:
            if c.metadata.get("device", "").lower() == "emulator":
                check = c
                break
        
        if check is None:
            pytest.skip("No emulator deposit in sample data")
        
        client = sample_data["clients"].get(check.client_id)
        result = run_fraud_detection_without_llm(check, client)
        
        assert result.final_verdict in [FraudVerdict.FRAUD, FraudVerdict.REVIEW]
        
        print(f"\n🚨 Emulator deposit: {result.final_verdict.value}")
        print(f"   Device: {check.metadata.get('device')}")
    
    def test_scenario_altered_check(self, sample_data):
        """
        Scenario: Check with suspected amount alteration.
        Expected: REVIEW or FRAUD due to manipulation indicators.
        """
        check = None
        for c in sample_data["fraudulent_checks"]:
            if "altered_amount_suspected" in c.metadata.get("flags", []):
                check = c
                break
        
        if check is None:
            pytest.skip("No altered check in sample data")
        
        client = sample_data["clients"].get(check.client_id)
        result = run_fraud_detection_without_llm(check, client)
        
        assert result.final_verdict in [FraudVerdict.FRAUD, FraudVerdict.REVIEW]
        
        print(f"\n🚨 Altered check: {result.final_verdict.value}")
        print(f"   Risk Level: {result.final_risk_level.value}")
    
    def test_scenario_cash_payee(self, sample_data):
        """
        Scenario: Check made payable to "Cash".
        Expected: REVIEW or FRAUD due to suspicious payee.
        """
        check = None
        for c in sample_data["fraudulent_checks"]:
            if c.payee.lower() == "cash":
                check = c
                break
        
        if check is None:
            pytest.skip("No cash payee check in sample data")
        
        client = sample_data["clients"].get(check.client_id)
        result = run_fraud_detection_without_llm(check, client)
        
        assert result.final_verdict in [FraudVerdict.FRAUD, FraudVerdict.REVIEW]
        
        print(f"\n🚨 Cash payee: {result.final_verdict.value}")


class TestToolsIntegration:
    """Test individual tools work correctly."""
    
    def test_watermark_detector(self, sample_data):
        """Test watermark detection tool."""
        detector = WatermarkDetector()
        
        legit_check = sample_data["legitimate_checks"][0].model_dump()
        result = detector.analyze(legit_check)
        assert result.watermark_detected == True
        
        fraud_check = sample_data["fraudulent_checks"][0].model_dump()
        result = detector.analyze(fraud_check)
        assert result.watermark_detected == False
    
    def test_signature_analyzer(self, sample_data):
        """Test signature analysis tool."""
        analyzer = SignatureAnalyzer()
        
        legit_check = sample_data["legitimate_checks"][0].model_dump()
        result = analyzer.analyze(legit_check)
        assert result.signature_present == True
        assert result.signature_valid == True
        
        for check in sample_data["fraudulent_checks"]:
            if not check.signature_present:
                result = analyzer.analyze(check.model_dump())
                assert result.signature_present == False
                break
    
    def test_micr_validator(self, sample_data):
        """Test MICR validation tool."""
        validator = MICRValidator()
        
        check = sample_data["legitimate_checks"][0].model_dump()
        result = validator.validate(check)
        
        assert result.micr_present == True
        assert result.routing_number is not None
    
    def test_image_quality_analyzer(self, sample_data):
        """Test image quality analysis tool."""
        analyzer = ImageQualityAnalyzer()
        
        legit_check = sample_data["legitimate_checks"][0].model_dump()
        result = analyzer.analyze(legit_check)
        assert result.overall_score > 0.5
        
        for check in sample_data["fraudulent_checks"]:
            if check.metadata.get("image_quality_score", 1.0) < 0.5:
                result = analyzer.analyze(check.model_dump())
                assert result.overall_score < 0.6
                break


class TestDatabaseIntegration:
    """Test database components."""
    
    def test_transaction_database(self, sample_data):
        """Test transaction database operations."""
        db = TransactionDatabase()
        
        client = db.get_client("CLIENT001")
        assert client is not None
        assert client.name == "John Smith"
        
        transactions = db.get_transactions_by_client("CLIENT001", days_back=365)
        assert len(transactions) > 0
        
        stats = db.get_transaction_statistics("CLIENT001")
        assert stats["total_transactions"] > 0
        assert stats["average_amount"] > 0
    
    def test_policy_database(self, sample_data):
        """Test policy database operations."""
        db = PolicyDatabase()
        
        policies = db.get_all_policies()
        assert len(policies) > 0
        
        policy = db.get_policy("POL001")
        assert policy is not None
        assert policy.name == "High Amount Threshold"
        
        summary = db.get_policy_summary()
        assert summary["total_policies"] > 0
    
    def test_policy_evaluation(self, sample_data):
        """Test policy evaluation against checks."""
        db = PolicyDatabase()
        tx_db = TransactionDatabase()
        
        fraud_check = sample_data["fraudulent_checks"][0]
        client = tx_db.get_client(fraud_check.client_id)
        stats = tx_db.get_transaction_statistics(fraud_check.client_id) if client else None
        
        violations = db.evaluate_check(fraud_check, client, stats)
        assert len(violations) > 0


class TestSystemResilience:
    """Test system handles edge cases gracefully."""
    
    def test_missing_client_data(self, sample_data):
        """Test system handles missing client gracefully."""
        check = sample_data["legitimate_checks"][0]
        check_dict = check.model_dump()
        check_dict["client_id"] = "NONEXISTENT"
        modified_check = Check(**check_dict)
        
        result = run_fraud_detection_without_llm(modified_check, None)
        
        assert result is not None
        assert result.final_verdict is not None
    
    def test_minimal_check_data(self):
        """Test system handles minimal check data."""
        minimal_check = Check(
            check_id="MINIMAL001",
            check_number="1",
            client_id="UNKNOWN",
            date=datetime.now(),
            amount=100.00,
            amount_written="One hundred",
            payee="Test Payee",
            bank_name="Test Bank",
            routing_number="071000013",
            account_number="1234567890",
        )
        
        result = run_fraud_detection_without_llm(minimal_check, None)
        
        assert result is not None
        assert result.final_verdict is not None
    
    def test_extreme_amount(self):
        """Test system handles extreme amounts."""
        extreme_check = Check(
            check_id="EXTREME001",
            check_number="1",
            client_id="CLIENT001",
            date=datetime.now(),
            amount=999999999.99,
            amount_written="Nine hundred ninety-nine million",
            payee="Test Payee",
            bank_name="Test Bank",
            routing_number="071000013",
            account_number="1234567890",
        )
        
        result = run_fraud_detection_without_llm(extreme_check, None)
        
        assert result is not None
        assert result.final_verdict in [FraudVerdict.FRAUD, FraudVerdict.REVIEW]
        assert result.final_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]


class TestPerformance:
    """Basic performance tests."""
    
    def test_workflow_completes_in_reasonable_time(self, sample_data):
        """Test workflow completes within acceptable time."""
        check = sample_data["legitimate_checks"][0]
        client = sample_data["clients"].get(check.client_id)
        
        start = datetime.now()
        result = run_fraud_detection_without_llm(check, client)
        elapsed = (datetime.now() - start).total_seconds()
        
        assert elapsed < 5.0
        assert result.processing_time_seconds < 5.0
        
        print(f"\n⏱️ Workflow completed in {elapsed:.3f} seconds")
    
    def test_batch_processing(self, sample_data):
        """Test processing multiple checks."""
        all_checks = sample_data["all_checks"]
        
        start = datetime.now()
        results = []
        
        for check in all_checks:
            client = sample_data["clients"].get(check.client_id)
            result = run_fraud_detection_without_llm(check, client)
            results.append(result)
        
        elapsed = (datetime.now() - start).total_seconds()
        avg_time = elapsed / len(all_checks)
        
        assert all(r is not None for r in results)
        assert avg_time < 2.0
        
        print(f"\n⏱️ Processed {len(all_checks)} checks in {elapsed:.2f}s")
        print(f"   Average: {avg_time:.3f}s per check")


def run_all_scenarios():
    """Run all test scenarios and print summary."""
    print("\n" + "=" * 60)
    print("CHECK FRAUD DETECTION - END-TO-END TEST SUITE")
    print("=" * 60)
    
    sample_data = initialize_sample_data()
    
    test_class = TestEndToEndScenarios()
    
    scenarios = [
        ("Legitimate Utility Payment", test_class.test_scenario_legitimate_utility_payment),
        ("Counterfeit Check (No Watermark)", test_class.test_scenario_counterfeit_check_no_watermark),
        ("Forged Signature", test_class.test_scenario_forged_signature),
        ("Account Takeover", test_class.test_scenario_account_takeover_unusual_amount),
        ("New Account Fraud", test_class.test_scenario_new_account_fraud),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in scenarios:
        try:
            test_func(sample_data)
            passed += 1
        except Exception as e:
            print(f"\n❌ {name}: FAILED - {str(e)}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)


if __name__ == "__main__":
    run_all_scenarios()
    print("\n\nRunning full pytest suite...")
    pytest.main([__file__, "-v", "--tb=short"])
