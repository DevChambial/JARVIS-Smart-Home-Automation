/*
 * ============================================================
 *  JARVIS Smart Home — ESP32 Firmware
 *  WiFi : MUSIC-NB (open, no password)
 *
 *  Sensors:
 *    DHT22  → GPIO 4   (Temperature + Humidity)
 *    LDR    → GPIO 34  (Light level, analog)
 *    IR     → GPIO 15  (Door person detection)
 *
 *  Relays (Active-LOW module — LOW=ON, HIGH=OFF):
 *    Relay 1 → GPIO 26  (Fan)
 *    Relay 2 → GPIO 27  (Light Bulb)
 *    Relay 3 → GPIO 25  (Spare)
 *    Relay 4 → GPIO 33  (Spare)
 *
 *  HTTP Endpoints:
 *    GET /data               → Full JSON (sensors + relays + mode)
 *    GET /relay/{id}/{state} → Manual relay control (1=ON, 0=OFF)
 *    GET /mode/auto          → Switch ALL to AUTO mode
 *    GET /mode/manual        → Switch ALL to MANUAL mode
 *    GET /mode/{id}/auto     → Per-relay AUTO
 *    GET /mode/{id}/manual   → Per-relay MANUAL
 *
 *  AUTO  mode : relay controlled by sensor thresholds
 *  MANUAL mode: relay controlled only by /relay/{id}/{state}
 * ============================================================
 */

#include <WiFi.h>
#include <WebServer.h>
#include <DHT.h>
#include <ArduinoJson.h>

// ── WiFi ─────────────────────────────────────────────────────
const char* SSID     = "MUSIC-NB";
const char* PASSWORD = "";            // Open network — no password

// ── Pin Definitions ──────────────────────────────────────────
#define DHT_PIN           4
#define DHT_TYPE          DHT22
#define LDR_PIN           34          // Analog input
#define IR_PIN            15          // Digital input

#define RELAY_FAN         26          // Relay 1
#define RELAY_LIGHT       27          // Relay 2
#define RELAY_SPARE3      25          // Relay 3
#define RELAY_SPARE4      33          // Relay 4

// ── Thresholds ───────────────────────────────────────────────
#define TEMP_THRESHOLD    28.0        // °C  → Fan ON above this
#define LDR_DARK_VALUE    2000        // ADC → Light ON above this (0=bright,4095=dark)

// ── Global Objects ───────────────────────────────────────────
DHT       dht(DHT_PIN, DHT_TYPE);
WebServer server(80);

// ── Per-Relay State ──────────────────────────────────────────
//  index 1-4  (index 0 unused)
bool relayState[5]  = {false, false, false, false, false};
bool manualMode[5]  = {false, false, false, false, false};
// manualMode[i] = true  → MANUAL  (only /relay command moves it)
// manualMode[i] = false → AUTO    (sensor logic moves it every poll)

// ── Cached sensor readings (updated each /data call) ─────────
float lastTemp = 0;
float lastHum  = 0;
int   lastLDR  = 0;
bool  lastIR   = false;

// ─────────────────────────────────────────────────────────────
//  HELPERS
// ─────────────────────────────────────────────────────────────
int relayPin(int id) {
  switch (id) {
    case 1: return RELAY_FAN;
    case 2: return RELAY_LIGHT;
    case 3: return RELAY_SPARE3;
    case 4: return RELAY_SPARE4;
    default: return -1;
  }
}

const char* relayName(int id) {
  switch (id) {
    case 1: return "Fan";
    case 2: return "Light Bulb";
    case 3: return "Spare Relay 3";
    case 4: return "Spare Relay 4";
    default: return "Unknown";
  }
}

void setRelay(int id, bool state) {
  int pin = relayPin(id);
  if (pin < 0) return;
  relayState[id] = state;
  digitalWrite(pin, state ? LOW : HIGH);   // Active-LOW
  Serial.printf("[Relay %d - %s] %s\n", id, relayName(id), state ? "ON" : "OFF");
}

// ─────────────────────────────────────────────────────────────
//  AUTO CONTROL LOGIC  (runs every /data poll)
// ─────────────────────────────────────────────────────────────
void runAutoLogic() {
  // Relay 1 — Fan: AUTO if temp > 28°C
  if (!manualMode[1]) {
    if (!isnan(lastTemp)) {
      setRelay(1, lastTemp > TEMP_THRESHOLD);
    }
  }

  // Relay 2 — Light: AUTO if dark (LDR > threshold)
  if (!manualMode[2]) {
    setRelay(2, lastLDR > LDR_DARK_VALUE);
  }

  // Relay 3 & 4 — Spare: no auto logic, stays as-is unless manually set
  // Add your own logic here if needed
}

