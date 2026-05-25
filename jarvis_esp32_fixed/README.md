# ⚡ JARVIS — Universal ESP32 AI Agent

> Just provide the IP address — the agent takes care of everything automatically.

---

## What Does It Do?

| Feature              | Details                                                                                                           |
| -------------------- | ----------------------------------------------------------------------------------------------------------------- |
| 🔍 Auto-Discovery    | Connect to any ESP32 device — sensors and relays are automatically detected                                       |
| 📊 Dynamic Dashboard | Any detected component (temperature, humidity, gas sensor, relay, etc.) automatically gets its own dashboard card |
| 🤖 Hybrid AI         | The rule engine and Claude API (claude-sonnet) work together for intelligent analysis                             |
| 🔊 Voice Support     | Speaks suggestions using Google TTS (can be enabled or disabled)                                                  |
| 🎛️ Relay Control    | Control relays directly from the dashboard                                                                        |

---

## Project Structure

```text
jarvis_esp32/
├── main.py                    ← Entry point
├── requirements.txt
├── agent/
│   └── controller.py          ← Master orchestrator
├── core/
│   ├── discoverer.py          ← Automatically probes ESP32 endpoints
│   └── ai_engine.py           ← Rules + Claude API
├── ui/
│   ├── dashboard.py           ← Connection screen + Live dashboard
│   ├── sensor_card.py         ← Dynamic sensor widget
│   └── relay_card.py          ← Relay toggle widget
└── voice/
    └── tts.py                 ← Google TTS engine
```

---

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python main.py
```

### 3. Connect

* Enter your ESP32 IP address in the IP field (example: `192.168.43.120`)
* Optionally enter your Anthropic API key for Claude AI integration
* Click **Connect & Discover** — the remaining process is fully automatic

---

## Expected JSON Formats for ESP32

The agent can handle almost any JSON structure, but the following formats are recommended.

### Format A — Recommended

```json
{
  "sensors": [
    {"id": "s1", "type": "temperature", "value": 32.5, "unit": "°C"},
    {"id": "s2", "type": "humidity", "value": 75, "unit": "%"}
  ],
  "relays": [
    {"id": "r1", "name": "Fan", "state": true}
  ]
}


---

## Notes

* **Claude AI** activates only during alerts or after every 10th polling cycle
* **Voice suggestions** are spoken only for new or updated recommendations — repeated suggestions are ignored
* Clicking a **relay toggle button** immediately sends the command to the ESP32
* **Trend arrows** (↑ ↓ →) update live with sensor values to indicate increasing, decreasing, or stable readings
