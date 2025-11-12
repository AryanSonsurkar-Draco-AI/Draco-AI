# main.py
# Draco: unified Flask + SocketIO assistant backend
# Save next to draco.html and run: python main.py
# Required packages (example):
# pip install flask flask-socketio pyttsx3 pygame SpeechRecognition ddgs psutil pyautogui pywhatkit
import os
import sys
import time
import json
import random
import datetime
import threading
import subprocess
import platform
import webbrowser
from urllib.parse import quote as url_quote
from urllib.parse import urlparse
from collections import deque
from typing import Optional
import re
from flask import session
from flask import Flask, send_from_directory, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
try:
    from docx import Document
except Exception:
    Document = None
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
except Exception:
    Presentation = None
    Inches = None
    Pt = None
    PP_ALIGN = None
    RGBColor = None
    MSO_SHAPE = None
try:
    from fpdf import FPDF
except Exception:
    FPDF = None
try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None
import sympy as sp
# optional imports (best-effort)
try:
    import pyttsx3
except Exception:
    pyttsx3 = None
try:
    import pygame
except Exception:
    pygame = None
try:
    import speech_recognition as sr
except Exception:
    sr = None
if sr:
    try:
        r = sr.Recognizer()
    except Exception:
        r = None
try:
    import psutil
except Exception:
    psutil = None
try:
    import pyautogui
except Exception:
    pyautogui = None
try:
    import pywhatkit
except Exception:
    pywhatkit = None
# DuckDuckGo scraping wrapper
try:
    from ddgs import DDGS
except Exception:
    DDGS = None
# Music library hook (user's file)
try:
    import musicLibrary
except Exception:
    musicLibrary = None
import requests
import pytz

ON_RENDER = os.environ.get("RENDER") is not None
ON_SERVER = ON_RENDER or (os.environ.get("PORT") is not None) or (os.environ.get("RENDER_EXTERNAL_URL") is not None)

# ------------- Flask / SocketIO -------------
# Force Flask-SocketIO to use threading instead of eventlet or gevent
os.environ["FLASK_SOCKETIO_ASYNC_MODE"] = "threading"
app = Flask(__name__, static_folder=".", template_folder=".")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ------------- Global utilities & config -------------
MEMORY_FILE = "memory.json"
NOTES_FILE = "notes.json"
REMINDERS_FILE = "reminders.json"
WEATHER_API_KEY = ""   # add your OpenWeatherMap key if desired
NEWSAPI_KEY = ""       # add your News API key if desired
USERS_DIR = os.path.join(os.getcwd(), "users")


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

def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass

def sanitize_email_for_path(email: str) -> str:
    # basic safe filename for email
    return email.replace("@", "_at_").replace(".", "_dot_")

def user_paths(email: str):
    root = os.path.join(USERS_DIR, sanitize_email_for_path(email))
    ensure_dir(root)
    return {
        "root": root,
        "profile": os.path.join(root, "profile.json"),
        "chat": os.path.join(root, "chat.json"),  # legacy single-thread file
        "chats": os.path.join(root, "chats.json"), # new: multi-chat storage
    }

def get_logged_in_email() -> Optional[str]:
    e = session.get("user_email")
    if isinstance(e, str) and "@" in e:
        return e
    return None

def _load_chats(email: str):
    p = user_paths(email)
    chats = safe_read_json(p["chats"], None)
    if chats is None:
        # migrate from legacy chat.json into a single chat
        legacy = safe_read_json(p["chat"], [])
        chat_id = str(int(time.time() * 1000))
        name = _summarize_chat_name(legacy)
        chats = [{"id": chat_id, "name": name, "items": legacy, "updated_at": time.time()}]
        safe_write_json(p["chats"], chats)
    return chats

def _save_chats(email: str, chats):
    p = user_paths(email)
    safe_write_json(p["chats"], chats)

def _current_chat_id() -> Optional[str]:
    cid = session.get("chat_id")
    return str(cid) if cid else None

def _set_current_chat_id(cid: str):
    session["chat_id"] = str(cid)

def _get_or_create_current_chat(email: str):
    chats = _load_chats(email)
    cid = _current_chat_id()
    chat = None
    if cid:
        for c in chats:
            if c.get("id") == cid:
                chat = c
                break
    if chat is None:
        # pick latest or create
        if chats:
            chats = sorted(chats, key=lambda c: c.get("updated_at", 0), reverse=True)
            chat = chats[0]
            _set_current_chat_id(chat.get("id"))
        else:
            chat = _create_new_chat(email)
            chats = _load_chats(email)  # ensure persisted
    return chat

def _create_new_chat(email: str):
    chats = _load_chats(email)
    cid = str(int(time.time() * 1000))
    chat = {"id": cid, "name": "New chat", "items": [], "updated_at": time.time()}
    chats.append(chat)
    _save_chats(email, chats)
    _set_current_chat_id(cid)
    return chat

def _clear_current_chat(email: str):
    chats = _load_chats(email)
    cid = _current_chat_id()
    for c in chats:
        if c.get("id") == cid:
            c["items"] = []
            c["updated_at"] = time.time()
            _save_chats(email, chats)
            return True
    return False

STOPWORDS = set("the a an and or to for in of on with at by from as be is are was were it this that these those i you he she we they them our your my mine ours yours their his her its about into than too very just can could should would will shall may might do does did not no yes ok please hey hi hello how what when where which who why".split())

def _summarize_chat_name(items):
    # items: list of {who, text}
    texts = [x.get("text", "") for x in items if x.get("who") == "user"]
    if not texts:
        texts = [x.get("text", "") for x in items]
    combined = " ".join(texts).strip()
    if not combined:
        return datetime.datetime.now().strftime("Chat %b %d %H:%M")
    # take first sentence
    first = combined.split("\n")[0].split(".")[0]
    words = [w.strip(" ,:;!?()[]{}\"'\t").lower() for w in first.split()]
    filtered = [w for w in words if w and w not in STOPWORDS and all(ch.isalnum() or ch in "-_'" for ch in w)]
    if not filtered:
        # fallback: first few original words
        filtered = first.split()
    # min 2 words, max 10 words
    if len(filtered) < 2:
        extra = (combined.split())[0:2]
        filtered = (filtered + extra)[:2]
    name_words = filtered[:10]
    name = " ".join(name_words).strip().title()
    if len(name.split()) < 2:
        name = (name + " Chat").strip()
    return name[:80]

def save_chat_line(email: str, who: str, text: str):
    chats = _load_chats(email)
    chat = _get_or_create_current_chat(email)
    # refresh chats after current selection (IDs)
    cid = chat.get("id")
    for c in chats:
        if c.get("id") == cid:
            c.setdefault("items", []).append({"ts": time.time(), "who": who, "text": text})
            # set name on first meaningful lines
            if (not c.get("name")) or c.get("name") in ("New chat", ""):
                c["name"] = _summarize_chat_name(c["items"]) or "New Chat"
            c["updated_at"] = time.time()
            break
    _save_chats(email, chats)

def get_chat_history(email: str, chat_id: Optional[str] = None):
    chats = _load_chats(email)
    cid = chat_id or _current_chat_id()
    if cid:
        for c in chats:
            if c.get("id") == cid:
                return c.get("items", [])
    # default to latest
    if chats:
        chats = sorted(chats, key=lambda c: c.get("updated_at", 0), reverse=True)
        _set_current_chat_id(chats[0].get("id"))
        return chats[0].get("items", [])
    return []

