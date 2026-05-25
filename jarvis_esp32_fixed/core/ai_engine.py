"""
Hybrid AI Engine
-----------------
Fast rule-based checks run first.
If anomalies are found OR complexity threshold hit → escalate to Claude API.
"""

import json
import os
from typing import Optional
import anthropic


# ── Thresholds (tweak as needed) ──────────────────────────────────────────
RULES = {
    "temperature": {"high": 35, "low": 10,  "unit": "°C"},
    "humidity":    {"high": 80, "low": 20,  "unit": "%"},
    "gas":         {"high": 300, "low": 0,  "unit": "ppm"},
    "light":       {"low": 500,             "unit": "lux"},
    "sound":       {"high": 85,             "unit": "dB"},
    "pressure":    {"high": 1020, "low": 980, "unit": "hPa"},
    "distance":    {"low": 10,              "unit": "cm"},
}


class AIEngine:

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = anthropic.Anthropic(api_key=key) if key else None
        self._history = []   # rolling sensor history for trend analysis

    # ─────────────────────────────────────────────────────────
    def analyze(self, parsed: dict) -> dict:
        """
        Returns:
        {
            "suggestions": ["...", "..."],
            "alerts":      ["...", "..."],   # urgent items
            "source":      "rules" | "claude"
        }
        """
        sensors = parsed.get("sensors", [])
        self._history.append(sensors)
        if len(self._history) > 30:
            self._history.pop(0)

        rule_alerts, rule_suggestions = self._run_rules(sensors)

        # FIX: history % 10 == 0 was True on first call (0 % 10 == 0).
        # Now requires history to be non-empty before periodic Claude escalation.
        use_claude = (
            self.client is not None and
            (len(rule_alerts) > 0 or
             (len(self._history) > 0 and len(self._history) % 10 == 0))
        )

        if use_claude:
            try:
                claude_result = self._ask_claude(parsed, rule_alerts)
                return {
                    "suggestions": claude_result.get("suggestions", rule_suggestions),
                    "alerts":      claude_result.get("alerts",      rule_alerts),
                    "source":      "claude",
                }
            except Exception as e:
                print(f"[AIEngine] Claude API error: {e}")

        return {
            "suggestions": rule_suggestions if rule_suggestions else ["✅ All systems normal."],
            "alerts":      rule_alerts,
            "source":      "rules",
        }

    # ─────────────────────────────────────────────────────────
    # RULE ENGINE
    # ─────────────────────────────────────────────────────────
    def _run_rules(self, sensors: list):
        alerts = []
        suggestions = []

        for s in sensors:
            stype = s.get("type", "")
            value = s.get("value", 0)
            name  = s.get("name", stype)

            if stype not in RULES:
                continue

            rule = RULES[stype]

            if "high" in rule and isinstance(value, (int, float)) and value > rule["high"]:
                alerts.append(
                    f"⚠️ {name} is HIGH: {value}{rule['unit']} (limit: {rule['high']})"
                )
                suggestions.append(
                    self._suggest_action(stype, "high", value)
                )

            elif "low" in rule and isinstance(value, (int, float)) and value < rule["low"]:
                alerts.append(
                    f"⚠️ {name} is LOW: {value}{rule['unit']} (limit: {rule['low']})"
                )
                suggestions.append(
                    self._suggest_action(stype, "low", value)
                )

            # Motion
            if stype == "motion" and str(value).lower() in ("detected", "1", "true"):
                suggestions.append("🚶 Motion detected — someone is nearby.")

        return alerts, suggestions

    def _suggest_action(self, stype: str, direction: str, value) -> str:
        actions = {
            ("temperature", "high"): "🌡️ Turn ON AC or open windows to cool down.",
            ("temperature", "low"):  "🔥 Turn ON heater to warm up.",
            ("humidity",    "high"): "💧 Run dehumidifier or open ventilation.",
            ("humidity",    "low"):  "🌵 Use a humidifier.",
            ("gas",         "high"): "🚨 DANGER: High gas levels! Open windows immediately.",
            ("light",       "low"):  "💡 Room is dark — turn ON the lights.",
            ("sound",       "high"): "🔊 High noise levels detected.",
            ("distance",    "low"):  "📏 Object very close to sensor.",
        }
        return actions.get((stype, direction), f"⚡ {stype.title()} anomaly detected.")

    # ─────────────────────────────────────────────────────────
    # CLAUDE API
    # ─────────────────────────────────────────────────────────
    def _ask_claude(self, parsed: dict, rule_alerts: list) -> dict:
        sensors_summary = json.dumps(parsed.get("sensors", []), indent=2)
        relays_summary  = json.dumps(parsed.get("relays",  []), indent=2)
        alerts_summary  = "\n".join(rule_alerts) if rule_alerts else "None"

        prompt = f"""You are a smart IoT assistant monitoring an ESP32 device.

Current sensor readings:
{sensors_summary}

Current relay states:
{relays_summary}

Rule-based alerts already triggered:
{alerts_summary}

Analyze the data and respond ONLY with a JSON object like this (no markdown, no extra text):
{{
  "suggestions": ["short actionable suggestion 1", "suggestion 2"],
  "alerts": ["urgent alert 1 if any"]
}}

Keep suggestions short (max 12 words each). Be practical and specific to the sensor values."""

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = message.content[0].text.strip()
        # Strip markdown fences if present
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
