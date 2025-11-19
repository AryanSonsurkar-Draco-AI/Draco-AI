import time
import random
from typing import Optional

from draco_backend.helpers import safe_read_json, safe_write_json
from draco_backend.config import MEMORY_FILE

# These will be wired from main.py
memory = None
personality = None
DDGS = None
speak = None
get_logged_in_email = None
get_user_profile = None


# ----- Gamification -----

def _ensure_gamification():
    g = memory.long.get("gamification")
    if not isinstance(g, dict):
        g = {}
    if "level" not in g:
        g["level"] = 1
    if "xp" not in g:
        g["xp"] = 0
    if "mode" not in g:
        g["mode"] = "balanced"  # study / coding / balanced
    if "total_xp" not in g:
        g["total_xp"] = 0
    if "last_action" not in g:
        g["last_action"] = None
    if "badges" not in g or not isinstance(g["badges"], list):
        g["badges"] = []
    memory.long["gamification"] = g
    memory._save()
    return g


def _xp_needed(level: int) -> int:
    try:
        lvl = max(1, int(level))
    except Exception:
        lvl = 1
    return 50 + lvl * 20


def add_xp(kind: str, amount: int):
    if amount <= 0:
        return
    g = _ensure_gamification()
    mode = g.get("mode", "balanced")
    boost = 1.0
    if mode == "study" and kind == "study":
        boost = 1.2
    elif mode == "coding" and kind == "coding":
        boost = 1.2
    gained = int(amount * boost)
    g["xp"] = int(g.get("xp", 0)) + gained
    g["total_xp"] = int(g.get("total_xp", 0)) + gained
    g["last_action"] = {"kind": kind, "amount": gained, "ts": time.time()}
    while g["xp"] >= _xp_needed(g["level"]):
        needed = _xp_needed(g["level"])
        g["xp"] -= needed
        g["level"] += 1
    memory.long["gamification"] = g
    memory._save()


def get_gamestate():
    g = _ensure_gamification()
    lvl = int(g.get("level", 1))
    xp = int(g.get("xp", 0))
    needed = _xp_needed(lvl)
    return {
        "level": lvl,
        "xp": xp,
        "xp_needed": needed,
        "mode": g.get("mode", "balanced"),
        "total_xp": int(g.get("total_xp", 0)),
        "badges": g.get("badges", []),
        "last_action": g.get("last_action"),
    }


def set_mode(mode: str):
    g = _ensure_gamification()
    m = (mode or "balanced").lower()
    if m not in ("study", "coding", "balanced"):
        m = "balanced"
    g["mode"] = m
    memory.long["gamification"] = g
    memory._save()
    return m


# ----- Search & small talk helpers -----

def web_search_duckduckgo(query: str, limit: int = 3) -> str:
    if DDGS is None:
        return "ddgs package not installed."
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=limit):
                body = r.get("body", "").strip()
                if body:
                    results.append(body)
        if not results:
            return "I couldn't find anything useful for that query."
        return "\n\n".join(results[:limit])
    except Exception as e:
        return f"Search error: {e}"


def handle_small_talk(cmd: str) -> Optional[str]:
    cmd_lower = cmd.lower()

    if "joke" in cmd_lower or "funny" in cmd_lower or "meme" in cmd_lower:
        return None

    if cmd_lower == "hi":
        reply = "Hey! Ready to tackle today?"
        if speak:
            speak(reply)
        return reply
    if cmd_lower == "hello":
        reply = "Hello! What's our first mission today?"
        if speak:
            speak(reply)
        return reply

    if any(x in cmd_lower for x in ["hello", "hi", "hey"]):
        reply = personality.respond(f"Hello {memory.get_pref('name', 'friend')}! How can I help?")
        if speak:
            speak(reply)
        user_email = get_logged_in_email() if get_logged_in_email else None
        if user_email:
            prof = get_user_profile(user_email)
            name = prof.get("name") or memory.get_pref('name', 'friend')
            reply = reply.replace("friend", name)
        return reply

    return None
