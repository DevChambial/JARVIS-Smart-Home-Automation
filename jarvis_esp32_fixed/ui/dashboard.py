"""
JARVIS — Ultra-Futuristic ESP32 Dashboard
Cyberpunk / HUD aesthetic with:
  - Animated scanlines + grid background
  - Left sidebar navigation
  - Holographic sensor cards with live bars
  - Relay matrix with AUTO/MANUAL toggle per relay
  - AI status bar (Claude / rules source)
  - Live event log + alert panel (right)
  - IR door alert toast notification
  - Real-time clock + uptime + poll counter
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea,
    QFrame, QTextEdit, QStackedWidget, QCheckBox,
    QSizePolicy, QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, QDateTime, QPropertyAnimation,
    QEasingCurve, QRect
)
from PyQt6.QtGui import (
    QFont, QPainter, QColor, QPen, QLinearGradient,
    QBrush, QPalette
)
import math, time


# ══════════════════════════════════════════════════════════════
#  PALETTE
# ══════════════════════════════════════════════════════════════
C = {
    "bg":          "#050d1a",
    "bg2":         "#080f20",
    "bg3":         "#0a1428",
    "panel":       "#060e1e",
    "border":      "#0d2540",
    "border_hi":   "#1a4a7a",
    "cyan":        "#00d4ff",
    "cyan_dim":    "#0a3a50",
    "cyan_glow":   "rgba(0,212,255,0.15)",
    "purple":      "#a064ff",
    "orange":      "#ff6b35",
    "green":       "#39ff8a",
    "yellow":      "#f9c340",
    "red":         "#ff3b3b",
    "text":        "#c8f0ff",
    "text_dim":    "#4a7a9a",
    "text_muted":  "#1e4060",
}

SENSOR_ACCENT = {
    "temperature": C["cyan"],
    "humidity":    C["purple"],
    "light":       C["yellow"],
    "motion":      C["green"],
    "gas":         C["orange"],
    "pressure":    "#89dceb",
    "sound":       "#fab387",
    "distance":    "#94e2d5",
    "generic":     C["text_dim"],
}

SENSOR_ICON = {
    "temperature": "TEMP",
    "humidity":    "HUM",
    "light":       "LUX",
    "motion":      "IR",
    "gas":         "GAS",
    "pressure":    "BAR",
    "sound":       "SND",
    "distance":    "DST",
    "generic":     "SEN",
}

RELAY_ICONS = ["FAN", "BULB", "SW3", "SW4", "SW5", "SW6", "SW7", "SW8"]


# ══════════════════════════════════════════════════════════════
#  HELPER: HUD Label
# ══════════════════════════════════════════════════════════════
def hud_label(text, size=11, color=None, bold=False, spacing=2):
    lbl = QLabel(text)
    c = color or C["text_dim"]
    w = "600" if bold else "400"
    lbl.setStyleSheet(
        f"color: {c}; font-size: {size}px; font-weight: {w}; "
        f"letter-spacing: {spacing}px; background: transparent; border: none;"
    )
    return lbl


def section_line(title: str) -> QWidget:
    """Horizontal rule with label — like '── SENSORS ──────'"""
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 4, 0, 4)
    lay.setSpacing(8)

    lbl = hud_label(title, size=9, color=C["cyan_dim"] if True else C["text_dim"],
                    spacing=3)
    lbl.setStyleSheet(
        f"color: {C['text_muted']}; font-size: 9px; letter-spacing: 3px; "
        "background: transparent; border: none;"
    )
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {C['border']}; background: {C['border']};")
    line.setFixedHeight(1)

    lay.addWidget(lbl)
    lay.addWidget(line, stretch=1)
    return row


# ══════════════════════════════════════════════════════════════
#  CONNECT SCREEN
# ══════════════════════════════════════════════════════════════
class ConnectScreen(QWidget):
    connect_requested = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background: {C['bg']};")
        self._anim_val = 0.0
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(50)

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setFixedWidth(440)
        card.setStyleSheet(f"""
            QFrame {{
                background: {C['bg3']};
                border: 1px solid {C['border_hi']};
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(36, 32, 36, 32)
        cl.setSpacing(0)

        # Top accent bar
        bar = QFrame()
        bar.setFixedHeight(3)
        bar.setStyleSheet(f"background: {C['cyan']}; border: none;")
        cl.addWidget(bar)
        cl.addSpacing(20)

        # Logo
        logo = QLabel("JARVIS")
        logo.setStyleSheet(
            f"color: {C['cyan']}; font-size: 30px; font-weight: 700; "
            f"letter-spacing: 12px; background: transparent; border: none;"
        )
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sub = QLabel("ESP32 NEURAL AGENT")
        sub.setStyleSheet(
            f"color: {C['text_muted']}; font-size: 10px; letter-spacing: 6px; "
            "background: transparent; border: none;"
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cl.addWidget(logo)
        cl.addWidget(sub)
        cl.addSpacing(28)
        cl.addWidget(self._divider())
        cl.addSpacing(20)

        # IP
        ip_lbl = hud_label("ESP32 IP ADDRESS", size=9, color=C["text_dim"], spacing=2)
        self._ip = QLineEdit("192.168.43.120")
        self._style_input(self._ip)

        cl.addWidget(ip_lbl)
        cl.addSpacing(5)
        cl.addWidget(self._ip)
        cl.addSpacing(14)

        # Key
        key_lbl = hud_label("ANTHROPIC API KEY  (optional)", size=9, color=C["text_dim"], spacing=2)
        self._key = QLineEdit()
        self._key.setPlaceholderText("sk-ant-...")
        self._key.setEchoMode(QLineEdit.EchoMode.Password)
        self._style_input(self._key)

        cl.addWidget(key_lbl)
        cl.addSpacing(5)
        cl.addWidget(self._key)
        cl.addSpacing(24)

        # Button
        self._btn = QPushButton("INITIALIZE CONNECTION")
        self._btn.setFixedHeight(44)
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C['cyan']};
                border: 1px solid {C['cyan']};
                font-size: 12px; font-weight: 600;
                letter-spacing: 3px;
            }}
            QPushButton:hover {{
                background: {C['cyan_glow']};
                border: 1px solid {C['cyan']};
            }}
            QPushButton:disabled {{
                color: {C['text_muted']};
                border: 1px solid {C['border']};
                background: transparent;
            }}
        """)
        self._btn.clicked.connect(self._on_connect)
        self._ip.returnPressed.connect(self._on_connect)
        cl.addWidget(self._btn)
        cl.addSpacing(10)

        self._status = QLabel("")
        self._status.setStyleSheet(
            f"color: {C['orange']}; font-size: 11px; letter-spacing: 1px; "
            "background: transparent; border: none;"
        )
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self._status)

        outer.addWidget(card)

    def _divider(self):
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet(f"color: {C['border']}; background: {C['border']};")
        f.setFixedHeight(1)
        return f

    def _style_input(self, w):
        w.setFixedHeight(38)
        w.setStyleSheet(f"""
            QLineEdit {{
                background: {C['bg2']};
                color: {C['text']};
                border: 1px solid {C['border']};
                padding: 0 12px;
                font-size: 13px;
                letter-spacing: 1px;
            }}
            QLineEdit:focus {{
                border: 1px solid {C['cyan']};
            }}
        """)

    def _tick(self):
        self._anim_val = (self._anim_val + 0.05) % (2 * math.pi)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Grid
        p.setPen(QPen(QColor(0, 212, 255, 8), 1))
        step = 40
        for x in range(0, self.width(), step):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            p.drawLine(0, y, self.width(), y)

        # Scanlines
        p.setPen(QPen(QColor(0, 200, 255, 4), 1))
        for y in range(0, self.height(), 4):
            p.drawLine(0, y, self.width(), y)
        p.end()

    def _on_connect(self):
        ip  = self._ip.text().strip()
        key = self._key.text().strip()
        if not ip:
            self._status.setText("[ ERROR ] IP address required")
            return
        self._btn.setEnabled(False)
        self._btn.setText("SCANNING...")
        self._status.setText("")
        self.connect_requested.emit(ip, key)

    def set_error(self, msg):
        self._status.setText(f"[ FAIL ] {msg}")
        self._btn.setEnabled(True)
        self._btn.setText("INITIALIZE CONNECTION")


# ══════════════════════════════════════════════════════════════
#  SENSOR CARD
# ══════════════════════════════════════════════════════════════
class HUDSensorCard(QFrame):
    def __init__(self, sensor: dict, parent=None):
        super().__init__(parent)
        self.sensor_id   = sensor["id"]
        self.sensor_type = sensor.get("type", "generic")
        self._alert      = False
        self._history    = []
        self._bar_pct    = 0.0

        accent = SENSOR_ACCENT.get(self.sensor_type, C["text_dim"])
        tag    = SENSOR_ICON.get(self.sensor_type, "SEN")
        name   = sensor.get("name", self.sensor_type.title()).upper()

        self.setFixedSize(168, 118)
        self._accent = accent
        self._apply_style(False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        # Header row
        hrow = QHBoxLayout()
        tag_lbl = QLabel(tag)
        tag_lbl.setStyleSheet(
            f"color: {accent}; font-size: 9px; font-weight: 700; "
            f"letter-spacing: 2px; background: transparent; border: none;"
        )
        self._trend = QLabel("")
        self._trend.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 10px; "
            "background: transparent; border: none;"
        )
        hrow.addWidget(tag_lbl)
        hrow.addStretch()
        hrow.addWidget(self._trend)
        lay.addLayout(hrow)

        # Name
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 9px; letter-spacing: 1px; "
            "background: transparent; border: none;"
        )
        lay.addWidget(name_lbl)

        # Value
        self._val_lbl = QLabel("--")
        self._val_lbl.setStyleSheet(
            f"color: #e8f8ff; font-size: 24px; font-weight: 700; "
            "background: transparent; border: none;"
        )
        lay.addWidget(self._val_lbl)

        # Unit
        self._unit_lbl = QLabel(sensor.get("unit", ""))
        self._unit_lbl.setStyleSheet(
            f"color: {C['text_muted']}; font-size: 10px; letter-spacing: 1px; "
            "background: transparent; border: none;"
        )
        lay.addWidget(self._unit_lbl)
        lay.addStretch()

    def _apply_style(self, alert: bool):
        border = C["red"] if alert else self._accent
        dim_border = f"rgba({self._hex_to_rgb(self._accent)}, 0.12)"
        self.setStyleSheet(f"""
            QFrame {{
                background: {C['panel']};
                border: 1px solid {C['border'] if not alert else C['red']};
                border-top: 2px solid {border};
            }}
        """)

    def _hex_to_rgb(self, h):
        h = h.lstrip('#')
        return ','.join(str(int(h[i:i+2], 16)) for i in (0,2,4))

    def paintEvent(self, e):
        super().paintEvent(e)
        if self._bar_pct > 0:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            bar_w = int((self.width() - 24) * min(self._bar_pct, 1.0))
            # Bar track
            p.fillRect(12, self.height()-8, self.width()-24, 2,
                       QColor(255, 255, 255, 10))
            # Bar fill
            col = QColor(self._accent)
            p.fillRect(12, self.height()-8, bar_w, 2, col)
            p.end()

    def update_value(self, value, unit=""):
        self._history.append(value)
        if len(self._history) > 20:
            self._history.pop(0)

        self._val_lbl.setText(str(value))
        if unit:
            self._unit_lbl.setText(unit.upper())

        # Bar percent
        try:
            v = float(value)
            thresholds = {
                "temperature": 50,
                "humidity":    100,
                "light":       1000,
                "gas":         500,
                "pressure":    1050,
                "sound":       100,
                "distance":    200,
            }
            mx = thresholds.get(self.sensor_type, 100)
            self._bar_pct = v / mx
        except Exception:
            self._bar_pct = 0.5

        # Trend
        if len(self._history) >= 3:
            try:
                recent = [float(x) for x in self._history[-3:]]
                if recent[-1] > recent[0]:
                    self._trend.setText("▲")
                    self._trend.setStyleSheet(
                        f"color: {C['red']}; font-size: 11px; "
                        "background:transparent; border:none;"
                    )
                elif recent[-1] < recent[0]:
                    self._trend.setText("▼")
                    self._trend.setStyleSheet(
                        f"color: {C['green']}; font-size: 11px; "
                        "background:transparent; border:none;"
                    )
                else:
                    self._trend.setText("▶")
                    self._trend.setStyleSheet(
                        f"color: {C['text_muted']}; font-size: 11px; "
                        "background:transparent; border:none;"
                    )
            except Exception:
                pass

        self.update()

    def set_alert(self, active: bool):
        if active != self._alert:
            self._alert = active
            self._apply_style(active)


# ══════════════════════════════════════════════════════════════
#  RELAY CARD  (with AUTO / MANUAL toggle)
# ══════════════════════════════════════════════════════════════
class HUDRelayCard(QFrame):
    toggle_requested   = pyqtSignal(str, bool)
    mode_change        = pyqtSignal(str, bool)   # relay_id, is_manual

    def __init__(self, relay: dict, parent=None):
        super().__init__(parent)
        self.relay_id  = relay["id"]
        self._state    = relay.get("state", False)
        self._manual   = False   # default AUTO

        # FIX: relay id may be non-numeric string like "relay1", "R2", etc.
        try:
            raw_id = relay.get("id", "1")
            # Extract trailing digits if present (e.g. "relay3" → 3)
            import re as _re
            digits = _re.findall(r'\d+', str(raw_id))
            idx = int(digits[-1]) - 1 if digits else 0
        except Exception:
            idx = 0
        self._icon_txt = RELAY_ICONS[idx] if 0 <= idx < len(RELAY_ICONS) else "SW"

        self.setFixedSize(210, 110)
        self._apply_style()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        # Header
        hrow = QHBoxLayout()
        icon_lbl = QLabel(self._icon_txt)
        icon_lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 9px; font-weight:700; "
            f"letter-spacing:2px; background:transparent; border:none;"
        )
        name_lbl = QLabel(relay.get("name", "Relay").upper())
        name_lbl.setStyleSheet(
            f"color: {C['text']}; font-size: 11px; font-weight:600; "
            f"letter-spacing:1px; background:transparent; border:none;"
        )
        self._mode_badge = QLabel("AUTO")
        self._mode_badge.setFixedHeight(16)
        self._refresh_badge()
        hrow.addWidget(icon_lbl)
        hrow.addSpacing(6)
        hrow.addWidget(name_lbl)
        hrow.addStretch()
        hrow.addWidget(self._mode_badge)
        lay.addLayout(hrow)

        # State + toggle
        mid = QHBoxLayout()
        self._state_lbl = QLabel()
        self._state_lbl.setFixedWidth(60)
        self._refresh_state_lbl()

        self._toggle_btn = QPushButton()
        self._toggle_btn.setFixedSize(54, 24)
        self._refresh_toggle_btn()
        self._toggle_btn.clicked.connect(self._on_toggle)

        mid.addWidget(self._state_lbl)
        mid.addStretch()
        mid.addWidget(self._toggle_btn)
        lay.addLayout(mid)

        # Mode buttons
        mrow = QHBoxLayout()
        mrow.setSpacing(4)
        self._auto_btn   = QPushButton("AUTO")
        self._manual_btn = QPushButton("MANUAL")
        for b in [self._auto_btn, self._manual_btn]:
            b.setFixedHeight(22)
            b.setStyleSheet(self._mode_btn_style(False))
        self._auto_btn.setStyleSheet(self._mode_btn_style(True, "auto"))
        self._auto_btn.clicked.connect(lambda: self._set_mode(False))
        self._manual_btn.clicked.connect(lambda: self._set_mode(True))
        mrow.addWidget(self._auto_btn)
        mrow.addWidget(self._manual_btn)
        lay.addLayout(mrow)

    def _mode_btn_style(self, active=False, which=""):
        if active and which == "auto":
            return (f"QPushButton {{ background: rgba(0,212,255,0.12); "
                    f"border: 1px solid {C['cyan']}; color: {C['cyan']}; "
                    f"font-size: 9px; letter-spacing:2px; font-weight:600; }}")
        elif active and which == "manual":
            return (f"QPushButton {{ background: rgba(255,107,53,0.12); "
                    f"border: 1px solid {C['orange']}; color: {C['orange']}; "
                    f"font-size: 9px; letter-spacing:2px; font-weight:600; }}")
        else:
            return (f"QPushButton {{ background: transparent; "
                    f"border: 1px solid {C['border']}; color: {C['text_muted']}; "
                    f"font-size: 9px; letter-spacing:2px; }}"
                    f"QPushButton:hover {{ border: 1px solid {C['border_hi']}; "
                    f"color: {C['text_dim']}; }}")

    def _apply_style(self):
        border = C["green"] if self._state else C["border"]
        self.setStyleSheet(f"""
            QFrame {{
                background: {C['panel']};
                border: 1px solid {border};
            }}
        """)

    def _refresh_badge(self):
        if self._manual:
            self._mode_badge.setText("MANUAL")
            self._mode_badge.setStyleSheet(
                f"color: {C['orange']}; font-size: 8px; font-weight:700; "
                f"letter-spacing:1px; background: rgba(255,107,53,0.1); "
                f"border: 1px solid rgba(255,107,53,0.4); padding: 0 5px; "
                "border-radius:0px;"
            )
        else:
            self._mode_badge.setText("AUTO")
            self._mode_badge.setStyleSheet(
                f"color: {C['cyan']}; font-size: 8px; font-weight:700; "
                f"letter-spacing:1px; background: rgba(0,212,255,0.08); "
                f"border: 1px solid rgba(0,212,255,0.3); padding: 0 5px; "
                "border-radius:0px;"
            )

    def _refresh_state_lbl(self):
        if self._state:
            self._state_lbl.setText("◉  ON")
            self._state_lbl.setStyleSheet(
                f"color: {C['green']}; font-size: 12px; font-weight:700; "
                "background:transparent; border:none;"
            )
        else:
            self._state_lbl.setText("○  OFF")
            self._state_lbl.setStyleSheet(
                f"color: {C['text_muted']}; font-size: 12px; "
                "background:transparent; border:none;"
            )

    def _refresh_toggle_btn(self):
        if self._state:
            self._toggle_btn.setText("KILL")
            self._toggle_btn.setStyleSheet(
                f"QPushButton {{ background: rgba(255,59,59,0.15); "
                f"color: {C['red']}; border: 1px solid {C['red']}; "
                f"font-size: 9px; letter-spacing:2px; font-weight:700; }}"
                f"QPushButton:hover {{ background: rgba(255,59,59,0.25); }}"
            )
        else:
            self._toggle_btn.setText("ARM")
            self._toggle_btn.setStyleSheet(
                f"QPushButton {{ background: rgba(57,255,138,0.12); "
                f"color: {C['green']}; border: 1px solid {C['green']}; "
                f"font-size: 9px; letter-spacing:2px; font-weight:700; }}"
                f"QPushButton:hover {{ background: rgba(57,255,138,0.22); }}"
            )

    def _on_toggle(self):
        new = not self._state
        self._manual = True   # manual command → switch to MANUAL mode
        self.update_state(new)
        self._refresh_badge()
        self._refresh_mode_btns()
        self.toggle_requested.emit(self.relay_id, new)
        self.mode_change.emit(self.relay_id, True)   # notify mode changed to manual

    def _set_mode(self, manual: bool):
        self._manual = manual
        self._refresh_badge()
        self._refresh_mode_btns()
        self.mode_change.emit(self.relay_id, manual)

    def _refresh_mode_btns(self):
        self._auto_btn.setStyleSheet(
            self._mode_btn_style(not self._manual, "auto")
        )
        self._manual_btn.setStyleSheet(
            self._mode_btn_style(self._manual, "manual")
        )

    def update_state(self, state: bool):
        self._state = state
        self._apply_style()
        self._refresh_state_lbl()
        self._refresh_toggle_btn()
        self._refresh_badge()

    def set_mode_external(self, manual: bool):
        self._manual = manual
        self._refresh_badge()
        self._refresh_mode_btns()

    @property
    def is_manual(self):
        return self._manual


# ══════════════════════════════════════════════════════════════
#  IR ALERT TOAST
# ══════════════════════════════════════════════════════════════
class IRAlertToast(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 64)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C['bg3']};
                border: 1px solid {C['orange']};
                border-left: 3px solid {C['orange']};
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(2)

        top = QHBoxLayout()
        dot = QLabel("◉")
        dot.setStyleSheet(
            f"color: {C['orange']}; font-size: 10px; background:transparent; border:none;"
        )
        title = QLabel("DOOR ALERT")
        title.setStyleSheet(
            f"color: {C['orange']}; font-size: 10px; font-weight:700; "
            f"letter-spacing:3px; background:transparent; border:none;"
        )
        top.addWidget(dot)
        top.addSpacing(4)
        top.addWidget(title)
        top.addStretch()

        body = QLabel("Person detected at entry point")
        body.setStyleSheet(
            f"color: rgba(255,180,140,0.8); font-size: 11px; "
            "background:transparent; border:none;"
        )

        lay.addLayout(top)
        lay.addWidget(body)
        self.hide()

    def show_alert(self):
        self.show()
        self.raise_()
        QTimer.singleShot(5000, self.hide)


# ══════════════════════════════════════════════════════════════
#  LIVE DASHBOARD
# ══════════════════════════════════════════════════════════════
class LiveDashboard(QWidget):

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background: {C['bg']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── TOP BAR ───────────────────────────────────
        topbar = QFrame()
        topbar.setFixedHeight(46)
        topbar.setStyleSheet(f"""
            QFrame {{
                background: rgba(8,15,32,0.95);
                border-bottom: 1px solid {C['border']};
            }}
        """)
        tb_lay = QHBoxLayout(topbar)
        tb_lay.setContentsMargins(20, 0, 20, 0)

        logo = QLabel("JAR<span style='color:#ff6b35'>V</span>IS")
        logo.setTextFormat(Qt.TextFormat.RichText)
        logo.setStyleSheet(
            f"color: {C['cyan']}; font-size: 16px; font-weight: 700; "
            f"letter-spacing: 8px; background: transparent; border: none;"
        )

        self._ip_pill   = self._pill("192.168.1.1", C["cyan"])
        self._conn_pill = self._pill("● ONLINE",    C["green"])
        self._ai_pill   = self._pill("CLAUDE API",  C["purple"])

        self._clock_lbl = QLabel("--:--:--")
        self._clock_lbl.setStyleSheet(
            f"color: {C['text_muted']}; font-size: 12px; font-family: monospace; "
            "background: transparent; border: none;"
        )

        self._disconnect_btn = QPushButton("DISCONNECT")
        self._disconnect_btn.setFixedHeight(28)
        self._disconnect_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C['orange']};
                border: 1px solid rgba(255,107,53,0.4);
                font-size: 9px; letter-spacing: 2px; padding: 0 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,107,53,0.1);
                border-color: {C['orange']};
            }}
        """)

        self._voice_cb = QCheckBox("VOICE")
        self._voice_cb.setChecked(True)
        self._voice_cb.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 9px; letter-spacing: 2px; "
            "background: transparent;"
        )

        tb_lay.addWidget(logo)
        tb_lay.addSpacing(16)
        tb_lay.addWidget(self._conn_pill)
        tb_lay.addWidget(self._ip_pill)
        tb_lay.addWidget(self._ai_pill)
        tb_lay.addStretch()
        tb_lay.addWidget(self._clock_lbl)
        tb_lay.addSpacing(12)
        tb_lay.addWidget(self._voice_cb)
        tb_lay.addSpacing(8)
        tb_lay.addWidget(self._disconnect_btn)
        root.addWidget(topbar)

        # ── AI BAR ────────────────────────────────────
        ai_bar = QFrame()
        ai_bar.setFixedHeight(40)
        ai_bar.setStyleSheet(f"""
            QFrame {{
                background: rgba(6,10,24,0.9);
                border-bottom: 1px solid {C['border']};
            }}
        """)
        ai_lay = QHBoxLayout(ai_bar)
        ai_lay.setContentsMargins(20, 0, 20, 0)

        ai_tag = QLabel("AI")
        ai_tag.setFixedWidth(24)
        ai_tag.setStyleSheet(
            f"color: {C['purple']}; font-size: 9px; font-weight:700; "
            f"letter-spacing:2px; background:transparent; border:none;"
        )

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"color: {C['border']}; background: {C['border']};")

        self._ai_lbl = QLabel("Initializing neural analysis...")
        self._ai_lbl.setStyleSheet(
            f"color: {C['text']}; font-size: 12px; letter-spacing:0px; "
            "background:transparent; border:none;"
        )
        self._source_lbl = QLabel("")
        self._source_lbl.setStyleSheet(
            f"color: {C['text_muted']}; font-size: 9px; letter-spacing:2px; "
            "background:transparent; border:none;"
        )

        ai_lay.addWidget(ai_tag)
        ai_lay.addSpacing(8)
        ai_lay.addWidget(sep)
        ai_lay.addSpacing(10)
        ai_lay.addWidget(self._ai_lbl, stretch=1)
        ai_lay.addWidget(self._source_lbl)
        root.addWidget(ai_bar)

        # ── MAIN ROW (sidebar + content + right panel) ─
        main_row = QHBoxLayout()
        main_row.setSpacing(0)
        main_row.setContentsMargins(0, 0, 0, 0)

        # Left sidebar
        main_row.addWidget(self._build_sidebar())

        # Center content
        main_row.addWidget(self._build_center(), stretch=1)

        # Right panel
        main_row.addWidget(self._build_right())

        root.addLayout(main_row)

        # Clock timer
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick_clock)
        self._timer.start(1000)
        self._start_ts = time.time()
        self._poll_count = 0

    # ── SIDEBAR ───────────────────────────────────────
    def _build_sidebar(self):
        sb = QFrame()
        sb.setFixedWidth(190)
        sb.setStyleSheet(f"""
            QFrame {{
                background: {C['panel']};
                border-right: 1px solid {C['border']};
            }}
        """)
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(0)

        def nav_item(icon, label, active=False):
            btn = QPushButton(f"  {icon}  {label}")
            btn.setFixedHeight(36)
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(0,212,255,0.08);
                        border: none;
                        border-left: 2px solid {C['cyan']};
                        color: {C['cyan']};
                        font-size: 11px; letter-spacing:1px;
                        text-align: left; padding-left: 12px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        border: none;
                        border-left: 2px solid transparent;
                        color: {C['text_muted']};
                        font-size: 11px; letter-spacing:1px;
                        text-align: left; padding-left: 12px;
                    }}
                    QPushButton:hover {{
                        background: rgba(0,212,255,0.04);
                        color: {C['text_dim']};
                    }}
                """)
            return btn

        def section_lbl(t):
            l = QLabel(t)
            l.setStyleSheet(
                f"color: {C['text_muted']}; font-size: 8px; letter-spacing:3px; "
                "background:transparent; border:none; padding-left:16px;"
            )
            l.setFixedHeight(24)
            return l

        lay.addWidget(section_lbl("NAVIGATION"))
        lay.addWidget(nav_item("◈", "DASHBOARD", True))
        lay.addWidget(nav_item("◫", "SENSORS"))
        lay.addWidget(nav_item("⊞", "RELAYS"))
        lay.addWidget(nav_item("◎", "AI CONSOLE"))
        lay.addWidget(nav_item("▤", "HISTORY"))
        lay.addSpacing(16)

        lay.addWidget(section_lbl("GLOBAL CONTROL"))
        self._all_auto_btn = nav_item("↺", "ALL AUTO")
        self._all_manual_btn = nav_item("⊟", "ALL MANUAL")
        lay.addWidget(self._all_auto_btn)
        lay.addWidget(self._all_manual_btn)
        lay.addSpacing(16)

        lay.addWidget(section_lbl("SYSTEM"))
        self._uptime_lbl = QLabel("00:00:00")
        self._uptime_lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 18px; font-family:monospace; "
            "background:transparent; border:none; padding-left:16px;"
        )
        uptime_title = QLabel("UPTIME")
        uptime_title.setStyleSheet(
            f"color: {C['text_muted']}; font-size: 8px; letter-spacing:2px; "
            "background:transparent; border:none; padding-left:16px;"
        )
        lay.addWidget(uptime_title)
        lay.addWidget(self._uptime_lbl)
        lay.addSpacing(8)

        self._poll_lbl = QLabel("POLLS:  0")
        self._poll_lbl.setStyleSheet(
            f"color: {C['text_muted']}; font-size: 10px; letter-spacing:1px; "
            "background:transparent; border:none; padding-left:16px;"
        )
        lay.addWidget(self._poll_lbl)
        lay.addStretch()
        return sb

    # ── CENTER ────────────────────────────────────────
    def _build_center(self):
        w = QWidget()
        w.setStyleSheet(f"background: {C['bg']};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        lay.addWidget(section_line("SENSOR ARRAY"))

        # Sensor scroll area
        sensor_scroll = QScrollArea()
        sensor_scroll.setWidgetResizable(True)
        sensor_scroll.setFixedHeight(140)
        sensor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sensor_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sensor_scroll.setStyleSheet("border: none; background: transparent;")

        self._sensor_container = QWidget()
        self._sensor_container.setStyleSheet("background: transparent;")
        self.sensor_layout = QHBoxLayout(self._sensor_container)
        self.sensor_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.sensor_layout.setSpacing(8)
        self.sensor_layout.setContentsMargins(0, 0, 0, 0)
        sensor_scroll.setWidget(self._sensor_container)
        lay.addWidget(sensor_scroll)

        lay.addWidget(section_line("RELAY CONTROL MATRIX"))

        # Relay scroll area
        relay_scroll = QScrollArea()
        relay_scroll.setWidgetResizable(True)
        relay_scroll.setFixedHeight(130)
        relay_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        relay_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        relay_scroll.setStyleSheet("border: none; background: transparent;")

        self._relay_container = QWidget()
        self._relay_container.setStyleSheet("background: transparent;")
        self.relay_layout = QHBoxLayout(self._relay_container)
        self.relay_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.relay_layout.setSpacing(8)
        self.relay_layout.setContentsMargins(0, 0, 0, 0)
        relay_scroll.setWidget(self._relay_container)
        lay.addWidget(relay_scroll)

        lay.addWidget(section_line("ALERT LOG"))

        self._alert_log = QTextEdit()
        self._alert_log.setReadOnly(True)
        self._alert_log.setStyleSheet(f"""
            QTextEdit {{
                background: {C['panel']};
                color: {C['orange']};
                border: 1px solid {C['border']};
                font-size: 11px;
                font-family: monospace;
                padding: 8px;
            }}
        """)
        lay.addWidget(self._alert_log, stretch=1)
        return w

    # ── RIGHT PANEL ───────────────────────────────────
    def _build_right(self):
        rp = QFrame()
        rp.setFixedWidth(210)
        rp.setStyleSheet(f"""
            QFrame {{
                background: {C['panel']};
                border-left: 1px solid {C['border']};
            }}
        """)
        lay = QVBoxLayout(rp)
        lay.setContentsMargins(14, 16, 14, 16)
        lay.setSpacing(14)

        def rp_title(t):
            l = QLabel(t)
            l.setStyleSheet(
                f"color: {C['text_muted']}; font-size: 8px; letter-spacing:3px; "
                "background:transparent; border:none;"
            )
            return l

        # Active alerts
        lay.addWidget(rp_title("ACTIVE ALERTS"))
        self._alert_panel = QVBoxLayout()
        self._alert_panel.setSpacing(4)
        no_alert = QLabel("No active alerts")
        no_alert.setStyleSheet(
            f"color: {C['text_muted']}; font-size: 11px; "
            "background:transparent; border:none;"
        )
        self._alert_panel.addWidget(no_alert)
        lay.addLayout(self._alert_panel)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {C['border']}; background:{C['border']};")
        div.setFixedHeight(1)
        lay.addWidget(div)

        # Device info
        lay.addWidget(rp_title("DEVICE INFO"))
        self._info_ip  = self._info_row("IP", "—")
        self._info_ssid = self._info_row("SSID", "MUSIC-NB")
        self._info_sens = self._info_row("SENSORS", "—")
        self._info_rel  = self._info_row("RELAYS", "—")
        for w in [self._info_ip, self._info_ssid,
                  self._info_sens, self._info_rel]:
            lay.addWidget(w)

        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet(f"color: {C['border']}; background:{C['border']};")
        div2.setFixedHeight(1)
        lay.addWidget(div2)

        lay.addWidget(rp_title("POLL GRAPH"))
        self._mini_graph = MiniGraph()
        self._mini_graph.setFixedHeight(60)
        lay.addWidget(self._mini_graph)

        lay.addStretch()
        return rp

    def _info_row(self, label, val):
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {C['text_muted']}; font-size: 10px; letter-spacing:1px; "
            "background:transparent; border:none;"
        )
        val_lbl = QLabel(val)
        val_lbl.setObjectName(f"info_{label}")
        val_lbl.setStyleSheet(
            f"color: {C['text']}; font-size: 11px; "
            "background:transparent; border:none;"
        )
        h.addWidget(lbl)
        h.addStretch()
        h.addWidget(val_lbl)
        return w

    def _pill(self, text, color):
        l = QLabel(text)
        l.setStyleSheet(
            f"color: {color}; font-size: 9px; letter-spacing:1px; "
            f"background: transparent; "
            f"border: 1px solid rgba({self._hex_rgb(color)},0.3); "
            f"padding: 2px 8px; border-radius:0px;"
        )
        return l

    def _hex_rgb(self, h):
        h = h.lstrip('#')
        return ','.join(str(int(h[i:i+2], 16)) for i in (0,2,4))

    # ── CLOCK ─────────────────────────────────────────
    def _tick_clock(self):
        self._clock_lbl.setText(QDateTime.currentDateTime().toString("hh:mm:ss"))
        elapsed = int(time.time() - self._start_ts)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        self._uptime_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")

    # ── PUBLIC UPDATES ────────────────────────────────
    def set_header(self, ip: str, schema: dict):
        self._ip_pill.setText(ip)
        ns = len(schema.get("sensors", []))
        nr = len(schema.get("relays",  []))
        for w in self._info_ip.findChildren(QLabel):
            if w.objectName() == "info_IP":
                w.setText(ip)
        for w in self._info_sens.findChildren(QLabel):
            if w.objectName() == "info_SENSORS":
                w.setText(str(ns))
        for w in self._info_rel.findChildren(QLabel):
            if w.objectName() == "info_RELAYS":
                w.setText(str(nr))

    def set_connected(self, ok: bool):
        self._conn_pill.setText("● ONLINE" if ok else "● OFFLINE")
        c = C["green"] if ok else C["red"]
        self._conn_pill.setStyleSheet(
            f"color: {c}; font-size: 9px; letter-spacing:1px; "
            f"background: transparent; "
            f"border: 1px solid rgba({self._hex_rgb(c)},0.3); "
            "padding: 2px 8px;"
        )

    def update_ai(self, result: dict):
        suggestions = result.get("suggestions", [])
        alerts      = result.get("alerts",      [])
        source      = result.get("source",      "rules").upper()

        self._ai_lbl.setText(suggestions[0] if suggestions else "All systems nominal.")
        self._source_lbl.setText(f"VIA {source}")

        # Poll counter + graph
        self._poll_count += 1
        self._poll_lbl.setText(f"POLLS:  {self._poll_count}")
        self._mini_graph.add_point(len(alerts))

        # Alert log
        if alerts:
            existing = self._alert_log.toPlainText()
            ts = QDateTime.currentDateTime().toString("hh:mm:ss")
            new = "\n".join(f"[{ts}] {a}" for a in alerts)
            self._alert_log.setPlainText(
                new + ("\n" + existing if existing else "")
            )

        # Alert panel (right)
        while self._alert_panel.count():
            item = self._alert_panel.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if alerts:
            for a in alerts[:4]:
                f = QFrame()
                f.setStyleSheet(
                    f"background: rgba(255,59,59,0.07); "
                    f"border-left: 2px solid {C['red']}; border: none; "
                    f"border-left: 2px solid {C['red']};"
                )
                fl = QVBoxLayout(f)
                fl.setContentsMargins(8, 6, 8, 6)
                al = QLabel(a)
                al.setStyleSheet(
                    f"color: rgba(255,180,180,0.9); font-size: 10px; "
                    "background:transparent; border:none;"
                )
                al.setWordWrap(True)
                fl.addWidget(al)
                self._alert_panel.addWidget(f)
        else:
            nl = QLabel("All clear")
            nl.setStyleSheet(
                f"color: {C['green']}; font-size: 11px; "
                "background:transparent; border:none;"
            )
            self._alert_panel.addWidget(nl)

    def show_ir_toast(self):
        # Find or create toast
        if not hasattr(self, '_toast'):
            self._toast = IRAlertToast(self)
        self._toast.move(self.width() - 510, self.height() - 90)
        self._toast.show_alert()

    @property
    def voice_enabled(self):
        return self._voice_cb.isChecked()

    @property
    def disconnect_btn(self):
        return self._disconnect_btn

    @property
    def all_auto_btn(self):
        return self._all_auto_btn

    @property
    def all_manual_btn(self):
        return self._all_manual_btn

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setPen(QPen(QColor(0, 212, 255, 6), 1))
        step = 40
        for x in range(0, self.width(), step):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            p.drawLine(0, y, self.width(), y)
        p.setPen(QPen(QColor(0, 200, 255, 3), 1))
        for y in range(0, self.height(), 4):
            p.drawLine(0, y, self.width(), y)
        p.end()


# ══════════════════════════════════════════════════════════════
#  MINI POLL GRAPH (right panel)
# ══════════════════════════════════════════════════════════════
class MiniGraph(QWidget):
    def __init__(self):
        super().__init__()
        self._points = []
        self.setStyleSheet(f"background: {C['panel']}; border: 1px solid {C['border']};")

    def add_point(self, v: float):
        self._points.append(v)
        if len(self._points) > 40:
            self._points.pop(0)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        if not self._points:
            return
        mx = max(self._points) if max(self._points) > 0 else 1
        pts = self._points
        step = w / max(len(pts) - 1, 1)
        pen = QPen(QColor(C["cyan"]), 1)
        p.setPen(pen)
        for i in range(1, len(pts)):
            x1 = (i-1) * step
            x2 =  i    * step
            y1 = h - (pts[i-1] / mx) * (h - 4) - 2
            y2 = h - (pts[i]   / mx) * (h - 4) - 2
            p.drawLine(int(x1), int(y1), int(x2), int(y2))
        p.end()


# ══════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════
class Dashboard(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS — ESP32 Neural Agent")
        self.setMinimumSize(1100, 680)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self.connect_screen = ConnectScreen()
        self.live           = LiveDashboard()

        self._stack.addWidget(self.connect_screen)
        self._stack.addWidget(self.live)

        self.show_connect()

    def show_connect(self):
        self._stack.setCurrentWidget(self.connect_screen)

    def show_live(self):
        self._stack.setCurrentWidget(self.live)