def get_user_profile(email: str):
    p = user_paths(email)
    return safe_read_json(p["profile"], {})

def set_user_profile(email: str, profile: dict):
    p = user_paths(email)
    safe_write_json(p["profile"], profile or {})

# ------------- Memory / Personality -------------
class MemoryManager:
    def __init__(self, memory_file=MEMORY_FILE):
        self.memory_file = memory_file
        self.session = deque(maxlen=60)
        self.long = safe_read_json(memory_file, {"language": "english", "name": "Ars", "mood": "neutral"})
        self._save()

    def add(self, text):
        self.session.append({"time": time.time(), "text": text})
        self._save()

    def get_session(self):
        return list(self.session)

    def set_pref(self, k, v):
        self.long[k] = v
        self._save()

    def get_pref(self, k, default=None):
        return self.long.get(k, default)

    def _save(self):
        safe_write_json(self.memory_file, self.long)

class Personality:
    def __init__(self):
        self.emotion = "neutral"

    def update(self, text: str):
        t = text.lower()
        if any(x in t for x in ["happy", "great", "awesome", "nice"]):
            self.emotion = "happy"
        elif any(x in t for x in ["sad", "upset", "bad", "angry"]):
            self.emotion = "concerned"
        else:
            # small random drift
            self.emotion = random.choice(["neutral", "playful", "helpful"])

    def respond(self, base: str) -> str:
        # dynamic replies based on emotion
        if self.emotion == "happy":
            templates = [f"Yay! {base}", f"I'm glad — {base}", f"Nice! {base}"]
        elif self.emotion == "concerned":
            templates = [f"I hear you. {base}", f"I'm here for you. {base}", f"Don't worry — {base}"]
        elif self.emotion == "playful":
            templates = [f"Heh — {base}", f"Alrighty! {base}", f"Let's do it: {base}"]
        else:
            templates = [base, f"Okay. {base}", f"Done — {base}"]
        return random.choice(templates)

memory = MemoryManager()
personality = Personality()

# ------------- TTS (single speak implementation) -------------
# On servers (Render/containers), avoid initializing pyttsx3 (needs eSpeak)
engine = None
if pyttsx3 and not ON_SERVER:
    try:
        engine = pyttsx3.init()
    except Exception:
        engine = None

def emit_to_ui(key: str, payload: dict):
    try:
        socketio.emit(key, payload)
    except Exception as e:
        print("Emit error:", e)

# Reconfirm TTS availability with safe init (local only)
if pyttsx3 and not ON_SERVER and engine is None:
    try:
        engine = pyttsx3.init()
    except Exception as e:
        engine = None
        print("TTS disabled:", e)

def speak(text):
    print("Draco says:", text)
    if engine:
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print("TTS error:", e)

# ------------- Notes / Reminders -------------
class NotesManager:
    def __init__(self, path=NOTES_FILE):
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
    def __init__(self, path=REMINDERS_FILE):
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
                speak(f"Reminder: {r['text']}")
                self.remove(r["id"])
            time.sleep(6)

notes_mgr = NotesManager()
reminder_mgr = ReminderManager()

# ------------- System utilities -------------
def system_status_summary():
    if not psutil:
        return "psutil not installed, cannot fetch system info."
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(os.path.expanduser("~"))
    bat = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    lines = [
        f"CPU: {cpu}%",
        f"RAM: {ram.percent}%",
        f"Disk: {disk.percent}%"
    ]
    if bat:
        lines.append(f"Battery: {bat.percent}% {'charging' if bat.power_plugged else 'not charging'}")
    return ". ".join(lines)

def take_screenshot(save_path: Optional[str] = None):
    if not pyautogui:
        raise RuntimeError("pyautogui not installed.")
    if not save_path:
        save_path = f"screenshot_{int(time.time())}.png"
    img = pyautogui.screenshot()
    img.save(save_path)
    return save_path

def open_app_windows(name: str):
    """Try to open an app by name (Windows start) or command on other OS."""
    try:
        if platform.system() == "Windows":
            # try known apps mapping first
            mapping = {
                "vscode": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
                "spotify": r"C:\Users\%USERNAME%\AppData\Roaming\Spotify\Spotify.exe",
                "chrome": r"chrome",
            }
            if name.lower() in mapping:
                path = mapping[name.lower()]
                try:
                    os.startfile(os.path.expandvars(path))
                    return True
                except Exception:
                    # fallback to shell start
                    subprocess.run(["start", path], shell=True)
                    return True
            else:
                # best-effort start name
                subprocess.run(["start", name], shell=True)
                return True
        elif platform.system() == "Linux":
            subprocess.Popen([name])
            return True
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-a", name])
            return True
    except Exception as e:
        print("open_app error:", e)
    return False

def run_system_command(cmd: str):
    """Run a shell command and return (stdout, stderr)."""
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
        return res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return "", str(e)

# Brightness / wifi / bluetooth / volume - best-effort examples (Windows)
def set_brightness_win(percent: int):
    try:
        script = f'(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{int(percent)})'
        subprocess.run(["powershell", "-Command", script], check=False)
        return True
    except Exception as e:
        print("brightness error:", e)
        return False

def toggle_wifi_win(enable: bool):
    try:
        state = "enable" if enable else "disable"
        subprocess.run(["powershell", "-Command", f"Get-NetAdapter | Where-Object {{ $_.Status -ne '{state}' }} | ForEach-Object {{ Set-NetAdapter -Name $_.Name -{state} -Confirm:$false }}"], check=False)
        return True
    except Exception as e:
        print("wifi toggle error:", e)
        return False

# ------------- Web helpers -------------
def open_youtube():
    webbrowser.open("https://youtube.com")
    return "Opened YouTube."

def open_instagram():
    webbrowser.open("https://instagram.com")
    return "Opened Instagram."

def open_github():
    webbrowser.open("https://github.com")
    return "Opened GitHub."

def open_render():
    webbrowser.open("https://render.com")
    return "Opened Render."

def open_whatsapp_web():
    webbrowser.open("https://web.whatsapp.com")
    return "Opened WhatsApp Web."

def send_whatsapp_message(phone: str, message: str):
    """Open WhatsApp web chat to phone with message (uses wa.me). Works if user is logged-in."""
    # phone should be in international format without +, e.g., 919xxxxxxxxx
    msg = url_quote(message)
    url = f"https://wa.me/{phone}?text={msg}"
    if ON_SERVER:
        return {"text": f"Opening WhatsApp chat for {phone}…", "action": "open_url", "url": url}
    webbrowser.open(url)
    return f"Opening WhatsApp chat for {phone}. Please confirm send in browser."

def open_linkedin():
    webbrowser.open("https://linkedin.com")
    return "Opened LinkedIn."

