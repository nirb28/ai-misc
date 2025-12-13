"""Transaction database for historical check analysis."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from .models import Transaction, Client, Check
from .sample_data import create_sample_clients, create_sample_transactions


class TransactionDatabase:
    """In-memory transaction database for demo purposes."""
    
    def __init__(self):
        self.clients: Dict[str, Client] = {}
        self.transactions: List[Transaction] = []
        self._load_sample_data()
    
    def _load_sample_data(self):
        """Load sample data into the database."""
        self.clients = create_sample_clients()
        self.transactions = create_sample_transactions(self.clients)
    
    def get_client(self, client_id: str) -> Optional[Client]:
        """Get client by ID."""
        return self.clients.get(client_id)
    
    def get_client_by_account(self, account_number: str) -> Optional[Client]:
        """Get client by account number."""
        for client in self.clients.values():
            if client.account_number == account_number:
                return client
        return None
    
    def get_transactions_by_client(
        self,
        client_id: str,
        days_back: int = 365,
        limit: Optional[int] = None,
    ) -> List[Transaction]:
        """Get transactions for a client within a time window."""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        transactions = [
            tx for tx in self.transactions
            if tx.client_id == client_id and tx.date >= cutoff_date
        ]
        transactions.sort(key=lambda x: x.date, reverse=True)
        if limit:
            return transactions[:limit]
        return transactions
    
    def get_transactions_by_payee(
        self,
        client_id: str,
        payee: str,
    ) -> List[Transaction]:
        """Get all transactions to a specific payee."""
        return [
            tx for tx in self.transactions
            if tx.client_id == client_id and tx.payee.lower() == payee.lower()
        ]
    
    def get_transaction_statistics(self, client_id: str) -> Dict[str, Any]:
        """Calculate transaction statistics for a client."""
        transactions = self.get_transactions_by_client(client_id)
        
        if not transactions:
            return {
                "total_transactions": 0,
                "average_amount": 0.0,
                "max_amount": 0.0,
                "min_amount": 0.0,
                "total_amount": 0.0,
                "unique_payees": [],
                "transactions_per_month": 0.0,
            }
        
        amounts = [tx.amount for tx in transactions]
        payees = list(set(tx.payee for tx in transactions))
        
        date_range = (max(tx.date for tx in transactions) - min(tx.date for tx in transactions)).days
        months = max(date_range / 30, 1)
        
        return {
            "total_transactions": len(transactions),
            "average_amount": sum(amounts) / len(amounts),
            "max_amount": max(amounts),
            "min_amount": min(amounts),
            "total_amount": sum(amounts),
            "std_dev_amount": self._calculate_std_dev(amounts),
            "unique_payees": payees,
            "transactions_per_month": len(transactions) / months,
        }
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    def is_payee_known(self, client_id: str, payee: str) -> bool:
        """Check if payee is in client's typical payees."""
        client = self.get_client(client_id)
        if not client:
            return False
        return payee.lower() in [p.lower() for p in client.typical_payees]
    
    def get_amount_anomaly_score(self, client_id: str, amount: float) -> float:
        """Calculate how anomalous an amount is (0-1 scale, higher = more anomalous)."""
        stats = self.get_transaction_statistics(client_id)
        
        if stats["total_transactions"] == 0:
            return 0.5
        
        avg = stats["average_amount"]
        std_dev = stats["std_dev_amount"]
        
        if std_dev == 0:
            return 0.0 if amount == avg else 0.8
        
        z_score = abs(amount - avg) / std_dev
        anomaly_score = min(z_score / 5, 1.0)
        
        return anomaly_score
    
    def get_recent_deposit_count(
        self,
        client_id: str,
        hours: int = 24,
    ) -> int:
        """Count deposits in recent time window."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return len([
            tx for tx in self.transactions
            if tx.client_id == client_id and tx.date >= cutoff
        ])
    
    def analyze_check_against_history(self, check: Check) -> Dict[str, Any]:
        """Comprehensive analysis of a check against transaction history."""
        client = self.get_client(check.client_id)
        stats = self.get_transaction_statistics(check.client_id)
        
        analysis = {
            "client_found": client is not None,
            "client_name": client.name if client else "Unknown",
            "account_age_days": 0,
            "transaction_history": stats,
            "amount_anomaly_score": self.get_amount_anomaly_score(check.client_id, check.amount),
            "payee_is_known": self.is_payee_known(check.client_id, check.payee),
            "recent_deposits_24h": self.get_recent_deposit_count(check.client_id, 24),
            "flags": [],
        }
        
        if client:
            analysis["account_age_days"] = (datetime.now() - client.account_opened_date).days
            analysis["client_risk_score"] = client.risk_score
        
        if analysis["amount_anomaly_score"] > 0.7:
            analysis["flags"].append("high_amount_anomaly")
        
        if not analysis["payee_is_known"]:
            analysis["flags"].append("unknown_payee")
        
        if analysis["account_age_days"] < 90 and check.amount > 5000:
            analysis["flags"].append("new_account_large_transaction")
        
        if analysis["recent_deposits_24h"] > 3:
            analysis["flags"].append("rapid_succession_deposits")
        
        if client and check.payee.lower() == client.name.lower():
            analysis["flags"].append("self_payee")
        
        return analysis
