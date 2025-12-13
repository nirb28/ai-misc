"""Tests for individual fraud detection agents."""

import pytest
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import Check, Client, FraudVerdict, RiskLevel
from database.sample_data import initialize_sample_data
from graph.state import create_initial_state
from agents.check_analysis_agent import CheckAnalysisAgent
from agents.transaction_history_agent import TransactionHistoryAgent
from agents.policy_agent import PolicyAnalysisAgent
from agents.voting_aggregator import VotingAggregator


@pytest.fixture
def sample_data():
    """Load sample data for tests."""
    return initialize_sample_data()


@pytest.fixture
def legitimate_check(sample_data):
    """Get a legitimate check for testing."""
    return sample_data["legitimate_checks"][0]


@pytest.fixture
def fraudulent_check(sample_data):
    """Get a fraudulent check for testing."""
    return sample_data["fraudulent_checks"][0]


@pytest.fixture
def client(sample_data):
    """Get a sample client."""
    return sample_data["clients"]["CLIENT001"]


class TestCheckAnalysisAgent:
    """Tests for CheckAnalysisAgent."""
    
    def test_analyze_legitimate_check(self, legitimate_check, client):
        """Test analysis of a legitimate check."""
        agent = CheckAnalysisAgent()
        state = create_initial_state(legitimate_check, client)
        
        result = agent.analyze(state)
        
        assert "check_analysis" in result
        assert "agent_verdicts" in result
        assert len(result["agent_verdicts"]) == 1
        
        verdict = result["agent_verdicts"][0]
        assert verdict.agent_name == "check_analysis_agent"
        assert verdict.verdict in [FraudVerdict.NOT_FRAUD, FraudVerdict.REVIEW]
        assert verdict.confidence > 0
    
    def test_analyze_check_missing_watermark(self, sample_data):
        """Test analysis of check missing watermark."""
        check = sample_data["fraudulent_checks"][0]
        agent = CheckAnalysisAgent()
        state = create_initial_state(check, None)
        
        result = agent.analyze(state)
        
        analysis = result["check_analysis"]
        assert analysis["watermark_analysis"]["detected"] == False
        assert "missing_watermark" in result["all_flags"]
    
    def test_analyze_check_missing_signature(self, sample_data):
        """Test analysis of check missing signature."""
        check = None
        for c in sample_data["fraudulent_checks"]:
            if not c.signature_present:
                check = c
                break
        
        if check is None:
            pytest.skip("No check without signature in sample data")
        
        agent = CheckAnalysisAgent()
        state = create_initial_state(check, None)
        
        result = agent.analyze(state)
        
        analysis = result["check_analysis"]
        assert analysis["signature_analysis"]["present"] == False
        assert "missing_signature" in result["all_flags"]
        
        verdict = result["agent_verdicts"][0]
        assert verdict.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]


class TestTransactionHistoryAgent:
    """Tests for TransactionHistoryAgent."""
    
    def test_analyze_normal_transaction(self, legitimate_check, client):
        """Test analysis of normal transaction."""
        agent = TransactionHistoryAgent()
        state = create_initial_state(legitimate_check, client)
        
        result = agent.analyze(state)
        
        assert "transaction_analysis" in result
        assert result["transaction_analysis"]["client_found"] == True
        
        verdict = result["agent_verdicts"][0]
        assert verdict.agent_name == "transaction_history_agent"
    
    def test_analyze_anomalous_amount(self, sample_data):
        """Test detection of anomalous transaction amount."""
        check = sample_data["fraudulent_checks"][0]
        client = sample_data["clients"].get(check.client_id)
        
        agent = TransactionHistoryAgent()
        state = create_initial_state(check, client)
        
        result = agent.analyze(state)
        
        analysis = result["transaction_analysis"]
        assert analysis["amount_anomaly_score"] > 0.5
    
    def test_unknown_client(self, sample_data):
        """Test handling of unknown client."""
        check = sample_data["legitimate_checks"][0]
        check_dict = check.model_dump()
        check_dict["client_id"] = "UNKNOWN_CLIENT"
        modified_check = Check(**check_dict)
        
        agent = TransactionHistoryAgent()
        state = create_initial_state(modified_check, None)
        
        result = agent.analyze(state)
        
        assert result["transaction_analysis"]["client_found"] == False
        assert "unknown_client" in result["all_flags"]


class TestPolicyAnalysisAgent:
    """Tests for PolicyAnalysisAgent."""
    
    def test_analyze_compliant_check(self, legitimate_check, client):
        """Test analysis of policy-compliant check."""
        agent = PolicyAnalysisAgent()
        state = create_initial_state(legitimate_check, client)
        
        result = agent.analyze(state)
        
        assert "policy_analysis" in result
        analysis = result["policy_analysis"]
        assert analysis["policies_evaluated"] > 0
    
    def test_detect_policy_violations(self, sample_data):
        """Test detection of policy violations."""
        check = sample_data["fraudulent_checks"][0]
        client = sample_data["clients"].get(check.client_id)
        
        agent = PolicyAnalysisAgent()
        state = create_initial_state(check, client)
        
        result = agent.analyze(state)
        
        analysis = result["policy_analysis"]
        assert analysis["violation_count"] > 0
    
    def test_get_policy_documentation(self):
        """Test policy documentation retrieval."""
        agent = PolicyAnalysisAgent()
        docs = agent.get_policy_documentation()
        
        assert "Fraud Detection Policies" in docs
        assert len(docs) > 100


