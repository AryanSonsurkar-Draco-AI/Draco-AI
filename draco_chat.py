import os
import re
import time
import random
from typing import Dict, Any, Tuple, List

# Simple in-memory context per session (can be expanded)
class ChatContext:
    def __init__(self):
        self.last_topic: str = ""
        self.last_subject: str = ""
        self.recent_intents: List[str] = []
        self.ts = time.time()

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
    if ack:
        return {"text": ack, "updated_profile": profile}

    # Small talk / basic Q&A
    s = small_talk(text, profile)
    if s:
        return {"text": s}

    # Personalized follow-ups
    pf = personalize_followups(text, profile)
    if pf:
        return {"text": pf}

    # Coding follow-up: favorite subject is coding and user answered our prompt
    fav = (profile.get("favorite_subject") or "").lower()
    lower = text.lower()
    if fav == "coding":
        pending = profile.get("coding_followup")
        # First step: user replies "practice question" or "quick tip"
        if not pending and ("practice question" in lower or "practice questions" in lower or "quick tip" in lower):
            if "practice" in lower:
                profile["coding_followup"] = "questions"
                return {
                    "text": "Nice, let's practice coding! Which language? Python, C++, Java, JavaScript, or HTML/CSS?",
                    "updated_profile": profile,
                }
            else:
                profile["coding_followup"] = "quick_tip"
                return {
                    "text": "Sure! For which language do you want a quick coding tip? Python, C++, Java, JavaScript, or HTML/CSS?",
                    "updated_profile": profile,
                }

        # Second step: user answers with a language name
        if pending in ("questions", "quick_tip"):
            lang = _detect_coding_language(lower)
            if lang:
                # clear state
                profile["coding_followup"] = ""
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
                    return {"text": reply_text, "updated_profile": profile}
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
                    return {"text": reply_text, "updated_profile": profile}

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
        return {"text": text_block, "title": title, "bullets": bullets}

    # Contextual nudge if missing info
    if "favorite subject" in text.lower() and not profile.get("favorite_subject"):
        return {"text": "I don't know your favorite subject yet, can you tell me?"}

    # Fallback
    return {"text": "I'm not sure about that. Can you ask differently?"}
