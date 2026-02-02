from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]

def load_model_config(relative_path: str) -> Dict[str, Any]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
