"""
Universal Agent Controller
---------------------------
Orchestrates: Discovery → Live Polling → AI Analysis → Voice → UI Update
Runs entirely from a single IP address.
"""

import threading
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from core.discoverer import ESP32Discoverer
from core.ai_engine  import AIEngine
from voice.tts       import VoiceEngine


class AgentController(QObject):
    """
    Signals emitted to the UI thread:
    """
    discovery_done   = pyqtSignal(dict)          # schema dict
    discovery_failed = pyqtSignal(str)           # error message
    data_updated     = pyqtSignal(dict)          # parsed sensors+relays
    ai_result        = pyqtSignal(dict)          # suggestions+alerts+source

    POLL_INTERVAL_MS = 2000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.discoverer: ESP32Discoverer = None
        self.ai        : AIEngine        = None
        self.voice     : VoiceEngine     = None
        self._timer    : QTimer          = None
        self._schema   : dict            = {}
        self.voice_enabled = True

    # ─────────────────────────────────────────────────
    # CONNECT
    # ─────────────────────────────────────────────────
    def connect(self, ip: str, api_key: str = ""):
        """Called from UI. Runs discovery in background thread."""
        self.discoverer = ESP32Discoverer(ip)
        self.ai         = AIEngine(api_key=api_key or None)
        self.voice      = VoiceEngine(enabled=True)

        thread = threading.Thread(
            target=self._run_discovery,
            daemon=True
        )
        thread.start()

    def _run_discovery(self):
        schema = self.discoverer.discover()
        if "error" in schema:
            self.discovery_failed.emit(schema["error"])
        else:
            self._schema = schema
            self.discovery_done.emit(schema)

    # ─────────────────────────────────────────────────
    # START POLLING
    # ─────────────────────────────────────────────────
    def start_polling(self):
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll)
        self._timer.start(self.POLL_INTERVAL_MS)

    def stop_polling(self):
        if self._timer:
            self._timer.stop()
            self._timer = None

    # ─────────────────────────────────────────────────
    # POLL
    # ─────────────────────────────────────────────────
    def _poll(self):
        # Guard against disconnect race condition
        if self.discoverer is None:
            return

        raw = self.discoverer.get_live_data()
        if not raw:
            return

        # Use public parse_schema method (not private _parse_schema)
        parsed = self.discoverer.parse_schema(raw)
        self.data_updated.emit(parsed)

        # AI analysis in background (non-blocking)
        threading.Thread(
            target=self._run_ai,
            args=(parsed,),
            daemon=True
        ).start()

    def _run_ai(self, parsed: dict):
        # Guard against disconnect during async execution
        if self.ai is None:
            return

        result = self.ai.analyze(parsed)
        self.ai_result.emit(result)

        # Voice — read voice_enabled at call time for up-to-date value
        if self.voice_enabled and self.voice:
            alerts = result.get("alerts", [])
            suggestions = result.get("suggestions", [])
            if alerts:
                self.voice.speak_alerts(alerts)
            elif suggestions and suggestions[0] != "✅ All systems normal.":
                self.voice.speak_suggestions(suggestions)

    # ─────────────────────────────────────────────────
    # RELAY CONTROL
    # ─────────────────────────────────────────────────
    def send_relay_command(self, relay_id: str, state: bool):
        if self.discoverer is None:
            return
        threading.Thread(
            target=self.discoverer.send_command,
            args=(relay_id, state),
            daemon=True
        ).start()

    # ─────────────────────────────────────────────────
    # DISCONNECT
    # ─────────────────────────────────────────────────
    def disconnect(self):
        self.stop_polling()
        self.discoverer = None
        self.ai         = None
        self.voice      = None
