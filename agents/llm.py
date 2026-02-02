from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

import requests

from .prompts import load_prompt, render

Category = str
Priority = str


class LocalStubLLM:
    """
    Deterministic, rules-based baseline used to:
      1) validate the multi-agent wiring
      2) make regression tests stable

    This must ALWAYS work so you have a stable baseline.
    """

    # -------- Public API --------

    def classify(self, ticket: Dict[str, Any], signals: Dict[str, Any]) -> Dict[str, Any]:
        title = self._lc(ticket.get("title"))
        desc = self._lc(ticket.get("description"))

        http_family = self._lc(signals.get("http_status_family"))
        symptom = self._lc(signals.get("symptom_type"))
        suspected = self._lc(signals.get("suspected_area"))
        scope = self._lc(signals.get("impact_scope"))

        security_risk = bool(signals.get("security_risk"))
        money_involved = bool(signals.get("money_involved"))
        error_count = signals.get("error_count")

        if self._is_security_issue(title, desc, security_risk):
            return self._cls("security", "P0", "Security", ["security", "account"], 0.80)

        if self._is_outage_explicit(title, desc, scope, http_family):
            return self._cls("outage", "P0", "SRE / On-Call", ["outage", "availability"], 0.80)

        if self._is_outage_error_spike(scope, symptom, error_count):
            return self._cls("outage", "P1", "SRE / On-Call", ["outage", "degraded"], 0.65)

        if self._is_billing(desc, money_involved):
            return self._cls("billing", "P2", "Billing", ["billing"], 0.70)

        if self._is_feature_request(title, desc, symptom):
            return self._cls("feature", "P3", "Product / PM", ["feature-request"], 0.65)

        if self._is_auth_issue(desc, suspected, symptom):
            return self._cls("account", "P1", "Auth", ["auth", "login"], 0.65)

        return self._cls("other", "P3", "Support", ["triage"], 0.55)

    def draft_reply(
        self,
        ticket: Dict[str, Any],
        classification: Dict[str, Any],
        signals: Dict[str, Any],
    ) -> Dict[str, Any]:
        cat: Category = classification["category"]
        title = (ticket.get("title") or "").strip()

        questions, actions = self._questions_and_actions(cat)

        # Outage ambiguity special case
        if cat == "outage" and self._is_ambiguous_200(ticket, signals):
            questions.insert(0, "Do you mean 200 error occurrences or HTTP 200 responses?")
            actions.insert(0, "Confirm status codes")
            actions.insert(0, "Check monitoring dashboards")

        summary = f"{cat.upper()} triage for: {title}" if title else f"{cat.upper()} triage"
        customer_reply = self._format_customer_reply(questions)

        return {
            "summary": summary,
            "customer_reply": customer_reply,
            "questions": questions,
            "actions": actions,
        }

    # -------- Helpers (belong to LocalStubLLM) --------

    @staticmethod
    def _lc(value: Any) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def _cls(category: Category, priority: Priority, routing: str, tags: List[str], confidence: float) -> Dict[str, Any]:
        return {
            "category": category,
            "priority": priority,
            "routing": routing,
            "tags": tags,
            "confidence": float(confidence),
        }

    @staticmethod
    def _is_security_issue(title: str, desc: str, security_risk: bool) -> bool:
        return (
            security_risk
            or "security" in title
            or "unknown location" in desc
            or "hacked" in desc
            or "account was accessed" in desc
            or "2fa" in desc
        )

    @staticmethod
    def _is_outage_explicit(title: str, desc: str, scope: str, http_family: str) -> bool:
        if scope != "many_users":
            return False
        return (
            http_family == "5xx"
            or "timeout" in desc
            or "502" in desc
            or "503" in desc
            or "app down" in title
            or "outage" in title
        )

    @staticmethod
    def _is_outage_error_spike(scope: str, symptom: str, error_count: Any) -> bool:
        if scope != "many_users":
            return False
        if symptom == "error_rate_spike":
            return True
        return isinstance(error_count, int) and error_count >= 50

    @staticmethod
    def _is_billing(desc: str, money_involved: bool) -> bool:
        return money_involved or ("charged" in desc) or ("refund" in desc)

    @staticmethod
    def _is_feature_request(title: str, desc: str, symptom: str) -> bool:
        return symptom == "feature_request" or ("feature" in title) or ("request" in desc) or ("add" in desc)

    @staticmethod
    def _is_auth_issue(desc: str, suspected: str, symptom: str) -> bool:
        return (
            symptom == "auth_failure"
            or suspected == "auth"
            or "login" in desc
            or "password" in desc
            or "reset" in desc
            or "403" in desc
        )

    @staticmethod
    def _questions_and_actions(category: Category) -> Tuple[List[str], List[str]]:
        if category == "account":
            return (
                [
                    "What email/username are you using?",
                    "Which device and browser/app version are you using?",
                    "What time (and timezone) did you try logging in?",
                ],
                [
                    "Check auth logs for 403 around the reported time",
                    "Verify password reset token flow and session invalidation",
                ],
            )

        if category == "billing":
            return (
                [
                    "Can you share the invoice ID(s) for the charges?",
                    "What are the dates of the charges?",
                    "What are the last 4 digits of the card (or payment method) used?",
                ],
                [
                    "Look up subscription and payment provider transactions",
                    "Confirm duplicate invoice and initiate refund workflow if applicable",
                ],
            )

        if category == "outage":
            return (
                [
                    "Are you seeing this across multiple regions or one region?",
                    "Do you have example request IDs/timestamps we can correlate?",
                ],
                [
                    "Check status page",
                    "Check error rate/latency dashboards",
                    "Open incident and page on-call if not already engaged",
                ],
            )

        if category == "feature":
            return (
                [
                    "What’s the main use case for CSV export (reporting, finance, sharing)?",
                    "Which fields do you need included in the export?",
                ],
                [
                    "Log feature request in backlog",
                    "Capture use case and expected output format",
                ],
            )

        if category == "security":
            return (
                [
                    "Do you recognize the location/device shown in the login activity?",
                    "When did you first notice the changes, and what changed?",
                ],
                [
                    "Force logout sessions (invalidate all active sessions)",
                    "Reset credentials and verify 2FA is enabled",
                    "Review audit logs for suspicious activity",
                ],
            )

        return (
            ["Can you share steps to reproduce and any screenshots or error messages?"],
            ["Collect details and route to the appropriate team"],
        )

    @staticmethod
    def _is_ambiguous_200(ticket: Dict[str, Any], signals: Dict[str, Any]) -> bool:
        desc = (ticket.get("description") or "").lower()
        ambiguity = signals.get("ambiguity_notes") or []
        return ("200 errors" in desc) or any("200" in str(a).lower() for a in ambiguity)

    @staticmethod
    def _format_customer_reply(questions: List[str]) -> str:
        return (
            "Thanks for reporting this. I’m going to help you get this resolved.\n\n"
            "To move quickly, could you confirm:\n- " + "\n- ".join(questions)
        )


