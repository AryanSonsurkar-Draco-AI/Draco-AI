import os


def ensure_dir(path: str) -> None:
    """Create directory if it does not already exist."""
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
