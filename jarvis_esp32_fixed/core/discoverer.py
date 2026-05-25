"""
Universal ESP32 Schema Discoverer
----------------------------------
Probes the ESP32 at various common endpoints and attempts to auto-discover
what sensors, relays, or other controls it exposes — regardless of firmware.
"""

import requests
from typing import Optional


# Common endpoints many ESP32 firmwares use
PROBE_ENDPOINTS = [
    "/data",
    "/sensors",
    "/status",
    "/json",
    "/api/data",
    "/api/sensors",
    "/api/status",
    "/all",
    "/info",
    "/",
]

RELAY_CONTROL_PATTERNS = [
    "/relay/{id}/{state}",      # JARVIS ESP32 firmware (primary)
    "/relay?id={id}&state={state}",
    "/control/{id}/{state}",
    "/gpio/{id}/{state}",
    "/switch/{id}/{state}",
    "/toggle/{id}",
]


class ESP32Discoverer:
    """
    Probes an ESP32 to discover:
      - Which HTTP endpoint returns sensor/relay data
      - What sensors exist and their types
      - What relays/outputs exist
      - How to control relays (URL pattern)
    """

    def __init__(self, ip: str, timeout: int = 4):
        self.ip = ip
        self.base_url = f"http://{ip}"
        self.timeout = timeout

        # Discovered after probe
        self.data_endpoint: Optional[str] = None
        self.control_pattern: Optional[str] = None
        self.schema: Optional[dict] = None

    # ─────────────────────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────────────────────

    def discover(self) -> dict:
        """
        Run full discovery. Returns a schema dict:
        {
            "data_endpoint": "/data",
            "control_pattern": "/relay/{id}/{state}",
            "sensors": [...],
            "relays":  [...],
            "raw":     {...}   # raw JSON from device
        }
        """
        raw = self._find_data_endpoint()
        if raw is None:
            return {"error": "Could not connect to ESP32. Check IP and Wi-Fi."}

        schema = self._parse_schema(raw)
        schema["data_endpoint"]   = self.data_endpoint
        schema["control_pattern"] = self._detect_control_pattern()
        schema["raw"] = raw

        self.schema = schema
        return schema

    def get_live_data(self) -> Optional[dict]:
        """Poll the discovered endpoint for fresh data."""
        if not self.data_endpoint:
            return None
        try:
            r = requests.get(
                f"{self.base_url}{self.data_endpoint}",
                timeout=self.timeout
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[Discoverer] Poll error: {e}")
            return None

    def parse_schema(self, raw: dict) -> dict:
        """Public wrapper for schema parsing — used by controller during polling."""
        return self._parse_schema(raw)

    def send_command(self, relay_id: str, state: bool) -> bool:
        """
        Send ON/OFF command to a relay.
        Tries ALL known patterns until one returns 200, then caches it.
        Supports both numeric (1/0) and string (on/off) state formats.
        """
        state_str = "1" if state else "0"
        on_off    = "on" if state else "off"

        # Cached pattern goes first, then all others
        patterns_to_try = []
        if self.control_pattern:
            patterns_to_try.append(self.control_pattern)
        for p in RELAY_CONTROL_PATTERNS:
            if p not in patterns_to_try:
                patterns_to_try.append(p)

        for pattern in patterns_to_try:
            # Each pattern gets tried with both state formats (1/0 and on/off)
            for sv in [state_str, on_off]:
                try:
                    url = self.base_url + pattern.format(id=relay_id, state=sv)
                except (KeyError, IndexError):
                    continue
                print(f"[Discoverer] Trying: {url}")
                try:
                    r = requests.get(url, timeout=self.timeout)
                    print(f"[Discoverer] Response: {r.status_code}")
                    if r.status_code == 200:
                        self.control_pattern = pattern
                        print(f"[Discoverer] Working pattern cached: {pattern}")
                        return True
                except Exception as e:
                    print(f"[Discoverer] Failed: {e}")
                    continue

        print(f"[Discoverer] No pattern worked for relay {relay_id}")
        return False

    # ─────────────────────────────────────────────────────────
    # PRIVATE
    # ─────────────────────────────────────────────────────────

    def _find_data_endpoint(self) -> Optional[dict]:
        for ep in PROBE_ENDPOINTS:
            try:
                r = requests.get(
                    f"{self.base_url}{ep}",
                    timeout=self.timeout
                )
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict) and len(data) > 0:
                        self.data_endpoint = ep
                        print(f"[Discoverer] Found data at {ep}")
                        return data
            except Exception:
                continue
        return None

    def _parse_schema(self, raw: dict) -> dict:
        """
        Intelligently parse any JSON structure into normalized sensors + relays.
        Handles flat dicts, nested lists, and mixed structures.
        """
        sensors = []
        relays  = []

        # Strategy 1: explicit "sensors" / "relays" keys (ideal format)
        if "sensors" in raw:
            for s in raw["sensors"]:
                sensors.append(self._normalize_sensor(s))

        if "relays" in raw or "outputs" in raw or "switches" in raw:
            key = next(k for k in ("relays", "outputs", "switches") if k in raw)
            for r in raw[key]:
                relays.append(self._normalize_relay(r))

        # Strategy 2: flat key-value pairs (e.g. {"temp": 32, "humidity": 75})
        if not sensors and not relays:
            for key, value in raw.items():
                inferred = self._infer_type(key, value)
                if inferred == "relay":
                    relays.append({
                        "id":    key,
                        "name":  key.replace("_", " ").title(),
                        "state": bool(value),
                    })
                else:
                    sensors.append({
                        "id":    key,
                        "name":  key.replace("_", " ").title(),
                        "type":  inferred,
                        "value": value,
                        "unit":  self._infer_unit(inferred),
                    })

        # Strategy 3: mixed nested dicts
        if not sensors:
            for key, val in raw.items():
                if isinstance(val, dict):
                    t = self._infer_type(key, val.get("value", 0))
                    sensors.append({
                        "id":    key,
                        "name":  val.get("name", key.replace("_", " ").title()),
                        "type":  t,
                        "value": val.get("value", val.get("v", 0)),
                        "unit":  val.get("unit", self._infer_unit(t)),
                    })

        return {"sensors": sensors, "relays": relays}

    def _normalize_sensor(self, s: dict) -> dict:
        t = s.get("type", self._infer_type(
            s.get("name", s.get("id", "")),
            s.get("value", 0)
        ))
        return {
            "id":    s.get("id",    s.get("name", "sensor")),
            "name":  s.get("name",  t.title()),
            "type":  t,
            "value": s.get("value", 0),
            "unit":  s.get("unit",  self._infer_unit(t)),
        }

    def _normalize_relay(self, r: dict) -> dict:
        raw_id = r.get("id", r.get("name", "relay"))
        # ESP32 sends id as String("1"), ensure it stays a clean string
        relay_id = str(raw_id).strip()
        return {
            "id":    relay_id,
            "name":  r.get("name",  f"Relay {relay_id}"),
            "state": bool(r.get("state", r.get("value", False))),
            "mode":  r.get("mode", "auto"),   # carry mode from ESP32 JSON
        }

    def _infer_type(self, key: str, value) -> str:
        key_lower = key.lower()
        if any(k in key_lower for k in ("temp", "temperature")):
            return "temperature"
        if any(k in key_lower for k in ("hum", "humidity", "moisture")):
            return "humidity"
        if any(k in key_lower for k in ("light", "lux", "brightness", "ldr")):
            return "light"
        if any(k in key_lower for k in ("motion", "pir", "presence")):
            return "motion"
        if any(k in key_lower for k in ("gas", "co2", "smoke", "air", "aqi", "mq")):
            return "gas"
        if any(k in key_lower for k in ("pressure", "baro")):
            return "pressure"
        if any(k in key_lower for k in ("sound", "noise", "db")):
            return "sound"
        if any(k in key_lower for k in ("distance", "ultra", "sonar")):
            return "distance"
        if any(k in key_lower for k in ("relay", "switch", "output", "fan",
                                         "light_sw", "pump", "motor")):
            return "relay"
        if isinstance(value, bool):
            return "relay"
        return "generic"

    def _infer_unit(self, sensor_type: str) -> str:
        return {
            "temperature": "°C",
            "humidity":    "%",
            "light":       "lux",
            "gas":         "ppm",
            "pressure":    "hPa",
            "sound":       "dB",
            "distance":    "cm",
            "motion":      "",
            "generic":     "",
        }.get(sensor_type, "")

    def _detect_control_pattern(self) -> str:
        """
        Probe real relay IDs (1-4) with state=0 (OFF — safe, no change if already off).
        Tries each pattern with id=1 first. Caches and returns the first 200 response.
        Falls back to /relay/{id}/{state} which matches JARVIS ESP32 firmware.
        """
        for pattern in RELAY_CONTROL_PATTERNS:
            if "{state}" not in pattern:
                continue
            # Try with real id=1, state=0 (turn OFF relay 1 — safe test)
            try:
                url = self.base_url + pattern.format(id="1", state="0")
            except (KeyError, IndexError):
                continue
            try:
                r = requests.get(url, timeout=2)
                if r.status_code == 200:
                    print(f"[Discoverer] Control pattern found: {pattern}")
                    return pattern
            except Exception:
                continue
        # JARVIS ESP32 firmware default
        print("[Discoverer] Using default control pattern: /relay/{id}/{state}")
        return "/relay/{id}/{state}"
