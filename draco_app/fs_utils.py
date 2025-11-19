"""File-system helpers for Draco app."""

from __future__ import annotations

import os


def ensure_dir(path: str) -> None:
    """Best-effort directory creation."""
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass


__all__ = ["ensure_dir"]
