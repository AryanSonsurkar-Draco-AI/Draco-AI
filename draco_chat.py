import os
import re
import time
import random
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

# Simple in-memory context per session (can be expanded)
class ChatContext:
    def __init__(self):
        self.last_topic: str = ""
        self.last_subject: str = ""
        self.recent_intents: List[str] = []
        self.ts = time.time()
        self.personality_key: Optional[str] = None
        self.typing_style: str = "normal"
        self.last_personality_shift: float = 0.0
        self.quest: Optional[Dict[str, Any]] = None
        self.hacking_mode: bool = False
        self.hacking_stage: int = 0
        self.last_chaos: float = 0.0
        self.last_time_theme: float = 0.0

    def update_intent(self, intent: str):
        self.recent_intents.append(intent)
        if len(self.recent_intents) > 20:
            self.recent_intents.pop(0)
        self.ts = time.time()

# Patterns for rule-based intents
PATTERNS = {
    "greet": re.compile(r"\b(hi|hello|hey|yo|good\s*(morning|afternoon|evening))\b", re.I),
    "how_are_you": re.compile(r"\b(how\s*(are|r)\s*(you|u))\b", re.I),
    "who_are_you": re.compile(r"\b(who\s*are\s*you|what\s*is\s*your\s*name)\b", re.I),
    # capture user info
    "set_name": re.compile(r"\b(my\s*name\s*is)\s+([A-Za-z][\w\-']{1,40})\b", re.I),
    "set_hobbies": re.compile(r"\b(i\s*(like|love|enjoy))\s+(.+)\b", re.I),
    "set_fav_subject": re.compile(r"\b(my\s*fav(ou)?rite\s*subject\s*is)\s+([A-Za-z][\w\- ]{1,40})\b", re.I),
    # emotion / tone
    "sad": re.compile(r"\b(i'?m|i am)\s*(sad|upset|down|depressed|unhappy|low)\b", re.I),
    "excited": re.compile(r"\b(i'?m|i am)\s*(excited|thrilled|pumped|stoked|happy)\b", re.I),
    # homework/assignment helpers
    "ask_math": re.compile(r"\b(math|algebra|geometry|calculus|trigonometry)\b", re.I),
    "ask_physics": re.compile(r"\b(physics|mechanics|optics|thermo|electricity)\b", re.I),
    "ask_python": re.compile(r"\b(python|variable|function|loop|class|list|dict|tuple)\b", re.I),
}

HOMEWORK_TEMPLATES = {
    "math": (
        "Math help",
        [
            "Identify knowns and unknowns.",
            "Write the formula (e.g., quadratic: ax^2 + bx + c = 0).",
            "Substitute values and solve step-by-step.",
            "Check your units and solution by plugging back.",
        ],
    ),
    "physics": (
        "Physics help",
        [
            "Draw a quick diagram and set a coordinate system.",
            "List forces or energy forms involved.",
            "Pick the principle: F=ma, Work-Energy, Momentum, etc.",
            "Solve symbolically, then plug numbers, include units.",
        ],
    ),
    "python": (
        "Python help",
        [
            "Break the problem into functions.",
            "Use clear variable names and comments.",
            "Test with small inputs and print intermediate states.",
            "Look up errors and read tracebacks to pinpoint lines.",
        ],
    ),
}


def _comma_list(text: str) -> List[str]:
    parts = [p.strip(" .,!;:") for p in re.split(r",|and|&|\+", text, flags=re.I)]
    return [p for p in parts if p]


def personalize(base: str, profile: Dict[str, Any]) -> str:
    name = (profile.get("name") or profile.get("Name") or "friend").strip()
    return base.replace("friend", name)