# ------------- Music integration -------------
def play_music_from_library(song_name: Optional[str] = None):
    if not musicLibrary:
        return "musicLibrary not found. Add musicLibrary.py with play/pause/stop functions."
    # On server: return a web action so the browser opens the URL
    if ON_SERVER:
        try:
            url = None
            song_display_name = song_name or "music"
            # Use musicLibrary's built-in search function if available
            if hasattr(musicLibrary, "_find_song_url_by_name") and song_name:
                url = musicLibrary._find_song_url_by_name(song_name)
                if url:
                    return {"text": f"Playing: {song_name}", "action": "open_url", "url": url}
            # Fallback: search music dict directly
            if hasattr(musicLibrary, "music") and isinstance(musicLibrary.music, dict):
                if song_name:
                    key = song_name.strip().lower()
                    # Exact match
                    if key in musicLibrary.music:
                        url = musicLibrary.music[key]
                    else:
                        # Substring/fuzzy match
                        for k, v in musicLibrary.music.items():
                            if key in k.lower() or k.lower() in key:
                                url = v
                                song_display_name = k
                                break
                # If no song specified or not found, use first song
                if url is None:
                    try:
                        url = next(iter(musicLibrary.music.values()))
                        song_display_name = next(iter(musicLibrary.music.keys()))
                    except Exception:
                        url = None
            if url:
                return {"text": f"Playing: {song_display_name}", "action": "open_url", "url": url}
            return "No matching song found. Try: play faded, play lily, play alone"
        except Exception as e:
            return f"musicLibrary error: {e}"
    # Local: invoke the library which opens the browser
    try:
        if song_name:
            return musicLibrary.play(song_name)
        else:
            return musicLibrary.play()
    except Exception as e:
        return f"musicLibrary error: {e}"

# ------------- Local system actions (best-effort) -------------
def sleep_pc():
    if platform.system() == "Windows":
        try:
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=False)
            return True, "Sleeping now."
        except Exception as e:
            return False, f"Sleep failed: {e}"
    return False, "Sleep not supported on this OS."

def type_text(text: str):
    if not pyautogui:
        return False, "Typing requires pyautogui installed locally."
    try:
        pyautogui.typewrite(text, interval=0.02)
        return True, "Typed your text."
    except Exception as e:
        return False, f"Typing failed: {e}"

def set_brightness(percent: int):
    if platform.system() == "Windows":
        ok = set_brightness_win(percent)
        return ok, ("Brightness updated." if ok else "Couldn't change brightness.")
    return False, "Brightness control not supported on this OS."

def toggle_wifi(enable: bool):
    if platform.system() == "Windows":
        ok = toggle_wifi_win(enable)
        return ok, ("Wi-Fi enabled." if (ok and enable) else ("Wi-Fi disabled." if ok else "Couldn't toggle Wi-Fi."))
    return False, "Wi-Fi control not supported on this OS."

def set_volume(percent: int):
    return False, "Volume control not implemented on this system."

def toggle_bluetooth(enable: bool):
    return False, "Bluetooth control not implemented."

def whatsapp_send_direct(phone: str, message: str):
    if ON_SERVER:
        return False, "Direct WhatsApp send only works on your local machine."
    if not pywhatkit:
        return False, "Install pywhatkit locally to send WhatsApp instantly."
    try:
        if not phone.startswith("+") and len(phone) >= 10:
            phone = "+" + phone
        pywhatkit.sendwhatmsg_instantly(phone_no=phone, message=message, wait_time=8, tab_close=True)
        return True, "WhatsApp message sent."
    except Exception as e:
        return False, f"WhatsApp send failed: {e}"

WEATHER_API_KEY = "96e102262e9745129d110636251111 "

def get_weather(city):
    if not WEATHER_API_KEY:
        return "Weather feature needs an API key. Add it to WEATHER_API_KEY."
    
    try:
        # OpenWeatherMap API call
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()

        if data.get("cod") != 200:
            return f"Could not find weather for '{city}'. Please check the city name."
        
        # Extract info
        temp = data["main"]["temp"]
        condition = data["weather"][0]["description"].title()
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]

        # Format result
        result = (
            f"Weather in {city}:\n"
            f"Temperature: {temp}°C\n"
            f"Condition: {condition}\n"
            f"Humidity: {humidity}%\n"
            f"Wind Speed: {wind_speed} m/s"
        )
        return result

    except Exception as e:
        return f"Error fetching weather: {str(e)}"

NEWS_API_KEY = "231a93af4a8b4dc6bafbb736c20b20c3"

def get_news(topic="general"):
    if not NEWS_API_KEY:
        return "News feature needs an API key. Add it to NEWS_API_KEY."
    
    try:
        url = f"https://newsapi.org/v2/top-headlines?q={topic}&apiKey={NEWS_API_KEY}&pageSize=5"
        response = requests.get(url)
        data = response.json()
        
        if data.get("status") != "ok" or not data.get("articles"):
            return f"No news found for '{topic}'."
        
        # Format top 5 headlines
        news_list = ""
        for i, article in enumerate(data["articles"], start=1):
            title = article.get("title", "No title")
            source = article.get("source", {}).get("name", "Unknown")
            news_list += f"{i}. {title} ({source})\n"
        
        return f"Top news on '{topic}':\n{news_list}"

    except Exception as e:
        return f"Error fetching news: {str(e)}"

def solve_math(cmd):
    try:
        if "calculate" in cmd.lower():
            expression = cmd.lower().replace("calculate", "").strip()
            result = eval(expression)  # simple math
            speak(f"Result: {result}")
            return f"Result: {result}"

        elif "solve" in cmd.lower():
            equation = cmd.lower().replace("solve", "").strip()
            x = sp.symbols('x')
            solution = sp.solve(equation, x)
            speak(f"Solution: {solution}")
            return f"Solution: {solution}"

        else:
            speak("Math command not recognized.")
            return "Math command not recognized."

    except Exception as e:
        speak(f"Error: {str(e)}")
        return f"Error: {str(e)}"

EXCHANGE_API_KEY = "d97d653e87f3ea812b311d20"  # for currency

def convert_unit(cmd):
    try:
        cmd_lower = cmd.lower()

        # Currency Conversion
        if "convert" in cmd_lower and "to" in cmd_lower:
            words = cmd_lower.replace("convert", "").strip().split(" ")
            amount = float(words[0])
            from_unit = words[1].upper()
            to_unit = words[-1].upper()

            # Only handle USD/INR for free example, expand later
            if from_unit == "USD" and to_unit == "INR":
                rate = 82.5  # example rate
                result = amount * rate
                speak(f"{amount} {from_unit} = {result} {to_unit}")
                return f"{amount} {from_unit} = {result} {to_unit}"
            else:
                speak(f"Conversion from {from_unit} to {to_unit} not supported yet.")
                return f"Conversion from {from_unit} to {to_unit} not supported yet."

        # Simple Length Conversion Example
        elif "km to miles" in cmd_lower:
            km = float(cmd_lower.split("km")[0].strip())
            miles = km * 0.621371
            speak(f"{km} km = {miles:.2f} miles")
            return f"{km} km = {miles:.2f} miles"

        # Temperature Conversion Example
        elif "c to f" in cmd_lower:
            c = float(cmd_lower.split("c")[0].strip())
            f = (c * 9/5) + 32
            speak(f"{c}°C = {f:.2f}°F")
            return f"{c}°C = {f:.2f}°F"

        else:
            speak("Unit conversion not recognized.")
            return "Unit conversion not recognized."

    except Exception as e:
        speak(f"Error: {str(e)}")
        return f"Error: {str(e)}"

# ------------- Search & utilities -------------
def web_search_duckduckgo(query: str, limit: int = 3):
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
            return "No results found."
        return " | ".join(results)[:1000]
    except Exception as e:
        return f"Search error: {e}"

