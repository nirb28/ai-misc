# Check Fraud Detection System

> **LangGraph-based Multi-Agent Fraud Analysis with Simulation and Real LLM Modes**

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

Create a `.env` file based on `.env.example`:

```bash
# LLM Provider API Keys
GROQ_API_KEY=your_groq_key_here
OPENAI_API_KEY=your_openai_key_here

# Azure OpenAI Configuration (for gpt-5-nano or other Azure models)
AZURE_OPENAI_API_KEY=your_azure_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-5-nano
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Default provider and simulation mode
LLM_PROVIDER=azure
USE_SIMULATION=false
```

## Simulation vs Real Mode

The system supports two modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Simulation** (default) | Uses rule-based heuristics for analysis | Testing, development, no API costs |
| **Real** | Uses actual LLM models for all analysis | Production, accurate fraud detection |

## Running the System

## Using Downloaded Check Images

This repo supports running analysis against real image files stored locally.

1) Create the folder:

```bash
mkdir sample_checks\downloaded
```

2) Download a permissively licensed sample check image (Wikimedia Commons):

```powershell
Invoke-WebRequest `
  -Uri "https://upload.wikimedia.org/wikipedia/commons/3/3c/Sample_cheque.jpeg" `
  -OutFile "sample_checks\downloaded\sample_cheque.jpeg"
```

The built-in sample checks `CHECK001` and `CHECK_FRAUD001` are configured to reference:

```
sample_checks/downloaded/sample_cheque.jpeg
```

In **real mode** (`--real`), the `ImageQualityAnalyzer` will compute brightness/contrast/sharpness from the image file.

### CLI Usage

```bash
# List available checks
python main.py --list-checks

# Simulation mode (default) - no LLM calls for tools
python main.py --check-id CHECK001 --no-llm --verbose

# With LLM generic agent (simulation for tools, LLM for holistic analysis)
python main.py --check-id CHECK_FRAUD001 --verbose

# REAL mode - all agents use LLM (Azure gpt-5-nano)
python main.py --check-id CHECK_FRAUD001 --real --llm-provider azure --verbose

# REAL mode with Groq
python main.py --check-id CHECK_FRAUD001 --real --llm-provider groq --verbose
```

### Start the UI
```bash
streamlit run ui/app.py
```

### Run Tests
```bash
pytest tests/ -v
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


.venv\Scripts\activate; 
python main.py --check-id CHECK001 --real --llm-provider azure --verbose