// ─────────────────────────────────────────────────────────────
//  READ SENSORS
// ─────────────────────────────────────────────────────────────
void readSensors() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (!isnan(t)) lastTemp = t;
  if (!isnan(h)) lastHum  = h;
  lastLDR = analogRead(LDR_PIN);
  lastIR  = (digitalRead(IR_PIN) == LOW);   // IR module: LOW = person detected
}

// ─────────────────────────────────────────────────────────────
//  BUILD JSON  — format JARVIS agent reads
// ─────────────────────────────────────────────────────────────
String buildJSON() {
  readSensors();
  runAutoLogic();

  StaticJsonDocument<768> doc;

  // ── Sensors ────────────────────────────────────────────
  JsonArray sensors = doc.createNestedArray("sensors");

  JsonObject s1 = sensors.createNestedObject();
  s1["id"]    = "temperature";
  s1["name"]  = "Temperature";
  s1["type"]  = "temperature";
  s1["value"] = round(lastTemp * 10.0) / 10.0;
  s1["unit"]  = "°C";

  JsonObject s2 = sensors.createNestedObject();
  s2["id"]    = "humidity";
  s2["name"]  = "Humidity";
  s2["type"]  = "humidity";
  s2["value"] = round(lastHum * 10.0) / 10.0;
  s2["unit"]  = "%";

  JsonObject s3 = sensors.createNestedObject();
  s3["id"]    = "light";
  s3["name"]  = "Light Level";
  s3["type"]  = "light";
  // Map ADC (0-4095) to lux-like value (inverted: high ADC = dark = low lux)
  s3["value"] = map(lastLDR, 0, 4095, 1000, 0);
  s3["unit"]  = "lux";

  JsonObject s4 = sensors.createNestedObject();
  s4["id"]    = "door_ir";
  s4["name"]  = "Door IR";
  s4["type"]  = "motion";
  s4["value"] = lastIR ? "detected" : "clear";
  s4["unit"]  = "";

  // ── Relays ─────────────────────────────────────────────
  JsonArray relays = doc.createNestedArray("relays");
  for (int i = 1; i <= 4; i++) {
    JsonObject r = relays.createNestedObject();
    r["id"]     = String(i);
    r["name"]   = relayName(i);
    r["state"]  = relayState[i];
    r["mode"]   = manualMode[i] ? "manual" : "auto";
  }

  // ── IR Alert ───────────────────────────────────────────
  if (lastIR) {
    doc["alert"] = "Person detected at door!";
  }

  String output;
  serializeJson(doc, output);
  return output;
}

// ─────────────────────────────────────────────────────────────
//  HTTP HANDLERS
// ─────────────────────────────────────────────────────────────

// GET /data
void handleData() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", buildJSON());
}

// GET /relay/{id}/{state}
// Always works — if relay is in AUTO mode, it switches to MANUAL automatically
void handleRelay() {
  String uri = server.uri();
  // uri = "/relay/1/1"
  int s1 = uri.indexOf('/', 1);
  int s2 = uri.indexOf('/', s1 + 1);

  if (s1 < 0 || s2 < 0) {
    server.send(400, "text/plain", "Bad URL. Use /relay/{id}/{state}");
    return;
  }

  int id    = uri.substring(s1 + 1, s2).toInt();
  int state = uri.substring(s2 + 1).toInt();

  if (id < 1 || id > 4) {
    server.send(400, "text/plain", "Relay id must be 1-4");
    return;
  }

  // Sending a relay command auto-switches that relay to MANUAL mode
  manualMode[id] = true;
  setRelay(id, state == 1);

  StaticJsonDocument<128> resp;
  resp["relay"]  = id;
  resp["name"]   = relayName(id);
  resp["state"]  = relayState[id];
  resp["mode"]   = "manual";
  String out;
  serializeJson(resp, out);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", out);
}

// GET /mode/auto     → all relays AUTO
// GET /mode/manual   → all relays MANUAL
void handleGlobalMode() {
  String uri  = server.uri();          // "/mode/auto" or "/mode/manual"
  String mode = uri.substring(6);      // "auto" or "manual"
  bool   isManual = (mode == "manual");

  for (int i = 1; i <= 4; i++) {
    manualMode[i] = isManual;
  }

  Serial.printf("[Mode] ALL relays → %s\n", isManual ? "MANUAL" : "AUTO");

  StaticJsonDocument<64> resp;
  resp["mode"] = isManual ? "manual" : "auto";
  resp["applied_to"] = "all";
  String out;
  serializeJson(resp, out);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", out);
}