# ------------- Command processing (centralised) -------------
def process_command(raw_cmd: str) -> str:
    """
    Central router: map raw user phrases to functions. Returns a string that will be both emitted and spoken.
    Add your 30-40 specific commands here; this is the place to expand.
    """
    if not raw_cmd:
        return "Please say something."

    cmd = raw_cmd.strip().lower()
    # Save to global session memory
    memory.add(f"You: {raw_cmd}")
    # If logged in, append to per-user chat history
    user_email = get_logged_in_email()
    if user_email:
        try:
            save_chat_line(user_email, "user", raw_cmd)
        except Exception:
            pass
    personality.update(cmd)

    # greetings / small talk
    if any(x in cmd for x in ["hello", "hi", "hey"]):
        reply = personality.respond(f"Hello {memory.get_pref('name', 'friend')}! How can I help?")
        speak(reply)
        # personalize greeting if user profile has name
        user_email = get_logged_in_email()
        if user_email:
            prof = get_user_profile(user_email)
            name = prof.get("name") or memory.get_pref('name', 'friend')
            reply = reply.replace("friend", name)
        return reply

    if "how are you" in cmd:
        reply = personality.respond("I'm good — ready to help you.")
        speak(reply)
        return reply

    if "who are you" in cmd:
        reply = "I am Draco AI made by Aryan and his co-workers which are kaustubh and ritesh."
        speak(reply)
        return reply
    if "calculate" in cmd.lower() or "solve" in cmd.lower():
        speak("I solved it.")
        return solve_math(cmd)
    if ("time" in cmd.lower() and "what" in cmd.lower()) or cmd.lower() == "time":
        india_tz = pytz.timezone("Asia/Kolkata")
        now = datetime.datetime.now(india_tz)
        t = now.strftime("%I:%M %p").lstrip("0")  # 12-hour format, remove leading zero
        speak(f"The time is {t}")
        return f"The time is {t}"

    if "date" in cmd:
        d = datetime.date.today().strftime("%B %d, %Y")
        speak(f"Today is {d}")
        return f"Today is {d}"

    # open websites
    if "open youtube" in cmd:
        if ON_SERVER:
            return {"text": "Opening YouTube…", "action": "open_url", "url": "https://youtube.com"}
        r = open_youtube()
        speak(personality.respond(r))
        return r
    if "open instagram" in cmd:
        if ON_SERVER:
            return {"text": "Opening Instagram…", "action": "open_url", "url": "https://instagram.com"}
        r = open_instagram()
        speak(personality.respond(r))
        return r
    if "open linkedin" in cmd:
        if ON_SERVER:
            return {"text": "Opening LinkedIn…", "action": "open_url", "url": "https://linkedin.com"}
        r = open_linkedin()
        speak(personality.respond(r))
        return r
    if "open github" in cmd:
        if ON_SERVER:
            return {"text": "Opening GitHub…", "action": "open_url", "url": "https://github.com"}
        r = open_github()
        speak(personality.respond(r))
        return r
    if "open render" in cmd:
        if ON_SERVER:
            return {"text": "Opening Render…", "action": "open_url", "url": "https://render.com"}
        r = open_render()
        speak(personality.respond(r))
        return r
    if "open whatsapp" in cmd or "open whatsapp web" in cmd:
        if ON_SERVER:
            return {"text": "Opening WhatsApp Web…", "action": "open_url", "url": "https://web.whatsapp.com"}
        r = open_whatsapp_web()
        speak(personality.respond(r))
        return r
    if "weather" in cmd.lower():
        city_name = cmd.lower().replace("weather in", "").strip()
        weather_info = get_weather(city_name)
        speak(weather_info)
        return weather_info
    if "news" in cmd.lower():
        topic_name = cmd.lower().replace("news on", "").strip()
        news_info = get_news(topic_name)
        speak(news_info)
        return news_info
    if "convert" in cmd.lower() or "km to miles" in cmd.lower() or "c to f" in cmd.lower():
        result = convert_unit(cmd)
        speak(result)
        return result

    # whatsapp send (phrase: send whatsapp to 919xxxxxxxxx message hi)
    if "whatsapp" in cmd and "send" in cmd:
        # naive parse: "send whatsapp to 919xxxxxxxxx msg hello there"
        parts = cmd.split()
        phone = None
        message = None
        for i, p in enumerate(parts):
            if p.isdigit() and (9 <= len(p) <= 15):
                phone = p
                # message is remainder after 'message' or 'msg' or 'text'
                if "message" in parts:
                    idx = parts.index("message") + 1
                    message = " ".join(parts[idx:])
                elif "msg" in parts:
                    idx = parts.index("msg") + 1
                    message = " ".join(parts[idx:])
                elif "text" in parts:
                    idx = parts.index("text") + 1
                    message = " ".join(parts[idx:])
                break
        if phone and message:
            sent, out = whatsapp_send_direct(phone, message)
            if sent:
                speak(out)
                return out
            r = send_whatsapp_message(phone, message)
            speak(r)
            return r
        else:
            return "Please provide phone number and message. Example: send whatsapp to 919123456789 message Hello"

    # music
    if cmd.startswith("play "):
        # allow "play music <name>", "play song <name>", or just "play <name>"
        rest = cmd[5:].strip()  # after "play "
        name = None
        if rest.startswith("music "):
            name = rest[6:].strip()  # after "music "
        elif rest.startswith("song "):
            name = rest[5:].strip()  # after "song "
        elif rest:
            name = rest  # just "play faded" -> "faded"
        r = play_music_from_library(name)
        if isinstance(r, dict):
            return r
        speak(str(r))
        return str(r)
    if "pause music" in cmd or "pause" == cmd:
        if musicLibrary and hasattr(musicLibrary, "pause"):
            musicLibrary.pause()
            speak("Paused music.")
            return "Paused music."
        return "No music library pause function available."

    # system commands
    if "system status" in cmd or "status" in cmd:
        s = system_status_summary()
        speak(s)
        return s
    if "sleep" in cmd or "sleep pc" in cmd or "put pc in sleep" in cmd:
        ok, msg = sleep_pc()
        speak(msg)
        return msg
    if "screenshot" in cmd:
        try:
            path = take_screenshot()
            speak(f"Screenshot saved as {path}")
            return f"Screenshot: {path}"
        except Exception as e:
            return f"Screenshot failed: {e}"

    if "shutdown" in cmd:
        speak("Shutting down the PC in 5 seconds. Cancel if you didn't mean this.")
        if platform.system() == "Windows":
            subprocess.run(["shutdown", "/s", "/t", "5"])
        else:
            subprocess.run(["shutdown", "now"])
        return "Shutdown initiated."

    if "restart" in cmd:
        speak("Restarting now.")
        if platform.system() == "Windows":
            subprocess.run(["shutdown", "/r", "/t", "5"])
        else:
            subprocess.run(["reboot"])
        return "Restart initiated."

    if "lock device" in cmd or "lock" == cmd:
        if platform.system() == "Windows":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
            return "Locked PC."
        return "Lock not available on this OS."

    # settings controls
    if cmd.startswith("set brightness "):
        try:
            val = int(cmd.rsplit("set brightness ", 1)[1].strip().rstrip("%"))
            val = max(0, min(100, val))
            ok, msg = set_brightness(val)
            speak(msg)
            return msg
        except Exception:
            return "Please specify brightness as a number 0-100."
    if "turn wifi on" in cmd or "wifi on" in cmd:
        ok, msg = toggle_wifi(True)
        speak(msg)
        return msg
    if "turn wifi off" in cmd or "wifi off" in cmd:
        ok, msg = toggle_wifi(False)
        speak(msg)
        return msg
    if cmd.startswith("set volume "):
        try:
            val = int(cmd.rsplit("set volume ", 1)[1].strip().rstrip("%"))
            val = max(0, min(100, val))
            ok, msg = set_volume(val)
            speak(msg)
            return msg
        except Exception:
            return "Please specify volume as a number 0-100."
    if "bluetooth on" in cmd or "turn bluetooth on" in cmd:
        ok, msg = toggle_bluetooth(True)
        speak(msg)
        return msg
    if "bluetooth off" in cmd or "turn bluetooth off" in cmd:
        ok, msg = toggle_bluetooth(False)
        speak(msg)
        return msg

    # file generation commands
    if cmd.startswith("generate ppt on ") or cmd.startswith("create ppt on "):
        topic = cmd.replace("generate ppt on ", "", 1).replace("create ppt on ", "", 1).strip()
        if not topic:
            return "Please provide a topic."
        # optional: detect "N sentences/per slide"
        msps = None
        m = re.search(r"(\d{1,2})\s*(?:sentences?|per\s*slide)", cmd)
        if m:
            try:
                msps = max(1, min(8, int(m.group(1))))
            except Exception:
                msps = None
        points, sources = research_query_to_texts_with_sources(topic, limit=8)
        try:
            if msps:
                path = _generate_pptx(f"{topic.title()} - Slides", points, max_sentences_per_slide=msps)
            else:
                path = _generate_pptx(f"{topic.title()} - Slides", points)
            rel = os.path.relpath(path, os.getcwd()).replace("\\", "/")
            url = f"/download/{rel}"
            speak("Slides ready. Opening the download link.")
            labeled = []
            for u in sources:
                try:
                    d = urlparse(u).netloc or u
                except Exception:
                    d = u
                labeled.append({"label": d, "url": u})
            return {"text": f"Generated slides for {topic}. Download: {url}", "action": "open_url", "url": url, "sources": sources, "sources_labeled": labeled}
        except Exception as e:
            return f"Could not generate PPTX: {e}"

    if cmd.startswith("generate doc on ") or cmd.startswith("create doc on "):
        topic = cmd.replace("generate doc on ", "", 1).replace("create doc on ", "", 1).strip()
        if not topic:
            return "Please provide a topic."
        points = research_query_to_texts(topic, limit=10)
        try:
            path = _generate_docx(f"{topic.title()} - Notes", points)
            rel = os.path.relpath(path, os.getcwd()).replace("\\", "/")
            url = f"/download/{rel}"
            speak("Document ready. Opening the download link.")
            return {"text": f"Generated DOCX for {topic}. Download: {url}", "action": "open_url", "url": url}
        except Exception as e:
            return f"Could not generate DOCX: {e}"

    if cmd.startswith("generate pdf on ") or cmd.startswith("create pdf on "):
        topic = cmd.replace("generate pdf on ", "", 1).replace("create pdf on ", "", 1).strip()
        if not topic:
            return "Please provide a topic."
        points = research_query_to_texts(topic, limit=12)
        try:
            path = _generate_pdf(f"{topic.title()} - Report", points)
            rel = os.path.relpath(path, os.getcwd()).replace("\\", "/")
            url = f"/download/{rel}"
            speak("PDF ready. Opening the download link.")
            return {"text": f"Generated PDF for {topic}. Download: {url}", "action": "open_url", "url": url}
        except Exception as e:
            return f"Could not generate PDF: {e}"

    # type text into active window
    if cmd.startswith("type "):
        text_to_type = raw_cmd.strip()[5:]
        ok, msg = type_text(text_to_type)
        speak(msg)
        return msg

    # open desktop apps
    if cmd.startswith("open app ") or cmd.startswith("open "):
        # try to parse "open app vscode" or "open spotify"
        name = cmd.replace("open app ", "").replace("open ", "").strip()
        ok = open_app_windows(name)
        if ok:
            s = f"Opened {name}"
            speak(s)
            return s
        else:
            return f"Couldn't open {name}"

    # file manager actions
    if cmd.startswith("find file ") or cmd.startswith("search file "):
        term = cmd.split(" ", 2)[2] if len(cmd.split(" ", 2)) > 2 else ""
        matches = []
        for root, _, files in os.walk(os.path.expanduser("~")):
            for f in files:
                if term.lower() in f.lower():
                    matches.append(os.path.join(root, f))
                    if len(matches) >= 6:
                        break
            if len(matches) >= 6:
                break
        if not matches:
            reply = "No files found."
        else:
            reply = f"Found {len(matches)} files. First: {matches[0]}"
        speak(reply)
        return reply

    # notes / reminders
    if cmd.startswith("take note") or cmd.startswith("note "):
        note_text = cmd.replace("take note", "").replace("note", "").strip()
        if not note_text:
            return "Please say the note text."
        nid = notes_mgr.add(note_text)
        r = f"Note saved. ID {nid}"
        speak(r)
        return r

    if "list notes" in cmd or "show notes" in cmd:
        n = notes_mgr.list()
        if not n:
            return "No notes."
        short = "; ".join([f"{i+1}. {x['text']}" for i,x in enumerate(n[:6])])
        speak("Reading notes.")
        return short

    if "set reminder" in cmd or "remind me" in cmd:
        # naive parse: "remind me to call mom at 19:30"
        if " at " in cmd:
            try:
                before, atpart = cmd.rsplit(" at ", 1)
                text = before.replace("remind me to", "").replace("set reminder to", "").strip()
                now = datetime.datetime.now()
                if ":" in atpart and len(atpart.split()) == 1:
                    hour, minute = map(int, atpart.split(":"))
                    when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if when < now:
                        when += datetime.timedelta(days=1)
                else:
                    when = datetime.datetime.fromisoformat(atpart.strip())
                rid = reminder_mgr.add(text, when)
                r = f"Reminder set for {when.isoformat()}"
                speak(r)
                return r
            except Exception as e:
                return f"Couldn't set reminder: {e}"
        else:
            return "Please include time with 'at'. Example: remind me to call mom at 19:30"

    # web search
    if cmd.startswith("search for ") or cmd.startswith("what is ") or cmd.startswith("who is "):
        q = cmd.replace("search for ", "").replace("what is ", "").replace("who is ", "")
        res = web_search_duckduckgo(q)
        speak("Here's what I found.")
        return res

    # jokes
    if "joke" in cmd or "tell me a joke" in cmd:
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs!",
            "I told my computer I needed a break, and it said 'No problem — I'll go to sleep.'",
            "There are only 10 kinds of people in the world: those who understand binary and those who don't.",
            "Rishte mai hum tumhare baap lagte hai.",
            "Kaun bhauk raha hai , ye bata-meez.",
            "What if a girl propose you? In your dreams. ha ha ha ha ha ha.",
            "Pahili furr, sat se nikal . Joke sunna hai tuze? Mai aajaau kya udhar."
        ]
        reply = random.choice(jokes)
        speak(reply)
        return reply

    # weather placeholder
    if "weather" in cmd:
        if WEATHER_API_KEY:
            # user can implement call to OpenWeatherMap here
            return "Weather lookup available — add API key to WEATHER_API_KEY."
        else:
            return "Weather feature needs an API key. Add it to WEATHER_API_KEY."

    # news placeholder
    if "news" in cmd or "headlines" in cmd:
        if NEWSAPI_KEY:
            return "News lookup available — add NEWSAPI_KEY."
        else:
            return "News feature needs an API key. Add it to NEWSAPI_KEY."

    # research and doc generation
    if cmd.startswith("research ") or cmd.startswith("search topic "):
        topic = cmd.replace("research ", "", 1).replace("search topic ", "", 1).strip()
        if not topic:
            return "Please provide a topic. Example: research quantum computing basics"
        items = research_query_to_texts(topic, limit=6)
        # try to generate docx
        path, err = save_docx_from_texts(topic, items)
        if path:
            rel = os.path.relpath(path, os.getcwd()).replace("\\", "/")
            url = f"/download/{rel}"
            speak("I compiled a short brief and created a document for you.")
            return {"text": f"Research summary ready. Download: {url}", "action": "open_url", "url": url}
        else:
            speak("Here is a quick summary I found.")
            return " • " + "\n • ".join(items[:6])

    # run shell command (explicit phrase: run)
    if cmd.startswith("run "):
        to_run = cmd.replace("run ", "", 1)
        out, err = run_system_command(to_run)
        if out:
            speak("Command executed, returning output.")
            return out[:1500]
        else:
            return f"Command error: {err}"

    # fallback
    speak("I didn't get that. Try asking me to open apps, play music, take notes, set reminders or search the web.")
    return "Unknown command. Try: open youtube, play music, take note, set reminder, search for ..."

