import os
import json
import time
import datetime
import threading
from typing import Optional

# These will be set from main.py so behavior stays consistent
emit_to_ui = None
speak = None


def safe_write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def safe_read_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


class NotesManager:
    def __init__(self, path):
        self.path = path
        self.notes = safe_read_json(self.path, [])

    def add(self, text):
        nid = int(time.time() * 1000)
        self.notes.append({"id": nid, "text": text, "created": datetime.datetime.now().isoformat()})
        safe_write_json(self.path, self.notes)
        return nid

    def delete(self, nid):
        self.notes = [n for n in self.notes if n["id"] != nid]
        safe_write_json(self.path, self.notes)

    def list(self):
        return list(self.notes)


class ReminderManager:
    def __init__(self, path):
        self.path = path
        self.reminders = safe_read_json(self.path, [])
        self._start_loop()

    def add(self, text, when: datetime.datetime):
        rid = int(time.time() * 1000)
        self.reminders.append({"id": rid, "text": text, "at": when.isoformat()})
        safe_write_json(self.path, self.reminders)
        return rid

    def remove(self, rid):
        self.reminders = [r for r in self.reminders if r["id"] != rid]
        safe_write_json(self.path, self.reminders)

    def list(self):
        return list(self.reminders)

    def _start_loop(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        global speak, emit_to_ui
        while True:
            now = datetime.datetime.now()

            to_fire = []
            for r in list(self.reminders):
                try:
                    at = datetime.datetime.fromisoformat(r["at"])
                    if now >= at:
                        to_fire.append(r)
                except Exception:
                    continue
            for r in to_fire:
                msg = f"Reminder: {r['text']}"
                if speak:
                    speak(msg)
                try:
                    if emit_to_ui:
                        emit_to_ui("draco_response", {"text": msg})
                        emit_to_ui("reminder_fired", {"text": r["text"]})
                        emit_to_ui("play_beep", {"kind": "reminder"})
                except Exception:
                    pass
                self.remove(r["id"])
            time.sleep(6)


class PomodoroState:
    def __init__(self):
        self.active = False
        self.mode = None  # "pomodoro", "break", "mini", "focus"
        self.total_seconds = 0
        self.remaining_seconds = 0
        self.paused = False
        self.started_at = None


class PomodoroManager:
    def __init__(self):
        self.state = PomodoroState()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def start(self, seconds: int, mode: str):
        with self._lock:
            self.state.active = True
            self.state.mode = mode
            self.state.total_seconds = max(1, int(seconds))
            self.state.remaining_seconds = self.state.total_seconds
            self.state.paused = False
            self.state.started_at = time.time()
        if emit_to_ui:
            emit_to_ui("pomodoro_started", {
                "mode": mode,
                "total_seconds": self.state.total_seconds,
            })
            emit_to_ui("play_beep", {"kind": "pomodoro_start"})

    def stop(self):
        with self._lock:
            self.state = PomodoroState()
        if emit_to_ui:
            emit_to_ui("pomodoro_stopped", {})

    def pause(self):
        with self._lock:
            if self.state.active:
                self.state.paused = True
        if emit_to_ui:
            emit_to_ui("pomodoro_paused", {})

    def resume(self):
        with self._lock:
            if self.state.active and self.state.paused:
                self.state.paused = False
        if emit_to_ui:
            emit_to_ui("pomodoro_resumed", {})

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
        if emit_to_ui:
            emit_to_ui("pomodoro_reset", {
                "mode": mode,
                "total_seconds": total,
            })

    def get_status(self):
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
        global speak, emit_to_ui
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

            progress = max(0.0, min(1.0, 1.0 - (remaining / float(total))))
            if emit_to_ui:
                emit_to_ui("pomodoro_tick", {
                    "mode": mode,
                    "remaining_seconds": remaining,
                    "total_seconds": total,
                    "progress": progress,
                })
                emit_to_ui("play_beep", {"kind": "tick"})
            if remaining <= 0:
                final_text = "Pomodoro done! ☕ All gone! Take a short break 😎"
                if speak:
                    speak(final_text)
                if emit_to_ui:
                    emit_to_ui("draco_response", {"text": final_text})
                    emit_to_ui("pomodoro_done", {"mode": mode})
                    emit_to_ui("play_beep", {"kind": "pomodoro_end"})
                with self._lock:
                    self.state = PomodoroState()


class TodoManager:
    def __init__(self, path):
        self.path = path
        self.todos = safe_read_json(self.path, [])

    def _save(self):
        safe_write_json(self.path, self.todos)

    def add(self, text: str) -> int:
        tid = int(time.time() * 1000)
        self.todos.append({
            "id": tid,
            "text": text,
            "done": False,
            "created_at": datetime.datetime.now().isoformat(),
            "done_at": None,
        })
        self._save()
        return tid

    def remove(self, tid: int) -> None:
        self.todos = [t for t in self.todos if t.get("id") != tid]
        self._save()

    def list(self):
        return list(self.todos)

    def mark_done(self, tid: int):
        for t in self.todos:
            if t.get("id") == tid:
                if not t.get("done"):
                    t["done"] = True
                    t["done_at"] = datetime.datetime.now().isoformat()
                    self._save()
                return t
        return None
