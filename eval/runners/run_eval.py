# eval/runners/run_eval.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

from jsonschema import validate, ValidationError

from agents.orchestrator import triage

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "eval" / "datasets" / "prompt_regression.jsonl"
SCHEMA_PATH = ROOT / "schemas" / "triage_output.schema.json"
ALIASES = {
  "device/browser": ["device", "browser"],
  "time of attempt": ["time", "timezone"],
  "date of charge": ["date", "charge"],
  "force logout sessions": ["force logout", "sessions"],
  "check monitoring dashboards": ["monitoring", "dashboards"],
  "confirm status codes": ["status codes", "http"]
}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

def load_schema(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def contains_any(haystack: str, needles: List[str]) -> bool:
    h = haystack.lower()
    return any(n.lower() in h for n in needles)
def requirement_met(q_text: str, req: str) -> bool:
    req_l = req.lower()
    if req_l in q_text:
        return True
    if req_l in ALIASES:
        return all(term in q_text for term in [t.lower() for t in ALIASES[req_l]])
    return False

def must_ask_about_check(questions: List[str], must_ask_about: List[str]) -> Tuple[bool, List[str]]:
    q_text = " ".join(questions).lower()
    missing = []
    for item in must_ask_about:
        if not requirement_met(q_text, item):
            missing.append(item)

    return (len(missing) == 0, missing)

def must_include_actions_check(actions: List[str], must_include: List[str]) -> Tuple[bool, List[str]]:
    a_text = " ".join(actions).lower()
    missing = []
    for item in must_include:
        if item.lower() not in a_text:
            missing.append(item)
    return (len(missing) == 0, missing)

def must_not_say_check(text: str, forbidden: List[str]) -> Tuple[bool, List[str]]:
    t = text.lower()
    found = [f for f in forbidden if f.lower() in t]
    return (len(found) == 0, found)

def run_case(case: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    ticket = case["ticket"]
    signals = case.get("signals", {})
    expect = case["expect"]

    output = triage(ticket=ticket, signals=signals)

    # 1) schema validation
    schema_ok = True
    schema_err = None
    try:
        validate(instance=output, schema=schema)
    except ValidationError as e:
        schema_ok = False
        schema_err = str(e)

    # 2) expectation checks
    checks = []
    def add_check(name: str, ok: bool, details: Any = None):
        checks.append({"name": name, "ok": ok, "details": details})

    add_check("category", output.get("category") == expect["category"], {"got": output.get("category"), "want": expect["category"]})
    add_check("priority_in", output.get("priority") in expect["priority_in"], {"got": output.get("priority"), "allowed": expect["priority_in"]})

    routing_contains = expect.get("routing_contains", [])
    if routing_contains:
        add_check("routing_contains", contains_any(output.get("routing",""), routing_contains), {"got": output.get("routing"), "need_any": routing_contains})
    else:
        add_check("routing_contains", True, None)

    min_conf = float(expect.get("min_confidence", 0))
    add_check("min_confidence", float(output.get("confidence", 0)) >= min_conf, {"got": output.get("confidence"), "min": min_conf})

    must_ask_about = expect.get("must_ask_about", [])
    if must_ask_about:
        ok, missing = must_ask_about_check(output.get("questions", []), must_ask_about)
        add_check("must_ask_about", ok, {"missing": missing})
    else:
        add_check("must_ask_about", True, None)

    must_include_actions = expect.get("must_include_actions", [])
    if must_include_actions:
        ok, missing = must_include_actions_check(output.get("actions", []), must_include_actions)
        add_check("must_include_actions", ok, {"missing": missing})
    else:
        add_check("must_include_actions", True, None)

    must_not_say = expect.get("must_not_say", [])
    if must_not_say:
        ok, found = must_not_say_check(output.get("customer_reply", "") + " " + output.get("summary",""), must_not_say)
        add_check("must_not_say", ok, {"found": found})
    else:
        add_check("must_not_say", True, None)

    passed = schema_ok and all(c["ok"] for c in checks)

    return {
        "id": case["id"],
        "passed": passed,
        "schema_ok": schema_ok,
        "schema_err": schema_err,
        "checks": checks,
        "output": output,
    }

def main():
    schema = load_schema(SCHEMA_PATH)
    cases = load_jsonl(DATASET_PATH)

    results = [run_case(c, schema) for c in cases]
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print(f"\nPrompt Regression Results: {passed}/{total} passed\n")

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['id']}")
        if not r["schema_ok"]:
            print(f"  - Schema error: {r['schema_err']}")
        for c in r["checks"]:
            if not c["ok"]:
                print(f"  - Check failed: {c['name']}  details={c['details']}")
        if status == "FAIL":
            print("  - Output snapshot:")
            print(json.dumps(r["output"], indent=2))
        print()

if __name__ == "__main__":
    main()
