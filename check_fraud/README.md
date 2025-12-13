# Check Fraud Detection System

A LangGraph-based agentic solution for detecting check fraud using multiple specialized agents and a voting mechanism.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Check Fraud Detection System                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Check      │    │  Transaction │    │   Policy     │      │
│  │   Analysis   │    │   History    │    │   Analysis   │      │
│  │   Agent      │    │   Agent      │    │   Agent      │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         │    ┌──────────────┴──────────────┐   │               │
│         └────►       Generic Fraud         ◄───┘               │
│              │       Analysis Agent        │                    │
│              └──────────────┬──────────────┘                    │
│                             │                                   │
│              ┌──────────────▼──────────────┐                    │
│              │      Voting Aggregator      │                    │
│              │   (Consensus Decision)      │                    │
│              └──────────────┬──────────────┘                    │
│                             │                                   │
│              ┌──────────────▼──────────────┐                    │
│              │      Final Decision         │                    │
│              │   FRAUD / NOT FRAUD / REVIEW│                    │
│              └─────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

## Agents

### 1. Check Analysis Agent
- Analyzes physical check characteristics
- Watermark detection and validation
- Signature analysis and comparison
- MICR line validation
- Check image quality assessment

### 2. Transaction History Agent
- Reviews client's historical check transactions
- Identifies unusual patterns (amount, frequency, payees)
- Compares against established behavior baseline
- Flags anomalies in transaction patterns

### 3. Policy Analysis Agent
- Applies documented fraud detection policies
- Rule-based analysis using bank policies
- Compliance checking
- Threshold-based alerts

### 4. Generic Fraud Analysis Agent
- Advanced LLM-based fraud detection
- Holistic analysis combining all signals
- Pattern recognition across multiple dimensions
- Contextual fraud assessment

### 5. Voting Aggregator
- Collects verdicts from all agents
- Weighted voting mechanism
- Consensus-based final decision
- Confidence scoring

## Setup

```bash
cd check_fraud
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file:
```
OPENAI_API_KEY=your_key_here
# Or use other LLM providers
GROQ_API_KEY=your_groq_key
```

## Running the System

### Start the UI
```bash
streamlit run ui/app.py
```

### Run Tests
```bash
pytest tests/ -v
```

### CLI Usage
```bash
python -m check_fraud.main --check-id CHECK001
```

## Project Structure

```
check_fraud/
├── README.md
├── requirements.txt
├── .env.example
├── agents/
│   ├── __init__.py
│   ├── check_analysis_agent.py
│   ├── transaction_history_agent.py
│   ├── policy_agent.py
│   ├── generic_fraud_agent.py
│   └── voting_aggregator.py
├── tools/
│   ├── __init__.py
│   ├── watermark_detector.py
│   ├── signature_analyzer.py
│   ├── micr_validator.py
│   └── image_quality.py
├── database/
│   ├── __init__.py
│   ├── models.py
│   ├── sample_data.py
│   ├── transaction_db.py
│   └── policy_db.py
├── graph/
│   ├── __init__.py
│   ├── workflow.py
│   └── state.py
├── ui/
│   ├── app.py
│   └── components.py
├── tests/
│   ├── __init__.py
│   ├── test_agents.py
│   ├── test_workflow.py
│   └── test_e2e.py
└── sample_checks/
    └── (sample check images and data)
```

## License

MIT
