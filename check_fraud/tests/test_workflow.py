"""Tests for the fraud detection workflow."""

import pytest
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import Check, Client, FraudVerdict, RiskLevel
from database.sample_data import initialize_sample_data
from graph.workflow import run_fraud_detection_without_llm
from graph.state import create_initial_state


@pytest.fixture
def sample_data():
    """Load sample data for tests."""
    return initialize_sample_data()


class TestWorkflowWithoutLLM:
    """Tests for workflow without LLM agent."""
    
    def test_workflow_legitimate_check(self, sample_data):
        """Test workflow with a legitimate check."""
        check = sample_data["legitimate_checks"][0]
        client = sample_data["clients"].get(check.client_id)
        
        result = run_fraud_detection_without_llm(check, client)
        
        assert result is not None
        assert result.check_id == check.check_id
        assert result.final_verdict in [FraudVerdict.NOT_FRAUD, FraudVerdict.REVIEW, FraudVerdict.FRAUD]
        assert 0 <= result.final_confidence <= 1
        assert result.final_risk_level in RiskLevel
        assert len(result.agent_verdicts) >= 3
        assert result.processing_time_seconds > 0
    
    def test_workflow_fraudulent_check_missing_watermark(self, sample_data):
        """Test workflow with check missing watermark."""
        check = sample_data["fraudulent_checks"][0]
        client = sample_data["clients"].get(check.client_id)
        
        result = run_fraud_detection_without_llm(check, client)
        
        assert result is not None
        assert result.final_verdict in [FraudVerdict.FRAUD, FraudVerdict.REVIEW]
        assert result.final_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    
    def test_workflow_fraudulent_check_missing_signature(self, sample_data):
        """Test workflow with check missing signature."""
        check = None
        for c in sample_data["fraudulent_checks"]:
            if not c.signature_present:
                check = c
                break
        
        if check is None:
            pytest.skip("No check without signature in sample data")
        
        client = sample_data["clients"].get(check.client_id)
        result = run_fraud_detection_without_llm(check, client)
        
        assert result is not None
        assert result.final_verdict in [FraudVerdict.FRAUD, FraudVerdict.REVIEW]
    
    def test_workflow_high_amount_anomaly(self, sample_data):
        """Test workflow with high amount anomaly check."""
        check = sample_data["fraudulent_checks"][2]
        client = sample_data["clients"].get(check.client_id)
        
        result = run_fraud_detection_without_llm(check, client)
        
        assert result is not None
        assert result.final_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    
    def test_workflow_unknown_client(self, sample_data):
        """Test workflow with unknown client."""
        check = sample_data["legitimate_checks"][0]
        check_dict = check.model_dump()
        check_dict["client_id"] = "UNKNOWN_CLIENT_XYZ"
        modified_check = Check(**check_dict)
        
        result = run_fraud_detection_without_llm(modified_check, None)
        
        assert result is not None
        assert result.final_verdict in [FraudVerdict.REVIEW, FraudVerdict.FRAUD]
    
    def test_workflow_all_legitimate_checks(self, sample_data):
        """Test workflow processes all legitimate checks."""
        for check in sample_data["legitimate_checks"]:
            client = sample_data["clients"].get(check.client_id)
            result = run_fraud_detection_without_llm(check, client)
            
            assert result is not None
            assert result.check_id == check.check_id
            assert result.final_verdict is not None
    
    def test_workflow_all_fraudulent_checks(self, sample_data):
        """Test workflow processes all fraudulent checks."""
        fraud_detected = 0
        review_needed = 0
        
        for check in sample_data["fraudulent_checks"]:
            client = sample_data["clients"].get(check.client_id)
            result = run_fraud_detection_without_llm(check, client)
            
            assert result is not None
            assert result.check_id == check.check_id
            
            if result.final_verdict == FraudVerdict.FRAUD:
                fraud_detected += 1
            elif result.final_verdict == FraudVerdict.REVIEW:
                review_needed += 1
        
        total_flagged = fraud_detected + review_needed
        assert total_flagged >= len(sample_data["fraudulent_checks"]) * 0.8
    
    def test_workflow_voting_summary(self, sample_data):
        """Test that voting summary is properly populated."""
        check = sample_data["legitimate_checks"][0]
        client = sample_data["clients"].get(check.client_id)
        
        result = run_fraud_detection_without_llm(check, client)
        
        assert result.voting_summary is not None
        assert "total_agents" in result.voting_summary
        assert "vote_counts" in result.voting_summary
        assert result.voting_summary["total_agents"] >= 3
    
    def test_workflow_agent_verdicts_populated(self, sample_data):
        """Test that all agent verdicts are populated."""
        check = sample_data["legitimate_checks"][0]
        client = sample_data["clients"].get(check.client_id)
        
        result = run_fraud_detection_without_llm(check, client)
        
        agent_names = [v.agent_name for v in result.agent_verdicts]
        
        assert "check_analysis_agent" in agent_names
        assert "transaction_history_agent" in agent_names
        assert "policy_analysis_agent" in agent_names
    
    def test_workflow_consensus_calculation(self, sample_data):
        """Test consensus calculation."""
        check = sample_data["legitimate_checks"][0]
        client = sample_data["clients"].get(check.client_id)
        
        result = run_fraud_detection_without_llm(check, client)
        
        assert isinstance(result.consensus_reached, bool)


class TestWorkflowEdgeCases:
    """Test edge cases in the workflow."""
    
    def test_check_with_all_flags(self, sample_data):
        """Test check with multiple fraud flags."""
        check = sample_data["fraudulent_checks"][-1]
        client = sample_data["clients"].get(check.client_id)
        
        result = run_fraud_detection_without_llm(check, client)
        
        assert result is not None
        assert result.final_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    
    def test_new_account_large_transaction(self, sample_data):
        """Test new account with large transaction."""
        check = None
        for c in sample_data["fraudulent_checks"]:
            if c.amount > 10000:
                check = c
                break
        
        if check is None:
            pytest.skip("No high-value check in sample data")
        
        client = sample_data["clients"].get(check.client_id)
        result = run_fraud_detection_without_llm(check, client)
        
        assert result is not None
        assert result.final_verdict != FraudVerdict.NOT_FRAUD or result.final_risk_level != RiskLevel.LOW
    
    def test_self_payee_check(self, sample_data):
        """Test check with self as payee."""
        check = None
        for c in sample_data["fraudulent_checks"]:
            client = sample_data["clients"].get(c.client_id)
            if client and c.payee.lower() == client.name.lower():
                check = c
                break
        
        if check is None:
            pytest.skip("No self-payee check in sample data")
        
        client = sample_data["clients"].get(check.client_id)
        result = run_fraud_detection_without_llm(check, client)
        
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
