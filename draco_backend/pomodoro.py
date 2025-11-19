import threading
import time
from typing import Callable, Dict, Optional, List, Any

"""
Pomodoro subsystem for Draco.

Public API (via PomodoroManager instance returned by create_pomodoro_manager):
- start(seconds: int, mode: str)
- stop()
- pause()
- resume()
- reset()
- get_status() -> dict
- on_tick(callback: Callable[[Dict[str, Any]], None])
"""


class PomodoroState:
    def __init__(self):
        self.active: bool = False
        self.mode: Optional[str] = None  # "pomodoro", "break", "mini", "focus"
        self.total_seconds: int = 0
        self.remaining_seconds: int = 0
        self.paused: bool = False
        self.started_at: Optional[float] = None


class PomodoroManager:
    def __init__(
        self,
        socketio,
        gamestate: Optional[Dict[str, Any]] = None,
        logger=None,
    ):
        self._socketio = socketio
        self._gamestate = gamestate or {}
        self._logger = logger
        self.state = PomodoroState()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._tick_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._thread.start()

    def _log(self, msg: str):
        if self._logger:
            try:
                self._logger.debug(msg)
            except Exception:
                pass

    def _emit(self, key: str, payload: dict):
        try:
            if self._socketio:
                self._socketio.emit(key, payload)
        except Exception as e:
            self._log(f"Emit error in PomodoroManager: {e}")

    def on_tick(self, callback: Callable[[Dict[str, Any]], None]):
        if callable(callback):
            self._tick_callbacks.append(callback)

    def _notify_tick(self, payload: Dict[str, Any]):
        for cb in list(self._tick_callbacks):
            try:
                cb(payload)
            except Exception as e:
                self._log(f"Pomodoro tick callback error: {e}")

    def start(self, seconds: int, mode: str):
        with self._lock:
            self.state.active = True
            self.state.mode = mode
            self.state.total_seconds = max(1, int(seconds))
            self.state.remaining_seconds = self.state.total_seconds
            self.state.paused = False
            self.state.started_at = time.time()
        self._emit(
            "pomodoro_started",
            {
                "mode": mode,
                "total_seconds": self.state.total_seconds,
            },
        )
        self._emit("play_beep", {"kind": "pomodoro_start"})

    def stop(self):
        with self._lock:
            self.state = PomodoroState()
        self._emit("pomodoro_stopped", {})

    def pause(self):
        with self._lock:
            if self.state.active:
                self.state.paused = True
        self._emit("pomodoro_paused", {})

    def resume(self):
        with self._lock:
            if self.state.active and self.state.paused:
                self.state.paused = False
        self._emit("pomodoro_resumed", {})

    def reset(self):
        with self._lock:
            if self.state.total_seconds > 0:
                total = self.state.total_seconds
                mode = self.state.mode or "pomodoro"
            else:
                total = 25 * 60
                mode = "pomodoro"
            self.state.active = True
            self.state.mode = mode
            self.state.remaining_seconds = total
            self.state.paused = False
            self.state.started_at = time.time()
        self._emit(
            "pomodoro_reset",
            {
                "mode": mode,
                "total_seconds": total,
            },
        )

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            st = self.state
            return {
                "active": st.active,
                "mode": st.mode,
                "total_seconds": st.total_seconds,
                "remaining_seconds": st.remaining_seconds,
                "paused": st.paused,
            }

    def _loop(self):
        bump_daily = None
        if isinstance(self._gamestate, dict):
            bump_daily = self._gamestate.get("bump_daily")

        while True:
            time.sleep(1)

            with self._lock:
                st = self.state
                if not st.active or st.paused or st.remaining_seconds <= 0:
                    continue
                st.remaining_seconds -= 1
                remaining = st.remaining_seconds
                total = st.total_seconds or 1
                mode = st.mode or "pomodoro"

            # emit tick update outside lock
            progress = max(0.0, min(1.0, 1.0 - (remaining / float(total))))
            payload = {
                "mode": mode,
                "remaining_seconds": remaining,
                "total_seconds": total,
                "progress": progress,
            }
            self._emit("pomodoro_tick", payload)
            self._emit("play_beep", {"kind": "tick"})
            self._notify_tick(payload)

            if remaining <= 0:
                final_text = "Pomodoro done! ☕ All gone! Take a short break 😎"
                self._emit("draco_response", {"text": final_text})
                self._emit("pomodoro_done", {"mode": mode})
                self._emit("play_beep", {"kind": "pomodoro_end"})
                if callable(bump_daily):
                    try:
                        bump_daily("pomodoro")
                    except Exception as e:
                        self._log(f"bump_daily error: {e}")
                with self._lock:
                    self.state = PomodoroState()


def create_pomodoro_manager(socketio, gamestate: Optional[Dict[str, Any]] = None, logger=None) -> PomodoroManager:
    """Factory to create a PomodoroManager bound to Socket.IO and gamestate hooks."""
    return PomodoroManager(socketio=socketio, gamestate=gamestate, logger=logger)