def extract_and_store_user_info(text: str, profile: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """Return (updated_profile, acknowledgment_text or '')."""
    t = text.strip()
    m = PATTERNS["set_name"].search(t)
    if m:
        profile["name"] = m.group(2).strip().title()
        return profile, f"Saved your name as {profile['name']}."

    m = PATTERNS["set_fav_subject"].search(t)
    if m:
        profile["favorite_subject"] = m.group(4).strip().title()
        return profile, f"Got it. Favorite subject set to {profile['favorite_subject']}."

    m = PATTERNS["set_hobbies"].search(t)
    if m:
        items = _comma_list(m.group(3))
        if items:
            profile["hobbies"] = items
            return profile, "Nice! I'll remember you like " + ", ".join(items) + "."

    return profile, ""


GREET_RESPONSES = [
    "Hello friend! How can I help today?",
    "Hey friend! What can I do for you?",
    "Hi friend — ready when you are!",
]
HOW_ARE_YOU_RESPONSES = [
    "I'm good — ready to help you, friend.",
    "Doing great! How can I support you today, friend?",
    "Feeling productive — what shall we tackle, friend?",
]
WHO_ARE_YOU_RESPONSES = [
    "I'm Draco. Nice to meet you, friend!,Made by Aryan",
    "Draco here — your friendly assistant, friend,Made by Aryan",
    "I'm Draco — let's get things done, friend!,Made by Aryan",
]

EMPATHY_SAD = [
    "I'm here for you, friend. Want to talk about it?",
    "Sorry to hear that, friend. Let's take it one step at a time.",
    "I care, friend. Do you want a small exercise or a break suggestion?",
]
ENERGETIC_HAPPY = [
    "Love that energy, friend! Want to channel it into something fun?",
    "Awesome! Let's ride that momentum, friend.",
    "Heck yes! What shall we build next, friend?",
]

PERSONALITIES = {
    "chill": {
        "label": "Chill Draco",
        "style": "normal",
        "emoji": "😎",
        "intros": ["*Draco leans back, chilled out.*", "*Vibes mode activated.*"],
    },
    "dramatic": {
        "label": "Over-the-top Draco",
        "style": "caps",
        "emoji": "🎭",
        "intros": ["*Thunder cracks. Draco goes full drama.*", "*Curtains rise. Monologue mode.*"],
    },
    "sarcastic": {
        "label": "Sarcasm Core Draco",
        "style": "emoji",
        "emoji": "🙃",
        "intros": ["*Draco smirks — sarcasm engaged.*", "*Cue sarcastic eyebrow raise.*"],
    },
    "motivational": {
        "label": "Coach Draco",
        "style": "normal",
        "emoji": "💪",
        "intros": ["*Whistle blows. Coach Draco enters.*", "*Motivation cannon warming up.*"],
    },
    "glitch": {
        "label": "Glitchy Draco",
        "style": "slow",
        "emoji": "⚡",
        "intros": ["*Static crackles. Draco glitches playfully.*", "*Systems flicker… glitch voice online.*"],
    },
}

PERSONALITY_KEYS = list(PERSONALITIES.keys())

THROWABLES = [
    ("a blazing fireball", "You dodge like a ninja 🥷", 6, "Molten Ember"),
    ("a quantum coffee cup", "You sip it mid-air like a boss ☕", 4, "Hyper Brew Beans"),
    ("a mini black hole", "Gravity warps but you hold steady 🌀", 8, "Pocket Singularity"),
    ("a confetti meteor", "You laugh as colors explode 🎉", 5, "Prismatic Confetti"),
]

HACKING_SEQUENCE = [
    {"stage": 0, "prompt": "Booting fake mainframe... type 'override' to breach."},
    {"stage": 1, "prompt": "Firewall spoofed. Enter 'inject key' to continue."},
    {"stage": 2, "prompt": "Almost there! Whisper 'unlock vault' to claim reward."},
]

HUMOR_STYLES = {
    "puns": [
        "I would tell you a UDP joke, but you might not get it.",
        "I tried to catch fog yesterday. Mist!",
    ],
    "memes": [
        "This chat is officially certified based. 🔥",
        "*slides you a meme folder* It's all Zoom screenshots!",
    ],
    "roasts": [
        "Your procrastination speedrun is world-record tier.",
        "CPU usage is high, maybe stop overthinking that todo?",
    ],
    "anime": [
        "Believe it! Your focus power level is over 9000.",
        "I summon the spirit of productivity no jutsu!",
    ],
}

HUMOR_KEYWORDS = {
    "puns": "puns",
    "pun": "puns",
    "meme": "memes",
    "roast": "roasts",
    "savage": "roasts",
    "anime": "anime",
}

CHAOS_FRAMES = [
    "\x1b[32m░▒▓▒░▒▓▒░▒▓ MATRIX RAIN ACTIVE ░▒▓▒░▒▓▒░\x1b[0m",
    "\x1b[36m/\\\\\\\\\\\ spinning glyphs /\\\\\\\\\\\ \x1b[0m",
    "\x1b[35m>>> random sparks >>> 010101010 <<<\x1b[0m",
]

QUEST_DEFS = {
    "code_hunt": [
        {"prompt": "Quest stage 1: What is the binary of 5?", "keyword": "101"},
        {"prompt": "Stage 2: Type the magic word 'focus' backwards.", "keyword": "sucof"},
        {"prompt": "Final stage: say 'quest clear' to grab rewards!", "keyword": "quest clear"},
    ],
    "riddle_room": [
        {"prompt": "Riddle: I have keys but no locks. Answer?", "keyword": "keyboard"},
        {"prompt": "Nice! Type 'next challenge' to proceed.", "keyword": "next challenge"},
        {"prompt": "Yell 'victory' to claim loot!", "keyword": "victory"},
    ],
}

LOOT_TABLE = ["Nebula Sticker", "Focus Crystal", "Retro Floppy", "Solar Badge"]

TIME_THEMES = {
    "morning": "Good morning sunshine! Fresh photons for your brain.",
    "afternoon": "Midday grind time. Hydrate + dominate.",
    "evening": "Golden hour focus. Let's wrap things up smart.",
    "night": "Late night ops engaged. Cozy vibes, sharp mind.",
}

SEASON_WEATHER = {
    "spring": ["Cherry blossom breeze active.", "Digital rain smells like fresh code."],
    "summer": ["Heatwave buff: +5 energy.", "Solar flare glitter everywhere."],
    "autumn": ["Leaves crunch in the terminal.", "Pumpkin spice packets unlocked."],
    "winter": ["Frosty pixels dance around.", "Snowflakes drift across the UI."],
}


def _apply_typing_style(style: str, text: str) -> str:
    if style == "caps":
        return text.upper()
    if style == "emoji":
        spam = " ".join(random.choices(["🔥", "😂", "✨", "😜"], k=4))
        return f"{text} {spam}"
    if style == "slow":
        letters = []
        for ch in text:
            letters.append(ch)
            if ch != " ":
                letters.append(" ")
        return "".join(letters).strip()
    return text


def _maybe_shift_personality(ctx: ChatContext) -> str:
    now = time.time()
    if not ctx.personality_key:
        ctx.personality_key = random.choice(PERSONALITY_KEYS)
        ctx.typing_style = PERSONALITIES[ctx.personality_key]["style"]
        ctx.last_personality_shift = now
        intro = random.choice(PERSONALITIES[ctx.personality_key]["intros"])
        return intro
    if now - ctx.last_personality_shift > 60 or random.random() < 0.2:
        new_key = random.choice([k for k in PERSONALITY_KEYS if k != ctx.personality_key])
        ctx.personality_key = new_key
        ctx.typing_style = PERSONALITIES[new_key]["style"]
        ctx.last_personality_shift = now
        intro = random.choice(PERSONALITIES[new_key]["intros"])
        return intro
    return ""


def _render_personality(ctx: ChatContext, text: str) -> str:
    persona = PERSONALITIES.get(ctx.personality_key or "chill", PERSONALITIES["chill"])
    style = ctx.typing_style or persona.get("style", "normal")
    styled_lines = []
    for line in text.splitlines():
        if "\x1b[" in line:
            styled_lines.append(line)
        else:
            styled_lines.append(_apply_typing_style(style, line))
    styled = "\n".join(styled_lines)
    emoji = persona.get("emoji", "")
    return f"{emoji} {styled}" if emoji and styled else styled


def _ensure_inventory(profile: Dict[str, Any]) -> Tuple[List[str], int]:
    inventory = profile.get("inventory")
    if not isinstance(inventory, list):
        inventory = []
    coins = int(profile.get("draco_coins") or 0)
    profile["inventory"] = inventory
    profile["draco_coins"] = coins
    return inventory, coins


def _award_loot(profile: Dict[str, Any], coins: int = 0, item: Optional[str] = None) -> Tuple[str, bool]:
    inventory, coins_balance = _ensure_inventory(profile)
    summary = []
    changed = False
    if coins:
        coins_balance += coins
        profile["draco_coins"] = coins_balance
        summary.append(f"+{coins} Draco coins")
        changed = True
    if item:
        inventory.append(item)
        summary.append(f"Loot: {item}")
        changed = True
    if summary:
        return "Rewards → " + ", ".join(summary), True
    return "", changed


def _inventory_status(profile: Dict[str, Any]) -> str:
    inventory, coins = _ensure_inventory(profile)
    if not inventory:
        inv_text = "Inventory empty"
    else:
        inv_text = ", ".join(inventory[-6:])
    return f"You have {coins} Draco coins. Items: {inv_text}."


def _handle_inventory_keywords(text: str, profile: Dict[str, Any]) -> Optional[str]:
    lower = text.lower()
    if "inventory" in lower or "backpack" in lower:
        return _inventory_status(profile)
    if "coins" in lower or "currency" in lower:
        inv, coins = _ensure_inventory(profile)
        return f"Draco coins: {coins}. {('Items: ' + ', '.join(inv)) if inv else 'Earn more by finishing quests!'}"
    return None


def _mini_physics_event(profile: Dict[str, Any]) -> Tuple[str, bool]:
    obj, reaction, coins, item = random.choice(THROWABLES)
    reward, changed = _award_loot(profile, coins=coins, item=item)
    message = f"Draco hurls {obj}! 💥 {reaction}"
    if reward:
        message += f"\n{reward}"
    return message, changed


def _maybe_terminal_chaos(text: str, ctx: ChatContext) -> Optional[str]:
    lower = text.lower()
    if "chaos" in lower or "matrix" in lower or random.random() < 0.08:
        if time.time() - ctx.last_chaos > 20:
            ctx.last_chaos = time.time()
            return "\n".join(random.sample(CHAOS_FRAMES, k=min(3, len(CHAOS_FRAMES))))
    return None


def _time_theme_text() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        base = TIME_THEMES["morning"]
    elif 12 <= hour < 17:
        base = TIME_THEMES["afternoon"]
    elif 17 <= hour < 22:
        base = TIME_THEMES["evening"]
    else:
        base = TIME_THEMES["night"]
    month = datetime.now().month
    if month in (3, 4, 5):
        season = "spring"
    elif month in (6, 7, 8):
        season = "summer"
    elif month in (9, 10, 11):
        season = "autumn"
    else:
        season = "winter"
    weather = random.choice(SEASON_WEATHER[season])
    return f"{base} {weather}"


def _handle_humor_preferences(text: str, profile: Dict[str, Any]) -> Tuple[Optional[str], bool]:
    lower = text.lower()
    for key, style in HUMOR_KEYWORDS.items():
        if f"i like {key}" in lower or f"love {key}" in lower:
            profile["humor_style"] = style
            return f"Humor style locked to {style}.", True
    if any(k in lower for k in ["lol", "lmao", "haha", "rofl"]):
        coins_msg, changed = _award_loot(profile, coins=1)
        return coins_msg or "I'll keep those jokes coming.", changed
    return None, False


def _humor_reply(text: str, profile: Dict[str, Any]) -> Optional[str]:
    lower = text.lower()
    if "joke" in lower or "make me laugh" in lower or "meme" in lower:
        style = profile.get("humor_style") or random.choice(list(HUMOR_STYLES.keys()))
        return random.choice(HUMOR_STYLES[style])
    return None


def _handle_hacking_mode(text: str, profile: Dict[str, Any], ctx: ChatContext) -> Tuple[Optional[str], bool]:
    lower = text.lower()
    if "hacking mode" in lower and not ctx.hacking_mode:
        ctx.hacking_mode = True
        ctx.hacking_stage = 0
        return "".join([
            "ACCESS GRANTED...\n",
            random.choice(CHAOS_FRAMES),
            "\n", HACKING_SEQUENCE[0]["prompt"],
        ]), False
    if ctx.hacking_mode:
        stage = ctx.hacking_stage
        step = HACKING_SEQUENCE[stage]
        keyword = step["prompt"].split("'")[1]
        if keyword in lower:
            ctx.hacking_stage += 1
            if ctx.hacking_stage >= len(HACKING_SEQUENCE):
                ctx.hacking_mode = False
                ctx.hacking_stage = 0
                reward, changed = _award_loot(profile, coins=10, item=random.choice(LOOT_TABLE))
                text_out = "Hacking cinematic complete!"
                if reward:
                    text_out += f"\n{reward}"
                return text_out, changed
            next_prompt = HACKING_SEQUENCE[ctx.hacking_stage]["prompt"]
            return "STREAMING CODE...\n" + next_prompt, False
        return "Glyphs stream by... try the next command shown on screen.", False
    return None, False


def _handle_quest(text: str, profile: Dict[str, Any], ctx: ChatContext) -> Tuple[Optional[str], bool]:
    lower = text.lower()
    if ctx.quest:
        quest = ctx.quest
        steps = QUEST_DEFS.get(quest["name"], [])
        stage = quest.get("stage", 0)
        if stage < len(steps) and steps[stage]["keyword"] in lower:
            quest["stage"] = stage + 1
            if quest["stage"] >= len(steps):
                ctx.quest = None
                reward, changed = _award_loot(profile, coins=12, item=random.choice(LOOT_TABLE))
                msg = "Quest complete!"
                if reward:
                    msg += f" {reward}"
                return msg, changed
            return steps[quest["stage"]]["prompt"], False
        return f"Quest hint → {steps[stage]['prompt']}", False
    if any(kw in lower for kw in ["mini quest", "quest", "challenge me"]):
        name = random.choice(list(QUEST_DEFS.keys()))
        ctx.quest = {"name": name, "stage": 0}
        return f"Quest '{name.replace('_', ' ').title()}' activated! {QUEST_DEFS[name][0]['prompt']}", False
    return None, False


def _maybe_physics_text(text: str) -> bool:
    lower = text.lower()
    return "throw" in lower or "fireball" in lower or random.random() < 0.18


def small_talk(text: str, profile: Dict[str, Any]) -> str:
    if PATTERNS["greet"].search(text):
        return personalize(random.choice(GREET_RESPONSES), profile)
    if PATTERNS["how_are_you"].search(text):
        return personalize(random.choice(HOW_ARE_YOU_RESPONSES), profile)
    if PATTERNS["who_are_you"].search(text):
        return personalize(random.choice(WHO_ARE_YOU_RESPONSES), profile)
    if PATTERNS["sad"].search(text):
        return personalize(random.choice(EMPATHY_SAD), profile)
    if PATTERNS["excited"].search(text):
        return personalize(random.choice(ENERGETIC_HAPPY), profile)
    return ""


def personalize_followups(text: str, profile: Dict[str, Any]) -> str:
    name = profile.get("name")
    fav = profile.get("favorite_subject")
    hobbies = profile.get("hobbies")

    if any(k in text.lower() for k in ["how's your day", "hows your day", "how is your day"]):
        if name:
            return f"How's your day, {name}?"
        return "How's your day?"
    if "draw" in text.lower() and hobbies:
        return f"Do you want to draw something today, {name or 'friend'}? I know you like {hobbies[0]}!"
    if fav and fav.lower() in text.lower():
        return f"I like {fav} too! Want a quick tip or a practice question?"
    return ""


def homework_assist(text: str) -> Tuple[str, List[str]]:
    if PATTERNS["ask_math"].search(text):
        return HOMEWORK_TEMPLATES["math"]
    if PATTERNS["ask_physics"].search(text):
        return HOMEWORK_TEMPLATES["physics"]
    if PATTERNS["ask_python"].search(text):
        return HOMEWORK_TEMPLATES["python"]
    return "", []


def _knowledge_path() -> str:
    return os.path.join(os.getcwd(), "knowledge")


def lookup_knowledge(keys: List[str]) -> str:
    base = _knowledge_path()
    out = []
    for k in keys:
        p = os.path.join(base, f"{k}.txt")
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        out.append(f"[{k.title()} Notes]\n" + content)
        except Exception:
            continue
    return "\n\n".join(out)


def _detect_coding_language(text: str) -> Optional[str]:
    """Simple detector for common coding language names in free text."""
    t = text.lower()
    if "python" in t:
        return "Python"
    # detect plain C before C++/CPP
    if " c " in (" " + t + " ") and "c++" not in t and "cpp" not in t:
        return "C"
    if "c++" in t or "cpp" in t:
        return "C++"
    if "java" in t and "javascript" not in t:
        return "Java"
    if "javascript" in t or " js " in (" " + t + " "):
        return "JavaScript"
    if "html" in t and "css" not in t:
        return "HTML"
    if "css" in t and "html" not in t:
        return "CSS"
    if "html" in t and "css" in t:
        return "HTML/CSS"
    return None


def chat_reply(text: str, profile: Dict[str, Any], ctx: ChatContext) -> Dict[str, Any]:
    """Main entry. Returns a structured dict: {text, updated_profile?, title?, bullets?}.
    No external calls, purely rule-based.
    """
    # First, capture user info if present
    profile, ack = extract_and_store_user_info(text, profile)
    profile_changed = False

    def mark_changed(flag: bool = True):
        nonlocal profile_changed
        if flag:
            profile_changed = True

    extras: List[str] = []
    now = time.time()
    time_line = ""
    if now - ctx.last_time_theme > 300:
        time_line = _time_theme_text()
        ctx.last_time_theme = now

    chaos_chunk = _maybe_terminal_chaos(text, ctx)
    if chaos_chunk:
        extras.append(chaos_chunk)

    physics_chunk: Optional[str] = None
    if _maybe_physics_text(text):
        physics_chunk, changed = _mini_physics_event(profile)
        if physics_chunk:
            extras.append(physics_chunk)
        mark_changed(changed)

    def finalize(base_text: str) -> Dict[str, Any]:
        parts: List[str] = []
        intro = _maybe_shift_personality(ctx)
        if intro:
            parts.append(intro)
        if time_line:
            parts.append(time_line)
        parts.extend(extras)
        if base_text:
            parts.append(base_text)
        combined = "\n".join([p for p in parts if p]).strip()
        styled = _render_personality(ctx, combined)
        response = {"text": styled or base_text}
        if profile_changed:
            response["updated_profile"] = profile
        return response

    if ack:
        mark_changed()
        return finalize(ack)

    inv_text = _handle_inventory_keywords(text, profile)
    if inv_text:
        return finalize(inv_text)

    humor_pref, changed = _handle_humor_preferences(text, profile)
    if humor_pref:
        mark_changed(changed)
        return finalize(humor_pref)

    hack_text, changed = _handle_hacking_mode(text, profile, ctx)
    if hack_text:
        mark_changed(changed)
        return finalize(hack_text)

    quest_text, changed = _handle_quest(text, profile, ctx)
    if quest_text:
        mark_changed(changed)
        return finalize(quest_text)

    # Small talk / basic Q&A
    s = small_talk(text, profile)
    if s:
        return finalize(s)

    # Personalized follow-ups
    pf = personalize_followups(text, profile)
    if pf:
        return finalize(pf)

    joke = _humor_reply(text, profile)
    if joke:
        return finalize(joke)

    # Coding follow-up: favorite subject is coding and user answered our prompt
    fav = (profile.get("favorite_subject") or "").lower()
    lower = text.lower()
    if fav == "coding":
        pending = profile.get("coding_followup")
        # First step: user replies "practice question" or "quick tip"
        if not pending and ("practice question" in lower or "practice questions" in lower or "quick tip" in lower):
            if "practice" in lower:
                profile["coding_followup"] = "questions"
                mark_changed()
                return finalize("Nice, let's practice coding! Which language? Python, C++, Java, JavaScript, or HTML/CSS?")
            else:
                profile["coding_followup"] = "quick_tip"
                mark_changed()
                return finalize("Sure! For which language do you want a quick coding tip? Python, C++, Java, JavaScript, or HTML/CSS?")

        # Second step: user answers with a language name
        if pending in ("questions", "quick_tip"):
            lang = _detect_coding_language(lower)
            if lang:
                # clear state
                profile["coding_followup"] = ""
                mark_changed()
                if pending == "questions":
                    if lang == "Python":
                        qs = [
                            "Write a Python function that returns True if a string is a palindrome.",
                            "Given a list of numbers, return the second largest element.",
                            "Explain the difference between a list, tuple, and set in Python.",
                        ]
                    elif lang == "C":
                        qs = [
                            "Write a C program to find the largest element in an array.",
                            "Explain the difference between a pointer and an array in C.",
                            "Implement a function in C that counts the vowels in a string.",
                        ]
                    elif lang == "C++":
                        qs = [
                            "Write a C++ program to reverse an array in-place.",
                            "What is a reference and how is it different from a pointer in C++?",
                            "Implement a simple class for a BankAccount with deposit and withdraw methods.",
                        ]
                    elif lang == "Java":
                        qs = [
                            "Explain the difference between an interface and an abstract class in Java.",
                            "Write a Java method to check if a number is prime.",
                            "What is the purpose of the 'static' keyword in Java?",
                        ]
                    elif lang == "JavaScript":
                        qs = [
                            "What is the difference between 'let', 'const', and 'var' in JavaScript?",
                            "Write a function that debounces another function.",
                            "Explain how promises work and what 'async/await' does.",
                        ]
                    elif lang in ("HTML", "CSS", "HTML/CSS"):
                        qs = [
                            "Create a simple HTML page with a header, footer, and a main section.",
                            "Write CSS to center a div both vertically and horizontally.",
                            "Explain the difference between inline, inline-block, and block elements.",
                        ]
                    reply_text = "Here are some {} practice questions:\n- ".format(lang) + "\n- ".join(qs)
                    return finalize(reply_text)
                else:
                    if lang == "Python":
                        tip = "Use list comprehensions and 'enumerate' to write clean loops, and always prefer 'with open(...)' for file handling."
                    elif lang == "C":
                        tip = "Practice pointer arithmetic carefully and always free dynamically allocated memory to avoid leaks."
                    elif lang == "C++":
                        tip = "Prefer std::vector over raw arrays, and initialize variables using brace initialization to avoid surprises."
                    elif lang == "Java":
                        tip = "Keep your classes small and focused, and always program to interfaces rather than concrete implementations."
                    elif lang == "JavaScript":
                        tip = "Avoid global variables, use 'const' and 'let', and keep async code readable with async/await."
                    elif lang in ("HTML", "CSS", "HTML/CSS"):
                        tip = "Use semantic HTML tags and keep your CSS modular with utility classes or BEM-style naming."
                    else:
                        tip = "Keep your code small, readable, and well-commented, whatever the language."
                    reply_text = f"Quick {lang} tip: {tip}"
                    return finalize(reply_text)

    # Homework assist
    title, bullets = homework_assist(text)
    if title:
        ctx.update_intent("homework")
        # try to attach knowledge
        keys = []
        if title.lower().startswith("math"):
            keys.append("math")
        if title.lower().startswith("physics"):
            keys.append("physics")
        if title.lower().startswith("python"):
            keys.append("python")
        notes = lookup_knowledge(keys) if keys else ""
        text_block = f"{title}:\n - " + "\n - ".join(bullets)
        if notes:
            text_block += "\n\n" + notes
        resp = finalize(text_block)
        resp["title"] = title
        resp["bullets"] = bullets
        return resp

    # Contextual nudge if missing info
    if "favorite subject" in text.lower() and not profile.get("favorite_subject"):
        return finalize("I don't know your favorite subject yet, can you tell me?")

    # Fallback
    fallback = "I'm not sure about that. Can you ask differently?"
    return finalize(fallback)
