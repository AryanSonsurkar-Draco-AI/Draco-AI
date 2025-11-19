"""Application-level memory and personality helpers."""

from __future__ import annotations

import random
import time
from collections import deque

from draco_backend.config import MEMORY_FILE
from draco_backend.helpers import safe_read_json, safe_write_json


class MemoryManager:
    def __init__(self, memory_file: str = MEMORY_FILE):
        self.memory_file = memory_file
        self.session = deque(maxlen=60)
        self.long = safe_read_json(
            memory_file,
            {"language": "english", "name": "Ars", "mood": "neutral"},
        )
        self._save()

    def add(self, text: str) -> None:
        self.session.append({"time": time.time(), "text": text})
        self._save()

    def get_session(self):
        return list(self.session)

    def set_pref(self, key: str, value):
        self.long[key] = value
        self._save()

    def get_pref(self, key: str, default=None):
        return self.long.get(key, default)

    def _save(self):
        safe_write_json(self.memory_file, self.long)


class Personality:
    def __init__(self):
        self.emotion = "neutral"

    def update(self, text: str):
        lowered = text.lower()
        if any(x in lowered for x in ["happy", "great", "awesome", "nice"]):
            self.emotion = "happy"
        elif any(x in lowered for x in ["sad", "upset", "bad", "angry"]):
            self.emotion = "concerned"
        else:
            self.emotion = random.choice(["neutral", "playful", "helpful"])

    def respond(self, base: str) -> str:
        if self.emotion == "happy":
            templates = [f"Yay! {base}", f"I'm glad — {base}", f"Nice! {base}"]
        elif self.emotion == "concerned":
            templates = [
                f"I hear you. {base}",
                f"I'm here for you. {base}",
                f"Don't worry — {base}",
            ]
        elif self.emotion == "playful":
            templates = [f"Heh — {base}", f"Alrighty! {base}", f"Let's do it: {base}"]
        else:
            templates = [base, f"Okay. {base}", f"Done — {base}"]
        return random.choice(templates)


__all__ = ["MemoryManager", "Personality"]
