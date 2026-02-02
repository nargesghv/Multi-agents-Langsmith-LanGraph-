from __future__ import annotations
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]

def load_prompt(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")

def render(template: str, variables: Dict[str, str]) -> str:
    out = template
    for k, v in variables.items():
        out = out.replace("{{" + k + "}}", v)
    return out
