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
from collections import deque
from typing import Optional

from flask import Flask, send_from_directory, request
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
try:
    import psutil
except Exception:
    psutil = None
try:
    import pyautogui
except Exception:
    pyautogui = None
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

# ------------- Flask / SocketIO -------------
app = Flask(__name__, static_folder=".", template_folder=".")
socketio = SocketIO(app, cors_allowed_origins="*")

# ------------- Global utilities & config -------------
MEMORY_FILE = "memory.json"
NOTES_FILE = "notes.json"
REMINDERS_FILE = "reminders.json"
WEATHER_API_KEY = ""   # add your OpenWeatherMap key if desired
NEWSAPI_KEY = ""       # add your News API key if desired

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
if pyttsx3:
    engine = pyttsx3.init()
else:
    engine = None

def emit_to_ui(key: str, payload: dict):
    try:
        socketio.emit(key, payload)
    except Exception as e:
        print("Emit error:", e)

def speak(text: str, announce_to_ui: bool = True):
    """Use local TTS (pyttsx3) and send message to UI. Single source of speak()."""
    print("[Draco-SPEAK]", text)
    if announce_to_ui:
        emit_to_ui("draco_response", {"text": text})
    try:
        if engine:
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

def send_whatsapp_message(phone: str, message: str):
    """Open WhatsApp web chat to phone with message (uses wa.me). Works if user is logged-in."""
    # phone should be in international format without +, e.g., 919xxxxxxxxx
    msg = webbrowser.quote(message)
    url = f"https://wa.me/{phone}?text={msg}"
    webbrowser.open(url)
    return f"Opening WhatsApp chat for {phone}. Please confirm send in browser."

def open_linkedin():
    webbrowser.open("https://linkedin.com")
    return "Opened LinkedIn."

# ------------- Music integration -------------
def play_music_from_library(song_name: Optional[str] = None):
    if musicLibrary:
        try:
            if song_name:
                return musicLibrary.play(song_name)
            else:
                return musicLibrary.play()
        except Exception as e:
            return f"musicLibrary error: {e}"
    else:
        return "musicLibrary not found. Add musicLibrary.py with play/pause/stop functions."

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
    memory.add(f"You: {raw_cmd}")
    personality.update(cmd)

    # greetings / small talk
    if any(x in cmd for x in ["hello", "hi", "hey"]):
        reply = personality.respond(f"Hello {memory.get_pref('name', 'friend')}! How can I help?")
        speak(reply)
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
        r = open_youtube()
        speak(personality.respond(r))
        return r
    if "open instagram" in cmd:
        r = open_instagram()
        speak(personality.respond(r))
        return r
    if "open linkedin" in cmd:
        r = open_linkedin()
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
            r = send_whatsapp_message(phone, message)
            speak(r)
            return r
        else:
            return "Please provide phone number and message. Example: send whatsapp to 919123456789 message Hello"

    # music
    if "play music" in cmd or "play song" in cmd:
        # allow "play music <name>"
        name = None
        if "play music " in cmd:
            name = cmd.split("play music ", 1)[1].strip()
        elif "play song " in cmd:
            name = cmd.split("play song ", 1)[1].strip()
        r = play_music_from_library(name)
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
    # serve draco.html in current dir
    return send_from_directory(".", "draco.html")

@app.route("/api/echo", methods=["POST"])
def api_echo():
    data = request.json or {}
    return {"ok": True, "echo": data}

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
        # send a structured response
        emit("draco_response", {"text": response})
    except Exception as e:
        print("Error handling user_command:", e)
        emit("draco_response", {"text": "Error processing command."})

# ------------- Background: optional voice listener thread -------------
def voice_listener_loop():
    if sr is None:
        print("SpeechRecognition not installed; voice listener disabled.")
        return
    r = sr.Recognizer()
    mic = None
    try:
        with sr.Microphone() as source:
            mic = source
    except Exception as e:
        print("Microphone init failed:", e)
        return

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
                    # listen for the command
                    audio2 = r.listen(source, timeout=6, phrase_time_limit=8)
                    try:
                        cmd = r.recognize_google(audio2, language="en-IN")
                        print("Heard command:", cmd)
                        res = process_command(cmd)
                        speak(res)
                    except Exception as e:
                        speak("I couldn't understand. Try again.")
        except Exception as e:
            print("Voice loop error:", e)
            time.sleep(1)

# ------------- Start-up -------------
from flask_socketio import SocketIO
import os

socketio = SocketIO(app, cors_allowed_origins="*")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)