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
from collections import deque
from typing import Optional

from flask import Flask, send_from_directory, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit

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
EMAIL_CODES_FILE = os.path.join(os.getcwd(), "email_codes.json")

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

    # time/date
    if "time" in cmd and "what" in cmd or cmd == "time":
        t = datetime.datetime.now().strftime("%I:%M %p")
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

    if "lock pc" in cmd or "lock" == cmd:
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
    # Redirect to login if not authenticated
    if not get_logged_in_email():
        return redirect(url_for("login_page"))
    return send_from_directory(".", "draco.html")

@app.route("/login")
def login_page():
    return send_from_directory(".", "login.html")

@app.route("/logout")
def logout_page():
    session.clear()
    return redirect(url_for("login_page"))

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

def _email_codes():
    return safe_read_json(EMAIL_CODES_FILE, {})

def _save_email_codes(d):
    safe_write_json(EMAIL_CODES_FILE, d)

def _send_code_via_email(email: str, code: str) -> None:
    # Best-effort: print to console. Optionally send via SMTP if configured.
    print(f"[LOGIN] Verification code for {email}: {code}")
    # Optional SMTP: set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
    host = os.environ.get("SMTP_HOST")
    if not host:
        return
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(f"Your Draco login code is: {code}\nThis code expires in 10 minutes.")
        msg["Subject"] = "Your Draco verification code"
        msg["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "draco@login"))
        msg["To"] = email
        port = int(os.environ.get("SMTP_PORT", "587"))
        user = os.environ.get("SMTP_USER")
        pwd = os.environ.get("SMTP_PASS")
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            if user and pwd:
                s.login(user, pwd)
            s.sendmail(msg["From"], [email], msg.as_string())
    except Exception as e:
        print("SMTP send failed:", e)

@app.route("/auth/email/start", methods=["POST"]) 
def auth_email_start():
    data = request.json or {}
    email = str(data.get("email", "")).strip().lower()
    if not email or "@" not in email:
        return {"ok": False, "error": "invalid_email"}, 400
    codes = _email_codes()
    code = str(random.randint(100000, 999999))
    codes[email] = {"code": code, "ts": time.time()}
    _save_email_codes(codes)
    _send_code_via_email(email, code)
    return {"ok": True}

@app.route("/auth/email/verify", methods=["POST"]) 
def auth_email_verify():
    data = request.json or {}
    email = str(data.get("email", "")).strip().lower()
    code = str(data.get("code", "")).strip()
    codes = _email_codes()
    rec = codes.get(email)
    if not rec:
        return {"ok": False, "error": "start_first"}, 400
    if rec.get("code") != code:
        return {"ok": False, "error": "wrong_code"}, 400
    if time.time() - float(rec.get("ts", 0)) > 600:
        return {"ok": False, "error": "expired"}, 400
    # success: log user in
    session["user_email"] = email
    # initialize storage
    _ = user_paths(email)
    # Remove used code
    try:
        codes.pop(email, None)
        _save_email_codes(codes)
    except Exception:
        pass
    return {"ok": True}

@app.route("/auth/google")
def auth_google_start():
    # Placeholder: requires OAuth client setup. Redirect to login with message if not configured.
    return redirect(url_for("login_page"))

@app.route("/auth/microsoft")
def auth_microsoft_start():
    # Placeholder: requires OAuth client setup. Redirect to login with message if not configured.
    return redirect(url_for("login_page"))

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