// GET /mode/{id}/auto    → per-relay AUTO
// GET /mode/{id}/manual  → per-relay MANUAL
void handleRelayMode() {
  String uri = server.uri();           // "/mode/1/auto"
  int s1 = uri.indexOf('/', 1);        // after "mode"
  int s2 = uri.indexOf('/', s1 + 1);

  if (s1 < 0 || s2 < 0) {
    server.send(400, "text/plain", "Use /mode/{id}/auto or /mode/{id}/manual");
    return;
  }

  int    id       = uri.substring(s1 + 1, s2).toInt();
  String modeStr  = uri.substring(s2 + 1);   // "auto" or "manual"
  bool   isManual = (modeStr == "manual");

  if (id < 1 || id > 4) {
    server.send(400, "text/plain", "Relay id must be 1-4");
    return;
  }

  manualMode[id] = isManual;
  Serial.printf("[Mode] Relay %d → %s\n", id, isManual ? "MANUAL" : "AUTO");

  StaticJsonDocument<128> resp;
  resp["relay"] = id;
  resp["name"]  = relayName(id);
  resp["mode"]  = isManual ? "manual" : "auto";
  String out;
  serializeJson(resp, out);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", out);
}

// GET /  — Info page
void handleRoot() {
  String ip = WiFi.localIP().toString();
  String html =
    "<html><body style='font-family:sans-serif;padding:20px'>"
    "<h2>⚡ JARVIS Smart Home ESP32</h2>"
    "<p><b>IP:</b> " + ip + "</p>"
    "<hr>"
    "<h3>Endpoints</h3>"
    "<ul>"
    "<li><a href='/data'>/data</a> — Live JSON (sensors + relays)</li>"
    "<li>/relay/{id}/{state} — Set relay (1=ON, 0=OFF)</li>"
    "<li>/mode/auto — All relays → AUTO</li>"
    "<li>/mode/manual — All relays → MANUAL</li>"
    "<li>/mode/{id}/auto — Single relay → AUTO</li>"
    "<li>/mode/{id}/manual — Single relay → MANUAL</li>"
    "</ul>"
    "<hr>"
    "<h3>Relay Map</h3>"
    "<ul>"
    "<li>Relay 1 → Fan (AUTO: temp &gt; 28°C)</li>"
    "<li>Relay 2 → Light Bulb (AUTO: dark)</li>"
    "<li>Relay 3 → Spare</li>"
    "<li>Relay 4 → Spare</li>"
    "</ul>"
    "</body></html>";
  server.send(200, "text/html", html);
}

void handleNotFound() {
  server.send(404, "text/plain", "Not found");
}

// ─────────────────────────────────────────────────────────────
//  SETUP
// ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== JARVIS Smart Home ESP32 Booting ===");

  // Relay pins — all OFF at boot (HIGH = OFF for active-low)
  int relayPins[] = {RELAY_FAN, RELAY_LIGHT, RELAY_SPARE3, RELAY_SPARE4};
  for (int p : relayPins) {
    pinMode(p, OUTPUT);
    digitalWrite(p, HIGH);
  }

  // Sensor pins
  pinMode(IR_PIN, INPUT_PULLUP);
  dht.begin();
  delay(2000);   // DHT22 warmup

  // WiFi connect (open network)
  Serial.printf("Connecting to WiFi: %s\n", SSID);
  WiFi.begin(SSID, PASSWORD);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 30) {
    delay(500);
    Serial.print(".");
    tries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n✅ Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    Serial.println("Open JARVIS agent → enter this IP → Connect & Discover");
  } else {
    Serial.println("\n❌ WiFi failed. Check SSID and restart.");
  }

  // Register routes
  server.on("/",        handleRoot);
  server.on("/data",    handleData);

  // Relay control: /relay/1/1, /relay/2/0, etc.
  server.onNotFound([&]() {
    String uri = server.uri();
    if (uri.startsWith("/relay/")) {
      handleRelay();
    }
    else if (uri == "/mode/auto" || uri == "/mode/manual") {
      handleGlobalMode();
    }
    else if (uri.startsWith("/mode/") && uri.indexOf('/', 6) > 0) {
      handleRelayMode();
    }
    else {
      handleNotFound();
    }
  });

  server.begin();
  Serial.println("HTTP server started on port 80");
}

// ─────────────────────────────────────────────────────────────
//  LOOP
// ─────────────────────────────────────────────────────────────
void loop() {
  server.handleClient();

  // IR alert print (every 3 seconds if detected)
  static unsigned long lastPrint = 0;
  if (millis() - lastPrint > 3000) {
    lastPrint = millis();
    if (lastIR) {
      Serial.println("🚨 ALERT: Person detected at door!");
    }
  }
}