class OllamaLLM:
    """
    Real local LLM via Ollama HTTP API.
    Uses versioned prompt files and returns strict JSON.
    """

    def __init__(self, model_cfg: Dict[str, Any], prompt_version: str = "triage/v1"):
        self.base_url = model_cfg.get("base_url", "http://localhost:11434").rstrip("/")
        self.model = model_cfg["model"]
        self.temperature = float(model_cfg.get("temperature", 0.2))
        self.top_p = float(model_cfg.get("top_p", 0.9))
        self.timeout = int(model_cfg.get("timeout_sec", 60))
        self.prompt_version = prompt_version

    def _generate(self, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature, "top_p": self.top_p},
        }
        r = requests.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["response"]

    @staticmethod
    def _json_only(text: str) -> Dict[str, Any]:
        text = text.strip()
        if text.startswith("{") and text.endswith("}"):
            return json.loads(text)

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])

        raise ValueError(f"Model did not return JSON. Got: {text[:200]}")

    def classify(self, ticket: Dict[str, Any], signals: Dict[str, Any]) -> Dict[str, Any]:
        tmpl = load_prompt(f"prompts/{self.prompt_version}/classify.md")
        prompt = render(
            tmpl,
            {
                "ticket_json": json.dumps(ticket, ensure_ascii=False),
                "signals_json": json.dumps(signals, ensure_ascii=False),
            },
        )
        return self._json_only(self._generate(prompt))

    def draft_reply(self, ticket: Dict[str, Any], classification: Dict[str, Any], signals: Dict[str, Any]) -> Dict[str, Any]:
        tmpl = load_prompt(f"prompts/{self.prompt_version}/respond.md")
        prompt = render(
            tmpl,
            {
                "ticket_json": json.dumps(ticket, ensure_ascii=False),
                "signals_json": json.dumps(signals, ensure_ascii=False),
                "classification_json": json.dumps(classification, ensure_ascii=False),
            },
        )
        return self._json_only(self._generate(prompt))
