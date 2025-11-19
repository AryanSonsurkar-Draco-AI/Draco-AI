"""Utilities for user-specific storage and chat history management."""

from __future__ import annotations

import datetime
import os
import time
from typing import Dict, List, Optional

from flask import session

from draco_backend.config import USERS_DIR
from draco_backend.helpers import safe_read_json, safe_write_json
from draco_backend.fs_utils import ensure_dir


def sanitize_email_for_path(email: str) -> str:
    return email.replace("@", "_at_").replace(".", "_dot_")


def user_paths(email: str) -> Dict[str, str]:
    root = os.path.join(USERS_DIR, sanitize_email_for_path(email))
    ensure_dir(root)
    return {
        "root": root,
        "profile": os.path.join(root, "profile.json"),
        "chat": os.path.join(root, "chat.json"),
        "chats": os.path.join(root, "chats.json"),
    }


def get_logged_in_email() -> Optional[str]:
    email = session.get("user_email")
    if isinstance(email, str) and "@" in email:
        return email
    return None


def _load_chats(email: str) -> List[dict]:
    paths = user_paths(email)
    chats = safe_read_json(paths["chats"], None)
    if chats is None:
        legacy = safe_read_json(paths["chat"], [])
        chat_id = str(int(time.time() * 1000))
        name = _summarize_chat_name(legacy)
        chats = [
            {"id": chat_id, "name": name, "items": legacy, "updated_at": time.time()}
        ]
        safe_write_json(paths["chats"], chats)
    return chats


def _save_chats(email: str, chats: List[dict]) -> None:
    safe_write_json(user_paths(email)["chats"], chats)


def _current_chat_id() -> Optional[str]:
    cid = session.get("chat_id")
    return str(cid) if cid else None


def _set_current_chat_id(cid: str) -> None:
    session["chat_id"] = str(cid)


def _get_or_create_current_chat(email: str) -> dict:
    chats = _load_chats(email)
    cid = _current_chat_id()
    if cid:
        for chat in chats:
            if chat.get("id") == cid:
                return chat
    if chats:
        chats = sorted(chats, key=lambda c: c.get("updated_at", 0), reverse=True)
        chat = chats[0]
        _set_current_chat_id(chat.get("id"))
        return chat
    chat = _create_new_chat(email)
    return chat


def _create_new_chat(email: str) -> dict:
    chats = _load_chats(email)
    cid = str(int(time.time() * 1000))
    chat = {"id": cid, "name": "New chat", "items": [], "updated_at": time.time()}
    chats.append(chat)
    _save_chats(email, chats)
    _set_current_chat_id(cid)
    return chat


def _clear_current_chat(email: str) -> bool:
    chats = _load_chats(email)
    cid = _current_chat_id()
    for chat in chats:
        if chat.get("id") == cid:
            chat["items"] = []
            chat["updated_at"] = time.time()
            _save_chats(email, chats)
            return True
    return False


_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "for",
    "in",
    "of",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "be",
    "is",
    "are",
    "was",
    "were",
    "it",
    "this",
    "that",
    "these",
    "those",
    "i",
    "you",
    "he",
    "she",
    "we",
    "they",
    "them",
    "our",
    "your",
    "my",
    "mine",
    "ours",
    "yours",
    "their",
    "his",
    "her",
    "its",
    "about",
    "into",
    "than",
    "too",
    "very",
    "just",
    "can",
    "could",
    "should",
    "would",
    "will",
    "shall",
    "may",
    "might",
    "do",
    "does",
    "did",
    "not",
    "no",
    "yes",
    "ok",
    "please",
    "hey",
    "hi",
    "hello",
    "how",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}


def _summarize_chat_name(items: List[dict]) -> str:
    texts = [x.get("text", "") for x in items if x.get("who") == "user"]
    if not texts:
        texts = [x.get("text", "") for x in items]
    combined = " ".join(texts).strip()
    if not combined:
        return datetime.datetime.now().strftime("Chat %b %d %H:%M")
    first = combined.split("\n")[0].split(".")[0]
    words = [w.strip(" ,:;!?()[]{}\"'\t").lower() for w in first.split()]
    filtered = [w for w in words if w and w not in _STOPWORDS and all(ch.isalnum() or ch in "-_'" for ch in w)]
    if not filtered:
        filtered = first.split()
    if len(filtered) < 2:
        extra = (combined.split())[0:2]
        filtered = (filtered + extra)[:2]
    name = " ".join(filtered[:10]).strip().title()
    if len(name.split()) < 2:
        name = (name + " Chat").strip()
    return name[:80]


def save_chat_line(email: str, who: str, text: str) -> None:
    chats = _load_chats(email)
    chat = _get_or_create_current_chat(email)
    cid = chat.get("id")
    for c in chats:
        if c.get("id") == cid:
            c.setdefault("items", []).append({"ts": time.time(), "who": who, "text": text})
            if (not c.get("name")) or c.get("name") in ("New chat", ""):
                c["name"] = _summarize_chat_name(c.get("items", [])) or "New Chat"
            c["updated_at"] = time.time()
            break
    _save_chats(email, chats)


def get_chat_history(email: str, chat_id: Optional[str] = None) -> List[dict]:
    chats = _load_chats(email)
    cid = chat_id or _current_chat_id()
    if cid:
        for c in chats:
            if c.get("id") == cid:
                return c.get("items", [])
    if chats:
        chats = sorted(chats, key=lambda c: c.get("updated_at", 0), reverse=True)
        _set_current_chat_id(chats[0].get("id"))
        return chats[0].get("items", [])
    return []


def get_user_profile(email: Optional[str]) -> dict:
    if not email:
        return {}
    return safe_read_json(user_paths(email)["profile"], {})


def set_user_profile(email: Optional[str], profile: dict) -> None:
    if not email:
        return
    safe_write_json(user_paths(email)["profile"], profile or {})


def list_chats(email: str) -> List[dict]:
    return _load_chats(email)


def set_current_chat(email: str, chat_id: str) -> bool:
    chats = _load_chats(email)
    if any(c.get("id") == chat_id for c in chats):
        _set_current_chat_id(chat_id)
        return True
    return False


def clear_current_chat(email: str) -> bool:
    return _clear_current_chat(email)


def create_new_chat(email: str) -> dict:
    return _create_new_chat(email)


def get_current_chat_id() -> Optional[str]:
    return _current_chat_id()


def set_current_chat_id(chat_id: str) -> None:
    _set_current_chat_id(chat_id)


__all__ = [
    "ensure_dir",
    "sanitize_email_for_path",
    "user_paths",
    "get_logged_in_email",
    "save_chat_line",
    "get_chat_history",
    "get_user_profile",
    "set_user_profile",
    "list_chats",
    "set_current_chat",
    "clear_current_chat",
]