class TestVotingAggregator:
    """Tests for VotingAggregator."""
    
    def test_aggregate_unanimous_fraud(self):
        """Test aggregation with unanimous fraud verdict."""
        from database.models import AgentVerdict
        
        verdicts = [
            AgentVerdict(
                agent_name="agent1",
                verdict=FraudVerdict.FRAUD,
                confidence=0.9,
                risk_level=RiskLevel.HIGH,
                reasoning="Test",
                findings=[],
                recommendations=[],
            ),
            AgentVerdict(
                agent_name="agent2",
                verdict=FraudVerdict.FRAUD,
                confidence=0.85,
                risk_level=RiskLevel.HIGH,
                reasoning="Test",
                findings=[],
                recommendations=[],
            ),
        ]
        
        state = {
            "check": Check(
                check_id="TEST",
                check_number="1",
                client_id="C1",
                date=datetime.now(),
                amount=100,
                amount_written="One hundred",
                payee="Test",
                bank_name="Test Bank",
                routing_number="123456789",
                account_number="1234567890",
            ),
            "client": None,
            "agent_verdicts": verdicts,
            "all_flags": [],
            "all_findings": [],
            "all_recommendations": [],
            "processing_start_time": datetime.now(),
            "processing_errors": [],
            "current_step": "test",
        }
        
        aggregator = VotingAggregator()
        result = aggregator.aggregate(state)
        
        assert result["final_verdict"] == FraudVerdict.FRAUD
        assert result["consensus_reached"] == True
    
    def test_aggregate_unanimous_not_fraud(self):
        """Test aggregation with unanimous not fraud verdict."""
        from database.models import AgentVerdict
        
        verdicts = [
            AgentVerdict(
                agent_name="agent1",
                verdict=FraudVerdict.NOT_FRAUD,
                confidence=0.9,
                risk_level=RiskLevel.LOW,
                reasoning="Test",
                findings=[],
                recommendations=[],
            ),
            AgentVerdict(
                agent_name="agent2",
                verdict=FraudVerdict.NOT_FRAUD,
                confidence=0.85,
                risk_level=RiskLevel.LOW,
                reasoning="Test",
                findings=[],
                recommendations=[],
            ),
        ]
        
        state = {
            "check": Check(
                check_id="TEST",
                check_number="1",
                client_id="C1",
                date=datetime.now(),
                amount=100,
                amount_written="One hundred",
                payee="Test",
                bank_name="Test Bank",
                routing_number="123456789",
                account_number="1234567890",
            ),
            "client": None,
            "agent_verdicts": verdicts,
            "all_flags": [],
            "all_findings": [],
            "all_recommendations": [],
            "processing_start_time": datetime.now(),
            "processing_errors": [],
            "current_step": "test",
        }
        
        aggregator = VotingAggregator()
        result = aggregator.aggregate(state)
        
        assert result["final_verdict"] == FraudVerdict.NOT_FRAUD
        assert result["consensus_reached"] == True
    
    def test_aggregate_mixed_verdicts(self):
        """Test aggregation with mixed verdicts."""
        from database.models import AgentVerdict
        
        verdicts = [
            AgentVerdict(
                agent_name="agent1",
                verdict=FraudVerdict.FRAUD,
                confidence=0.7,
                risk_level=RiskLevel.HIGH,
                reasoning="Test",
                findings=[],
                recommendations=[],
            ),
            AgentVerdict(
                agent_name="agent2",
                verdict=FraudVerdict.NOT_FRAUD,
                confidence=0.8,
                risk_level=RiskLevel.LOW,
                reasoning="Test",
                findings=[],
                recommendations=[],
            ),
            AgentVerdict(
                agent_name="agent3",
                verdict=FraudVerdict.REVIEW,
                confidence=0.6,
                risk_level=RiskLevel.MEDIUM,
                reasoning="Test",
                findings=[],
                recommendations=[],
            ),
        ]
        
        state = {
            "check": Check(
                check_id="TEST",
                check_number="1",
                client_id="C1",
                date=datetime.now(),
                amount=100,
                amount_written="One hundred",
                payee="Test",
                bank_name="Test Bank",
                routing_number="123456789",
                account_number="1234567890",
            ),
            "client": None,
            "agent_verdicts": verdicts,
            "all_flags": [],
            "all_findings": [],
            "all_recommendations": [],
            "processing_start_time": datetime.now(),
            "processing_errors": [],
            "current_step": "test",
        }
        
        aggregator = VotingAggregator()
        result = aggregator.aggregate(state)
        
        assert result["final_verdict"] in [FraudVerdict.FRAUD, FraudVerdict.REVIEW, FraudVerdict.NOT_FRAUD]
        assert "voting_summary" in result
        assert result["voting_summary"]["total_agents"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
