"""
JARVIS ESP32 Universal Agent — main.py
Updated for futuristic HUD dashboard with AUTO/MANUAL relay modes.
"""

import sys
from PyQt6.QtWidgets import QApplication

from ui.dashboard     import Dashboard
from ui.sensor_card   import HUDSensorCard
from ui.relay_card    import HUDRelayCard
from agent.controller import AgentController


app = QApplication(sys.argv)
app.setStyle("Fusion")

dashboard = Dashboard()
agent     = AgentController()

sensor_cards: dict[str, HUDSensorCard] = {}
relay_cards:  dict[str, HUDRelayCard]  = {}


# ── Slots ──────────────────────────────────────────────────────

def on_connect_requested(ip: str, api_key: str):
    agent.connect(ip, api_key)


def on_discovery_done(schema: dict):
    dashboard.show_live()
    dashboard.live.set_header(agent.discoverer.ip, schema)
    for sensor in schema.get("sensors", []):
        _ensure_sensor_card(sensor)
    for relay in schema.get("relays", []):
        _ensure_relay_card(relay)
    agent.start_polling()


def on_discovery_failed(error: str):
    dashboard.connect_screen.set_error(error)


def on_data_updated(parsed: dict):
    dashboard.live.set_connected(True)
    for sensor in parsed.get("sensors", []):
        card = _ensure_sensor_card(sensor)
        card.update_value(sensor["value"], sensor.get("unit", ""))
        # IR toast
        if sensor.get("type") == "motion" and str(sensor.get("value","")).lower() == "detected":
            dashboard.live.show_ir_toast()
    for relay in parsed.get("relays", []):
        card = _ensure_relay_card(relay)
        # Sync mode from ESP32 (esp32 is the source of truth for mode)
        esp_manual = relay.get("mode", "auto") == "manual"
        if esp_manual != card.is_manual:
            card.set_mode_external(esp_manual)
        # Only update state if relay is in AUTO mode on ESP32
        if not esp_manual:
            card.update_state(relay["state"])


def on_ai_result(result: dict):
    dashboard.live.update_ai(result)
    agent.voice_enabled = dashboard.live.voice_enabled
    alert_text = " ".join(result.get("alerts", [])).lower()
    for sid, card in sensor_cards.items():
        card.set_alert(card.sensor_type in alert_text)


def on_relay_toggle(relay_id: str, state: bool):
    # Mark card as manual immediately so the next auto-poll doesn't override
    if relay_id in relay_cards:
        relay_cards[relay_id].set_mode_external(True)
    agent.send_relay_command(relay_id, state)


def on_mode_change(relay_id: str, is_manual: bool):
    # Send mode command to ESP32
    # /mode/{id}/auto  or  /mode/{id}/manual
    import threading
    def _send():
        import requests
        mode_str = "manual" if is_manual else "auto"
        try:
            requests.get(
                f"http://{agent.discoverer.ip}/mode/{relay_id}/{mode_str}",
                timeout=3
            )
        except Exception as e:
            print(f"[Mode] Command failed: {e}")
    threading.Thread(target=_send, daemon=True).start()


def on_all_auto():
    for card in relay_cards.values():
        card.set_mode_external(False)
    import threading, requests
    def _send():
        try:
            requests.get(f"http://{agent.discoverer.ip}/mode/auto", timeout=3)
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()


def on_all_manual():
    for card in relay_cards.values():
        card.set_mode_external(True)
    import threading, requests
    def _send():
        try:
            requests.get(f"http://{agent.discoverer.ip}/mode/manual", timeout=3)
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()


def on_disconnect():
    agent.disconnect()
    sensor_cards.clear()
    relay_cards.clear()
    for layout in [dashboard.live.sensor_layout, dashboard.live.relay_layout]:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    dashboard.show_connect()


# ── Helpers ────────────────────────────────────────────────────

def _ensure_sensor_card(sensor: dict) -> HUDSensorCard:
    sid = sensor["id"]
    if sid not in sensor_cards:
        card = HUDSensorCard(sensor)
        sensor_cards[sid] = card
        dashboard.live.sensor_layout.addWidget(card)
    return sensor_cards[sid]


def _ensure_relay_card(relay: dict) -> HUDRelayCard:
    rid = relay["id"]
    if rid not in relay_cards:
        card = HUDRelayCard(relay)
        relay_cards[rid] = card
        card.toggle_requested.connect(on_relay_toggle)
        card.mode_change.connect(on_mode_change)
        dashboard.live.relay_layout.addWidget(card)
    return relay_cards[rid]


# ── Wire signals ───────────────────────────────────────────────
dashboard.connect_screen.connect_requested.connect(on_connect_requested)
agent.discovery_done.connect(on_discovery_done)
agent.discovery_failed.connect(on_discovery_failed)
agent.data_updated.connect(on_data_updated)
agent.ai_result.connect(on_ai_result)
dashboard.live.disconnect_btn.clicked.connect(on_disconnect)
dashboard.live.all_auto_btn.clicked.connect(on_all_auto)
dashboard.live.all_manual_btn.clicked.connect(on_all_manual)

# ── Launch ─────────────────────────────────────────────────────
dashboard.show()
sys.exit(app.exec())
