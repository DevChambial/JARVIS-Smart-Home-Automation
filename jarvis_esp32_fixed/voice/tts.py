"""
Voice Engine — gTTS + winsound (Windows built-in)
No pygame needed at all. Works on Windows out of the box.
Falls back to silent mode if gTTS also unavailable.
"""

import threading
import tempfile
import os
import sys

try:
    from gtts import gTTS
    _gtts_ok = True
except Exception:
    _gtts_ok = False


def _play_mp3(path: str):
    """Play mp3 without pygame — uses OS native player."""
    if sys.platform == "win32":
        # Windows: convert mp3 -> wav via audioop-free method, play with winsound
        try:
            import winsound
            # winsound can't play mp3 directly, use Windows Media via subprocess
            import subprocess
            # PowerShell one-liner — plays and waits
            cmd = (
                f'powershell -c "(New-Object Media.SoundPlayer).Stop(); '
                f'Add-Type -AssemblyName presentationCore; '
                f'$p = New-Object System.Windows.Media.MediaPlayer; '
                f'$p.Open([uri]\\"{path}\\"); $p.Play(); '
                f'Start-Sleep -s 5; $p.Stop()"'
            )
            subprocess.run(cmd, shell=True, timeout=15,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            # Absolute fallback: just open with default app (non-blocking)
            try:
                os.startfile(path)
                import time; time.sleep(4)
            except Exception:
                pass
    elif sys.platform == "darwin":
        import subprocess
        subprocess.run(["afplay", path], timeout=15)
    else:
        # Linux
        import subprocess
        for player in ["mpg123", "mpg321", "ffplay", "aplay"]:
            try:
                subprocess.run([player, "-q", path], timeout=15,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
            except Exception:
                continue


class VoiceEngine:

    def __init__(self, lang: str = "en", enabled: bool = True):
        self.lang    = lang
        self.enabled = enabled and _gtts_ok
        self._lock   = threading.Lock()
        self._last   = ""

        if enabled and not _gtts_ok:
            print("[VoiceEngine] gTTS not found — voice disabled. "
                  "Run: pip install gtts")
        elif enabled:
            print("[VoiceEngine] Ready (no pygame needed)")

    def speak(self, text: str, force: bool = False):
        if not self.enabled:
            return
        if not force and text == self._last:
            return
        self._last = text
        threading.Thread(target=self._run, args=(text,), daemon=True).start()

    def speak_alerts(self, alerts: list):
        if alerts:
            self.speak(". ".join(alerts), force=True)

    def speak_suggestions(self, suggestions: list):
        if suggestions:
            self.speak(suggestions[0])

    def set_enabled(self, v: bool):
        self.enabled = v and _gtts_ok

    def _run(self, text: str):
        with self._lock:
            tmp_path = None
            try:
                tts = gTTS(text=text, lang=self.lang, slow=False)
                with tempfile.NamedTemporaryFile(
                    suffix=".mp3", delete=False
                ) as f:
                    tmp_path = f.name
                tts.save(tmp_path)
                _play_mp3(tmp_path)
            except Exception as e:
                print(f"[VoiceEngine] Error: {e}")
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
