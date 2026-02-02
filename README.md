# 🧠 Multi-Agent LLM Support Triage System

A **production-grade, contract-based multi-agent LLM system** for support-ticket triage.  
Built to make **probabilistic LLMs safe, testable, and deployable** using deterministic guarantees, regression tests, and versioning.

---

## 🎯 Core Idea

LLMs are stochastic → outputs can drift  
So we **define a contract** and **enforce it automatically**.

This project applies **software engineering discipline** to AI systems.

---

## 🧩 Architecture Overview



---

## 🧠 Agent Roles

### Classifier Agent
Determines:
- `category`
- `priority`
- `routing`
- `confidence`

### Responder Agent
Generates:
- Customer reply
- Required clarifying questions
- Internal follow-up actions

### Orchestrator
- Merges sub-agent outputs
- Enforces schema and behavioral rules
- Prevents unsafe language
- Adds model & prompt version metadata

---

## 📜 Contract-Based Engineering

### 1. Schema Contract
- Required fields
- Minimum lengths
- Correct types

### 2. Behavioral Contract
- Mandatory questions per category
- Mandatory actions per scenario
- Safety constraints

### 3. Regression Contract
- Fixed test cases
- Automatic failure on behavior drift

This is **unit testing for LLM behavior**.

---

## 🧪 Prompt Regression Testing

Run the full regression suite:

```bash
python -m eval.runners.run_eval

```
## 🧠 LLM Backends

```bash
export USE_OLLAMA=1
export PROMPT_VERSION=triage/v1
export MODEL_VERSION=models/triage/v1.json
```
## 🧾 Prompt Versioning

prompts/
└── triage/
    ├── v1/
    │   ├── classify.md
    │   └── respond.md
    └── v2/
        ├── classify.md
        └── respond.md
Change → test → promote.

## 🚀 Deployment Options

```bash
PROMPT_VERSION=triage/v1
MODEL_VERSION=models/triage/v1.json
```