# ------------- Flask / SocketIO endpoints -------------
@app.route("/")
def index():
    # Always show main app; login removed
        return send_from_directory(".", "draco.html")


@app.route("/guest")
def guest_mode():
    # Guest mode (login removed) – just serve app
    return send_from_directory(".", "draco.html")

@app.route("/me")
def me():
    email = get_logged_in_email()
    if not email:
        return {"logged_in": False}
    prof = get_user_profile(email)
    return {"logged_in": True, "email": email, "profile": prof}

@app.route("/api/profile", methods=["GET", "POST"])
def api_profile():
    email = get_logged_in_email()
    if not email:
        return {"ok": False, "error": "not_authenticated"}, 401
    if request.method == "GET":
        return {"ok": True, "profile": get_user_profile(email)}
    data = request.json or {}
    if not isinstance(data, dict):
        return {"ok": False, "error": "invalid"}, 400
    prof = get_user_profile(email)
    prof.update({k: v for k, v in data.items() if isinstance(k, str)})
    set_user_profile(email, prof)
    return {"ok": True, "profile": prof}

@app.route("/api/chat_history", methods=["GET"]) 
def api_chat_history():
    email = get_logged_in_email()
    if not email:
        return {"ok": False, "error": "not_authenticated"}, 401
    chat_id = request.args.get("chat_id")
    return {"ok": True, "items": get_chat_history(email, chat_id)}

