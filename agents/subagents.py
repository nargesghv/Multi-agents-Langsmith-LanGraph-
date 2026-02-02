from __future__ import annotations

import os
from typing import Any, Dict

from .llm import LocalStubLLM, OllamaLLM
from .model_config import load_model_config

PROMPT_VERSION = os.getenv("PROMPT_VERSION", "triage/v1")
MODEL_VERSION = os.getenv("MODEL_VERSION", "models/triage/v1.json")

# ✅ default is stub unless explicitly enabled
USE_OLLAMA = os.getenv("USE_OLLAMA", "0") == "1"

_llm = (
    OllamaLLM(load_model_config(MODEL_VERSION), prompt_version=PROMPT_VERSION)
    if USE_OLLAMA
    else LocalStubLLM()
)

def classifier_subagent(ticket: Dict[str, Any], signals: Dict[str, Any]) -> Dict[str, Any]:
    return _llm.classify(ticket, signals)

def responder_subagent(
    ticket: Dict[str, Any],
    classification: Dict[str, Any],
    signals: Dict[str, Any],
) -> Dict[str, Any]:
    return _llm.draft_reply(ticket, classification, signals)
