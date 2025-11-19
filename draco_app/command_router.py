"""Command routing and high-level assistant actions."""

from __future__ import annotations

import datetime
import os
import platform
import random
import re
import subprocess
import time
import webbrowser
from typing import Any, Dict, Optional

import pytz

from draco_backend.domain import add_xp, get_gamestate, handle_small_talk, set_mode, web_search_duckduckgo
from draco_backend.services import convert_unit, get_news, get_weather, solve_math
from draco_backend.system_utils import system_status_summary

# These globals will be configured by the main app via the configure() function below.
socketio = None
memory = None
personality = None
chat_ctx = None
notes_mgr = None
reminder_mgr = None
pomodoro_mgr = None
todo_mgr = None
pyautogui = None
pywhatkit = None
musicLibrary = None
ON_SERVER = False
DDGS = None
draco_chat = None
speak = None
openai_client = None
get_logged_in_email = None
get_user_profile = None
set_user_profile = None
save_chat_line = None
get_chat_history = None
engine = None
r = None
sr = None
pyttsx3 = None
requests = None
pytz_timezone = pytz.timezone


def configure(**kwargs):
    globals().update(kwargs)