@app.route("/api/chats", methods=["GET"]) 
def api_chats_list():
    email = get_logged_in_email()
    if not email:
        return {"ok": False, "error": "not_authenticated"}, 401
    chats = _load_chats(email)
    # minimal list
    out = [
        {"id": c.get("id"), "name": c.get("name") or "New Chat", "updated_at": c.get("updated_at", 0)}
        for c in chats
    ]
    out.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return {"ok": True, "chats": out, "current": _current_chat_id()}

@app.route("/api/chats/new", methods=["POST"]) 
def api_chats_new():
    email = get_logged_in_email()
    if not email:
        return {"ok": False, "error": "not_authenticated"}, 401
    c = _create_new_chat(email)
    return {"ok": True, "chat": {"id": c.get("id"), "name": c.get("name")}}

@app.route("/api/chats/select", methods=["POST"]) 
def api_chats_select():
    email = get_logged_in_email()
    if not email:
        return {"ok": False, "error": "not_authenticated"}, 401
    data = request.json or {}
    cid = str(data.get("chat_id", ""))
    if not cid:
        return {"ok": False, "error": "invalid"}, 400
    chats = _load_chats(email)
    if any(c.get("id") == cid for c in chats):
        _set_current_chat_id(cid)
        return {"ok": True}
    return {"ok": False, "error": "not_found"}, 404

@app.route("/api/chats/clear", methods=["POST"]) 
def api_chats_clear():
    email = get_logged_in_email()
    if not email:
        return {"ok": False, "error": "not_authenticated"}, 401
    ok = _clear_current_chat(email)
    return {"ok": ok}



# ------------- Research & DOCX export -------------
GENERATED_DIR = os.path.join(os.getcwd(), "generated")
ensure_dir(GENERATED_DIR)
UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")
ensure_dir(UPLOADS_DIR)

def research_query_to_texts(query: str, limit: int = 6):
    text = web_search_duckduckgo(query, limit=limit)
    if isinstance(text, str):
        parts = [p.strip() for p in text.split("|") if p.strip()]
        return parts[:limit] if parts else [text]
    return [str(text)]

def research_query_to_texts_with_sources(query: str, limit: int = 6):
    """Return (texts, sources_urls) using DDGS when available.
    Falls back to research_query_to_texts without sources.
    """
    if DDGS is None:
        return research_query_to_texts(query, limit=limit), []
    texts = []
    urls = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=limit):
                body = (r.get("body") or "").strip()
                href = (r.get("href") or "").strip()
                if body:
                    texts.append(body)
                if href:
                    urls.append(href)
        # ensure bounded sizes
        return texts[:limit] if texts else ["No results found."], urls[:limit]
    except Exception:
        return research_query_to_texts(query, limit=limit), []

def save_docx_from_texts(title: str, bullets):
    if not Document:
        return None, "python-docx not installed."
    try:
        doc = Document()
        doc.add_heading(title.strip() or "Research", level=1)
        doc.add_paragraph("")
        for b in bullets:
            doc.add_paragraph(b.strip(), style=None)
        safe_name = "".join(ch for ch in title if ch.isalnum() or ch in (" ", "_", "-")).strip() or "research"
        filename = f"{safe_name[:40].replace(' ', '_')}_{int(time.time())}.docx"
        path = os.path.join(GENERATED_DIR, filename)
        doc.save(path)
        return path, None
    except Exception as e:
        return None, str(e)

@app.route("/api/research", methods=["POST"])
def api_research():
    """
    Body: { "query": "topic", "make_doc": true/false }
    Returns summaries and optional doc download path.
    """
    data = request.json or {}
    query = (data.get("query") or "").strip()
    make_doc = bool(data.get("make_doc"))
    if not query:
        return {"ok": False, "error": "missing_query"}, 400

    items = research_query_to_texts(query, limit=6)
    out = {"ok": True, "items": items}
    if make_doc:
        path, err = save_docx_from_texts(query, items)
        if path:
            # Provide relative path for download (served by Flask send_from_directory if needed)
            rel = os.path.relpath(path, os.getcwd()).replace("\\", "/")
            out["doc"] = f"/download/{rel}"
        else:
            out["doc_error"] = err or "failed_to_write_doc"
    return out

@app.route("/download/<path:filepath>", methods=["GET"])
def download_generated(filepath):
    # Only allow files inside GENERATED_DIR
    abs_path = os.path.abspath(os.path.join(os.getcwd(), filepath))
    if not abs_path.startswith(os.path.abspath(GENERATED_DIR)):
        return {"ok": False, "error": "forbidden"}, 403
    try:
        directory = os.path.dirname(abs_path)
        filename = os.path.basename(abs_path)
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        return {"ok": False, "error": str(e)}, 404

