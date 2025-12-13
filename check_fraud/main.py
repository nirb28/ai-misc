"""Main entry point for the check fraud detection system."""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

from database.models import FraudVerdict, RiskLevel
from database.sample_data import initialize_sample_data
from graph.workflow import run_fraud_detection, run_fraud_detection_without_llm


def print_analysis_result(result, verbose: bool = False):
    """Print analysis result in a formatted way."""
    print("\n" + "=" * 60)
    print("CHECK FRAUD ANALYSIS RESULT")
    print("=" * 60)
    
    print(f"\nAnalysis ID: {result.analysis_id}")
    print(f"Check ID: {result.check_id}")
    print(f"Client ID: {result.client_id}")
    
    verdict_colors = {
        FraudVerdict.FRAUD: "\033[91m",
        FraudVerdict.NOT_FRAUD: "\033[92m",
        FraudVerdict.REVIEW: "\033[93m",
    }
    reset = "\033[0m"
    
    color = verdict_colors.get(result.final_verdict, "")
    print(f"\n{'─' * 40}")
    print(f"FINAL VERDICT: {color}{result.final_verdict.value.upper()}{reset}")
    print(f"Confidence: {result.final_confidence:.1%}")
    print(f"Risk Level: {result.final_risk_level.value.upper()}")
    print(f"Consensus: {'Yes' if result.consensus_reached else 'No'}")
    print(f"{'─' * 40}")
    
    print(f"\nProcessing Time: {result.processing_time_seconds:.2f} seconds")
    
    if result.voting_summary:
        print("\n--- Voting Summary ---")
        votes = result.voting_summary.get("vote_counts", {})
        print(f"Vote Counts: {votes}")
        
        if verbose and result.voting_summary.get("agent_votes"):
            print("\nAgent Votes:")
            for agent, vote in result.voting_summary["agent_votes"].items():
                print(f"  {agent}:")
                print(f"    Verdict: {vote['verdict']}")
                print(f"    Confidence: {vote['confidence']:.1%}")
                print(f"    Risk: {vote['risk_level']}")
    
    if verbose and result.agent_verdicts:
        print("\n--- Agent Details ---")
        for verdict in result.agent_verdicts:
            print(f"\n[{verdict.agent_name}]")
            print(f"  Verdict: {verdict.verdict.value}")
            print(f"  Confidence: {verdict.confidence:.1%}")
            print(f"  Risk Level: {verdict.risk_level.value}")
            print(f"  Reasoning: {verdict.reasoning[:200]}...")
            if verdict.findings:
                print(f"  Findings: {verdict.findings[:3]}")
    
    if result.notes:
        print("\n--- Analysis Notes ---")
        print(result.notes)
    
    print("\n" + "=" * 60)


def main():
    """Main function to run fraud detection from command line."""
    parser = argparse.ArgumentParser(
        description="Check Fraud Detection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --check-id CHECK001
  python main.py --check-id CHECK_FRAUD001 --verbose
  python main.py --list-checks
  python main.py --check-id CHECK_FRAUD003 --no-llm
        """
    )
    
    parser.add_argument(
        "--check-id",
        type=str,
        help="ID of the check to analyze",
    )
    parser.add_argument(
        "--list-checks",
        action="store_true",
        help="List all available sample checks",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed analysis output",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Run without LLM-based generic agent",
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        default="groq",
        choices=["groq", "openai"],
        help="LLM provider to use (default: groq)",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        help="Specific LLM model to use",
    )
    
    args = parser.parse_args()
    
    load_dotenv()
    
    sample_data = initialize_sample_data()
    
    if args.list_checks:
        print("\nAvailable Sample Checks:")
        print("-" * 60)
        print("\nLegitimate Checks:")
        for check in sample_data["legitimate_checks"]:
            print(f"  {check.check_id}: ${check.amount:,.2f} to {check.payee}")
        print("\nPotentially Fraudulent Checks:")
        for check in sample_data["fraudulent_checks"]:
            flags = check.metadata.get("flags", [])
            print(f"  {check.check_id}: ${check.amount:,.2f} to {check.payee}")
            print(f"    Flags: {', '.join(flags[:3])}")
        return
    
    if not args.check_id:
        parser.print_help()
        print("\nError: --check-id is required unless using --list-checks")
        return
    
    check = None
    for c in sample_data["all_checks"]:
        if c.check_id == args.check_id:
            check = c
            break
    
    if not check:
        print(f"Error: Check '{args.check_id}' not found")
        print("Use --list-checks to see available checks")
        return
    
    client = sample_data["clients"].get(check.client_id)
    
    print(f"\nAnalyzing check: {check.check_id}")
    print(f"Amount: ${check.amount:,.2f}")
    print(f"Payee: {check.payee}")
    print(f"Client: {client.name if client else 'Unknown'}")
    print("\nRunning fraud detection workflow...")
    
    try:
        if args.no_llm:
            result = run_fraud_detection_without_llm(check, client)
        else:
            result = run_fraud_detection(
                check,
                client,
                llm_provider=args.llm_provider,
                llm_model=args.llm_model,
            )
        
        print_analysis_result(result, args.verbose)
        
    except Exception as e:
        print(f"\nError during analysis: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
