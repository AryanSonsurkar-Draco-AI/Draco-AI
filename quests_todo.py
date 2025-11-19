import datetime
import time
import json
import os

TODOS_FILE = "todos.json"


def _safe_read_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def _safe_write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class TodoManager:
    def __init__(self, path=TODOS_FILE):
        self.path = path
        self.todos = _safe_read_json(self.path, [])

    def _save(self):
        _safe_write_json(self.path, self.todos)

    def add(self, text: str) -> int:
        tid = int(time.time() * 1000)
        self.todos.append(
            {
                "id": tid,
                "text": text,
                "done": False,
                "created_at": datetime.datetime.now().isoformat(),
                "done_at": None,
            }
        )
        self._save()
        return tid

    def list(self):
        return list(self.todos)

    def remove(self, tid: int) -> bool:
        before = len(self.todos)
        self.todos = [t for t in self.todos if t["id"] != tid]
        changed = len(self.todos) != before
        if changed:
            self._save()
        return changed

    def mark_done(self, tid: int):
        for t in self.todos:
            if t["id"] == tid:
                if not t["done"]:
                    t["done"] = True
                    t["done_at"] = datetime.datetime.now().isoformat()
                    self._save()
                return t
        return None


# --- Daily quest helpers ---


def _today_str():
    return datetime.date.today().isoformat()


def ensure_daily_block(g: dict) -> dict:
    d = g.get("daily")
    if not isinstance(d, dict) or d.get("date") != _today_str():
        d = {
            "date": _today_str(),
            "pomodoros_done": 0,
            "commands_used": 0,
            "todos_done": 0,
            "quests": {
                "pomodoro2": {"done": False, "reward": 20},
                "use5": {"done": False, "reward": 10},
                "todos3": {"done": False, "reward": 15},
            },
        }
        g["daily"] = d
    return d


def bump_counter_and_check_quests(g, kind: str, add_xp_fn, emit_to_ui):
    d = ensure_daily_block(g)

    if kind == "pomodoro":
        d["pomodoros_done"] += 1
        q = d["quests"].get("pomodoro2")
        if q and not q["done"] and d["pomodoros_done"] >= 2:
            q["done"] = True
            add_xp_fn("study", q["reward"])
            try:
                emit_to_ui("quest_completed", {"id": "pomodoro2", "reward": q["reward"]})
            except Exception:
                pass

    elif kind == "command":
        d["commands_used"] += 1
        q = d["quests"].get("use5")
        if q and not q["done"] and d["commands_used"] >= 5:
            q["done"] = True
            add_xp_fn("general", q["reward"])
            try:
                emit_to_ui("quest_completed", {"id": "use5", "reward": q["reward"]})
            except Exception:
                pass

    elif kind == "todo_done":
        d["todos_done"] += 1
        q = d["quests"].get("todos3")
        if q and not q["done"] and d["todos_done"] >= 3:
            q["done"] = True
            add_xp_fn("study", q["reward"])
            try:
                emit_to_ui("quest_completed", {"id": "todos3", "reward": q["reward"]})
            except Exception:
                pass