def _extract_text_from_docx(path: str) -> str:
    if not Document:
        return ""
    try:
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return ""

def _extract_text_from_pptx(path: str) -> str:
    if not Presentation:
        return ""
    try:
        prs = Presentation(path)
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    t = (shape.text or "").strip()
                    if t:
                        texts.append(t)
        return "\n".join(texts)
    except Exception:
        return ""

def _extract_text_from_pdf(path: str) -> str:
    if not PdfReader:
        return ""
    try:
        reader = PdfReader(path)
        texts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            if t.strip():
                texts.append(t.strip())
        return "\n".join(texts)
    except Exception:
        return ""

def _summarize_text(text: str, max_len: int = 1200) -> str:
    # naive summarizer: keep first N chars and compress whitespace
    if not text:
        return "No content to summarize."
    s = " ".join(text.split())
    return s[:max_len] + ("…" if len(s) > max_len else "")

def _generate_docx(title: str, bullets) -> str:
    if not Document:
        raise RuntimeError("python-docx not installed.")
    doc = Document()
    doc.add_heading(title, level=1)
    for b in bullets:
        doc.add_paragraph(b)
    safe = "".join(ch for ch in title if ch.isalnum() or ch in (" ","_","-")).strip() or "document"
    name = f"{safe[:40].replace(' ','_')}_{int(time.time())}.docx"
    path = os.path.join(GENERATED_DIR, name)
    doc.save(path)
    return path

def _generate_pptx(title: str, bullets, max_sentences_per_slide: int = 4) -> str:
    if not Presentation:
        raise RuntimeError("python-pptx not installed.")
    prs = Presentation()

    # palettes and fonts for a modern look
    palettes = [
        {"bg": RGBColor(245, 248, 255), "accent": RGBColor(62, 99, 221)},  # soft blue
        {"bg": RGBColor(250, 247, 255), "accent": RGBColor(141, 82, 255)},  # soft violet
        {"bg": RGBColor(246, 252, 250), "accent": RGBColor(10, 163, 127)},  # teal
        {"bg": RGBColor(254, 248, 246), "accent": RGBColor(242, 95, 58)},   # coral
        {"bg": RGBColor(247, 249, 252), "accent": RGBColor(45, 55, 72)},    # slate
    ]
    fonts = ["Montserrat", "Poppins", "Roboto", "Segoe UI", "Arial"]
    palette = random.choice(palettes)
    font_name = random.choice(fonts)

    # helper to create a white rounded card
    def add_card(slide, margin=Inches(0.6)):
        left = margin
        top = margin
        width = prs.slide_width - margin * 2
        height = prs.slide_height - margin * 2
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(255, 255, 255)
        card.line.fill.background()
        return card

    # infer a simple icon from the title/topic and add title
    def get_topic_icon(title_text: str) -> str:
        t = (title_text or "").lower()
        mapping = [
            ("ai", "🤖"), ("machine learning", "🤖"), ("data", "📊"), ("analytics", "📈"),
            ("climate", "🌍"), ("environment", "🌿"), ("biology", "🧬"), ("health", "🩺"),
            ("medicine", "🧪"), ("finance", "💹"), ("marketing", "📣"), ("cloud", "☁️"),
            ("security", "🔒"), ("python", "🐍"), ("java", "☕"), ("web", "🌐"),
            ("quantum", "⚛️"), ("robot", "🤖"), ("network", "🌐"), ("database", "🗄️"),
        ]
        for k, e in mapping:
            if k in t:
                return e
        return "✨"

    def add_title(slide, text, y=Inches(1.0)):
        tx = slide.shapes.add_textbox(Inches(1.1), y, prs.slide_width - Inches(2.2), Inches(1.2))
        tf = tx.text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.text = f"{get_topic_icon(title)}  {text}"
        p.alignment = PP_ALIGN.LEFT
        run = p.runs[0]
        run.font.name = font_name
        run.font.size = Pt(40)
        run.font.bold = True
        run.font.color.rgb = palette["accent"]
        return tx

    def add_icon_bullets(slide, count, top=Inches(2.1), left=Inches(0.95)):
        line_h = Inches(0.42)
        size = Inches(0.12)
        for idx in range(count):
            y = top + Inches(0.2) + line_h * idx
            dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, left, y, size, size)
            dot.fill.solid()
            dot.fill.fore_color.rgb = palette["accent"]
            dot.line.fill.background()
        return True

    def add_bullets(slide, items, top=Inches(2.1), left=Inches(1.1), width=None):
        if width is None:
            width = prs.slide_width - Inches(2.2)
        tx = slide.shapes.add_textbox(left, top, width, prs.slide_height - top - Inches(1.0))
        tf = tx.text_frame
        tf.clear()
        tf.word_wrap = True
        for idx, line in enumerate(items):
            if idx == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = line
            p.level = 0
            p.font.name = font_name
            p.font.size = Pt(22)
        add_icon_bullets(slide, len(items), top, left - Inches(0.15))
        return tx

    # Cover slide
    cover_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    cover = prs.slides.add_slide(cover_layout)
    # background
    try:
        cover.background.fill.solid()
        cover.background.fill.fore_color.rgb = palette["bg"]
    except Exception:
        pass
    add_card(cover, margin=Inches(0.7))
    add_title(cover, title, y=Inches(1.5))
    # subtitle
    sub = cover.shapes.add_textbox(Inches(1.1), Inches(2.3), prs.slide_width - Inches(2.2), Inches(0.8))
    stf = sub.text_frame
    stf.clear()
    sp = stf.paragraphs[0]
    sp.text = "Generated by Draco"
    sp.alignment = PP_ALIGN.LEFT
    srun = sp.runs[0]
    srun.font.name = font_name
    srun.font.size = Pt(20)

    # Content slides: split into sentences and batch into slides
    def split_sentences(text: str):
        raw = [s.strip() for s in re.split(r"(?<=[.!?۔؟！。]|।)\s+", text) if s.strip()]
        abbr = {"e.g.", "i.e.", "etc.", "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "vs.", "no.", "fig.", "al.", "u.s.", "u.k.", "dept.",
                "inc.", "ltd.", "co.", "est.", "approx.", "misc.", "ref.", "ed.", "pp.", "vol.", "jan.", "feb.", "mar.", "apr.", "jun.", "jul.", "aug.", "sep.", "oct.", "nov.", "dec."}
        merged = []
        for seg in raw:
            if merged and (merged[-1].lower().endswith(tuple(abbr)) or len(merged[-1]) <= 2 or re.search(r"\b[A-Z]\.\s*$", merged[-1])):
                merged[-1] = (merged[-1] + " " + seg).strip()
            else:
                merged.append(seg)
        return merged

    all_sentences = []
    for b in bullets:
        # support list of paragraphs/snippets
        all_sentences.extend(split_sentences(str(b)))

    if max_sentences_per_slide <= 0:
        max_sentences_per_slide = 4

    # batch sentences into slides
    for i in range(0, len(all_sentences), max_sentences_per_slide):
        chunk = all_sentences[i:i + max_sentences_per_slide]
        slide_palette = random.choice(palettes)
        layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[1]
        s = prs.slides.add_slide(layout)
        try:
            s.background.fill.solid()
            s.background.fill.fore_color.rgb = slide_palette["bg"]
        except Exception:
            pass
        variant = random.choice(["card", "accent_bar", "two_col", "image_text"])  # more variety
        if variant == "accent_bar":
            bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.35), prs.slide_height)
            bar.fill.solid()
            bar.fill.fore_color.rgb = slide_palette["accent"]
            bar.line.fill.background()
        card = add_card(s, margin=Inches(0.6))
        add_title(s, "Key Points", y=Inches(1.1))
        if variant == "two_col" and len(chunk) >= 2:
            mid = (len(chunk) + 1) // 2
            left_items = chunk[:mid]
            right_items = chunk[mid:]
            col_width = (prs.slide_width - Inches(2.2) - Inches(0.6)) / 2
            add_bullets(s, left_items, top=Inches(2.2), left=Inches(1.1), width=col_width)
            add_bullets(s, right_items, top=Inches(2.2), left=Inches(1.1) + col_width + Inches(0.6), width=col_width)
        elif variant == "image_text":
            # left image placeholder, right text
            img_left = Inches(1.1)
            img_top = Inches(2.2)
            img_w = Inches(3.6)
            img_h = Inches(3.0)
            ph = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, img_left, img_top, img_w, img_h)
            ph.fill.solid()
            ph.fill.fore_color.rgb = RGBColor(235, 240, 255)
            ph.line.color.rgb = slide_palette["accent"]
            txt = s.shapes.add_textbox(img_left, img_top + img_h + Inches(0.05), img_w, Inches(0.4))
            ttf = txt.text_frame
            ttf.clear()
            tp = ttf.paragraphs[0]
            tp.text = "Illustration"
            tp.font.name = font_name
            tp.font.size = Pt(12)
            # bullets on right
            add_bullets(s, chunk, top=Inches(2.2), left=img_left + img_w + Inches(0.6))
        else:
            add_bullets(s, chunk, top=Inches(2.2))

    safe = "".join(ch for ch in title if ch.isalnum() or ch in (" ","_","-")).strip() or "slides"
    name = f"{safe[:40].replace(' ','_')}_{int(time.time())}.pptx"
    path = os.path.join(GENERATED_DIR, name)
    prs.save(path)
    return path

