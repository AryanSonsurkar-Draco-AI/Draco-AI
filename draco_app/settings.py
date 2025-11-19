"""Runtime environment settings for the Draco app."""

import os

ON_RENDER = os.environ.get("RENDER") is not None
ON_SERVER = ON_RENDER or (os.environ.get("PORT") is not None) or (
    os.environ.get("RENDER_EXTERNAL_URL") is not None
)

__all__ = ["ON_RENDER", "ON_SERVER"]
