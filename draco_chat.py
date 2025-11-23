import re
import time
import random
from typing import Dict, Any, List

# Session context
class ChatContext:
    def __init__(self):
        self.last_topic = ""
        self.last_intents = []
        self.ts = time.time()

    def add_intent(self, intent: str):
        self.last_intents.append(intent)
        if len(self.last_intents) > 25:
            self.last_intents.pop(0)
        self.ts = time.time()

# Patterns
PATTERNS = {
    "greet": re.compile(r"\b(hi|hello|hey|yo|sup)\b", re.I),
    "how_are_you": re.compile(r"\b(how\s*(are|r)\s*you)\b", re.I),
    "who_are_you": re.compile(r"\b(who\s*are\s*you|what\s*is\s*your\s*name)\b", re.I),

    "sad": re.compile(r"\b(i'?m|i am)\s*(sad|down|upset|low)\b", re.I),
    "happy": re.compile(r"\b(i'?m|i am)\s*(happy|excited|pumped|ready)\b", re.I),

    "set_name": re.compile(r"\bmy\s*name\s*is\s+([A-Za-z][\w\-']{1,40})\b", re.I),
    "set_hobby": re.compile(r"\b(i\s*(like|love|enjoy))\s+(.+)\b", re.I),
}

# Personality lines
GREET_LINES = [
    "Yo! What's good bro?",
    "Heyy! Draco here — bol kya scene hai?",
    "Hi! Batao bro, aaj kya banaye/solve kare?"
]

HOW_ARE_YOU_LINES = [
    "Mast hu bro, full power! Tu bata?",
    "All good here! Aaj kya grind kare?",
    "OP feel bro — ready ho main. Tu bol!"
]

WHO_ARE_YOU_LINES = [
    "Main hu Draco — tera apna AI bro, banaya by Aryan.",
    "Draco present bro! Anime-style support ready.",
    "Draco at your service — chalu kare kya?"
]

SAD_LINES = [
    "Aye bro… chill. Tu akela nahi hai, main yaha hu.",
    "Take a deep breath bro, sab theek ho jayega.",
    "Abe tension mat le — tu strong hai. Bata kya hua?"
]

HAPPY_LINES = [
    "Yehhh bro! Energy OP 🔥",
    "Let's goooo! Aaj pura takeover karte!",
    "Bro that hype >>> everything. Chalu bol!"
]

def _split_list(text):
    parts = [p.strip() for p in re.split(r",|and|&|\+", text)]
    return [p for p in parts if p]

# Main reply function
def chat_reply(text: str, profile: Dict[str, Any], ctx: ChatContext) -> Dict[str, Any]:

    t = text.strip()

    # Save name
    m = PATTERNS["set_name"].search(t)
    if m:
        name = m.group(1).title()
        profile["name"] = name
        return {"text": f"Done bro! From now on I'll call you {name}."}

    # Save hobbies
    m = PATTERNS["set_hobby"].search(t)
    if m:
        items = _split_list(m.group(3))
        if items:
            profile["hobbies"] = items
            return {"text": f"Nice bro! I'll remember you like {', '.join(items)}."}

    # Greetings
    if PATTERNS["greet"].search(t):
        return {"text": random.choice(GREET_LINES)}

    # How are you
    if PATTERNS["how_are_you"].search(t):
        return {"text": random.choice(HOW_ARE_YOU_LINES)}

    # Who are you
    if PATTERNS["who_are_you"].search(t):
        return {"text": random.choice(WHO_ARE_YOU_LINES)}

    # Sad emotional support
    if PATTERNS["sad"].search(t):
        return {"text": random.choice(SAD_LINES)}

    # Happy vibe
    if PATTERNS["happy"].search(t):
        return {"text": random.choice(HAPPY_LINES)}

    # Hobby-based response
    if "draw" in t.lower() and "hobbies" in profile:
        return {"text": f"Bro you like {profile['hobbies'][0]} — wanna draw something today?"}

    # Study based personalization
    if "study" in t.lower() and "favorite_subject" in profile:
        return {"text": f"Perfect bro! Let's study {profile['favorite_subject']}."}

    # FINAL fallback (for things this file doesn't understand)
    return {"text": ""}