def _generate_pdf(title: str, paragraphs) -> str:
    if not FPDF:
        raise RuntimeError("fpdf not installed.")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, txt=title, ln=True)
    pdf.ln(4)
    pdf.set_font("Arial", "", 12)
    for p in paragraphs:
        pdf.multi_cell(0, 8, txt=str(p))
        pdf.ln(1)
    safe = "".join(ch for ch in title if ch.isalnum() or ch in (" ","_","-")).strip() or "report"
    name = f"{safe[:40].replace(' ','_')}_{int(time.time())}.pdf"
    path = os.path.join(GENERATED_DIR, name)
    pdf.output(path)
    return path

    

@app.route("/api/upload_process", methods=["POST"])
def api_upload_process():
    """
    Accept a user file and optional instruction.
    Returns processed summary or a modified file for download.
    Form fields:
      - file: uploaded file
      - instruction: optional text instructions (e.g., "summarize", "shorten", etc.)
    """
    if "file" not in request.files:
        return {"ok": False, "error": "no_file"}, 400
    f = request.files["file"]
    if f.filename == "":
        return {"ok": False, "error": "empty_filename"}, 400
    instruction = (request.form.get("instruction") or "").strip().lower()
    filename = secure_filename(f.filename)
    path = os.path.join(UPLOADS_DIR, filename)
    f.save(path)

    ext = os.path.splitext(filename)[1].lower()
    text = ""
    if ext == ".docx":
        text = _extract_text_from_docx(path)
    elif ext == ".pptx":
        text = _extract_text_from_pptx(path)
    elif ext == ".pdf":
        text = _extract_text_from_pdf(path)
    else:
        return {"ok": False, "error": "unsupported_type"}, 400

    if not text:
        return {"ok": False, "error": "no_text_found"}, 400

    # simple processing
    title = os.path.splitext(filename)[0]
    if "summarize" in instruction or "summary" in instruction:
        summary = _summarize_text(text, max_len=1500)
        # also generate a doc file to return
        try:
            out = _generate_docx(f"Summary of {title}", [summary])
            rel = os.path.relpath(out, os.getcwd()).replace("\\", "/")
            return {"ok": True, "summary": summary, "doc": f"/download/{rel}"}
        except Exception:
            return {"ok": True, "summary": summary}

    # default: return content and optionally repackage to docx
    try:
        out = _generate_docx(f"Processed - {title}", [text[:6000]])
        rel = os.path.relpath(out, os.getcwd()).replace("\\", "/")
        return {"ok": True, "text": text[:3000], "doc": f"/download/{rel}"}
    except Exception:
        return {"ok": True, "text": text[:3000]}



@app.route("/api/echo", methods=["POST"])
def api_echo():
    data = request.json or {}
    return {"ok": True, "echo": data}

@app.route("/api/command", methods=["POST"])
def api_command():
    data = request.json or {}
    text = str(data.get("text", ""))
    try:
        resp = process_command(text)
        # persist bot reply in user's chat history
        user_email = get_logged_in_email()
        if user_email and not isinstance(resp, dict):
            try:
                save_chat_line(user_email, "bot", str(resp))
            except Exception:
                pass
        if isinstance(resp, dict):
            out = {"ok": True}
            out.update(resp)
            return out
        return {"ok": True, "text": resp}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

@socketio.on("connect")
def ws_connect():
    print("Client connected")
    emit("draco_response", {"text": "Draco is online and ready!"})

@socketio.on("disconnect")
def ws_disconnect():
    print("Client disconnected")

@socketio.on("user_command")
def ws_user_command(payload):
    try:
        text = payload.get("text", "")
        print("Received command from web:", text)
        response = process_command(text)
        # send a structured response (allow dict for web actions)
        if isinstance(response, dict):
            emit("draco_response", response)
        else:
            emit("draco_response", {"text": response})
        # persist bot reply for logged-in users
        user_email = get_logged_in_email()
        if user_email and not isinstance(response, dict):
            try:
                save_chat_line(user_email, "bot", str(response))
            except Exception:
                pass
    except Exception as e:
        print("Error handling user_command:", e)
        emit("draco_response", {"text": "Error processing command."})

# ------------- Background: optional voice listener thread -------------
if not ON_RENDER:
    # simple wake-word loop (optional)
    speak("Voice listener active.")
    while True:
        try:
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.6)
                print("Listening for wake word...")
                audio = r.listen(source, timeout=4, phrase_time_limit=4)
                text = ""
                try:
                    text = r.recognize_google(audio, language="en-IN").lower()
                except Exception:
                    continue
                if "draco" in text:
                    speak("Yes? Say your command.")
                    audio2 = r.listen(source, timeout=6, phrase_time_limit=8)
                    try:
                        cmd = r.recognize_google(audio2, language="en-IN")
                        print("Heard command:", cmd)
                        res = process_command(cmd)
                        speak(res)
                    except Exception:
                        speak("I couldn't understand. Try again.")
        except Exception as e:
            print("Voice loop error:", e)
            time.sleep(1)
else:
    print("Voice listener disabled on Render (no audio hardware).")
# ------------- Start-up -------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    run_kwargs = {}
    if ON_SERVER:
        run_kwargs["allow_unsafe_werkzeug"] = True
    socketio.run(app, host="0.0.0.0", port=port, **run_kwargs)