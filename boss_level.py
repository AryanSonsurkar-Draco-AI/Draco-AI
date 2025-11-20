import random
import time
from typing import Dict, Any, Optional, List

TIME_ERAS = [
    {
        "name": "medieval",
        "prefix": "[Year 1287 · Royal Scroll]",
        "tone": "Thou hast issued a decree: {command}.",
    },
    {
        "name": "retro_80s",
        "prefix": "[1986 · Neon Terminal]",
        "tone": "{command} // Bootleg synthwave vibes initialized.",
    },
    {
        "name": "future",
        "prefix": "[2199 · Quantum Console]",
        "tone": "Command '{command}' encoded in photonic data stream.",
    },
    {
        "name": "steampunk",
        "prefix": "[Cogwheel Era]",
        "tone": "Steam valves hiss as '{command}' is etched into brass.",
    },
]

MOOD_STYLES = [
    "[Sarcastic mode]",
    "[Wholesome coach]",
    "[Spooky whisper]",
    "[Hyperactive hype]",
]

MEME_REACTIONS = [
    "Big brain moment 💡",
    "Bruh 😳",
    "Distracted programmer meme intensifies.",
    "Galaxy brain sequence unlocked.",
]

ASCII_ANIMATIONS = [
    "🔥  ~\\~  ~/~  flames flicker in ASCII",
    "➡️ ➡️ ➡️  data arrows sweep across the screen",
    "\\\\    dragon wings flap    //",
]

NPC_POOL = [
    "Flux the Gremlin Engineer",
    "Byte the Mini Dragon",
    "Captain Stacktrace",
    "Sir NullPointer",
]

CHAOS_EVENTS = [
    "Suddenly the terminal showers confetti 🎉",
    "Draco sneezes and flips your todo list!",
    "A wormhole opens, rearranging your emojis.",
]

SECRET_REFERENCES = {
    "konami": "You entered the Konami code... extra lives granted (metaphorically).",
    "nani": "NANI?! Power levels spike dramatically!",
    "portal": "The cake is still a lie, but I brought cupcakes.",
    "java": "One does not simply escape NullPointerException.",
}

REACTION_GIFS = [
    "[GIF] (╯°□°)╯︵ ┻━┻",
    "[GIF] (☞ﾟヮﾟ)☞",
    "[GIF] (ง'̀-'́)ง",
    "[GIF] ¯\\_(ツ)_/¯",
]

class BossLevelEngine:
    def __init__(self) -> None:
        self.last_time_travel = 0.0
        self.last_glitch = 0.0

    def _ensure_state(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        state = profile.setdefault("boss_level", {})
        state.setdefault("xp", 0)
        state.setdefault("level", 1)
        state.setdefault("coins", 0)
        state.setdefault("hp", 24)
        state.setdefault("inventory", [])
        state.setdefault("reputation", {
            "jokes": 0,
            "todos_exploded": 0,
            "commands_glitched": 0,
        })
        state.setdefault("mood", "neutral")
        state.setdefault("time_era", "modern")
        state.setdefault("npc_index", 0)
        return state

    # -------------------- helpers --------------------
    def _glitch_text(self, text: str) -> str:
        chars = []
        for ch in text:
            if ch.isalpha() and random.random() < 0.1:
                chars.append(ch.upper())
                chars.append(random.choice([ch.lower(), ch.upper(), ch + ch]))
            elif random.random() < 0.03:
                chars.append("…")
            else:
                chars.append(ch)
        return "".join(chars)

    def _time_travel_line(self, command: str, state: Dict[str, Any]) -> str:
        era = random.choice(TIME_ERAS)
        state["time_era"] = era["name"]
        self.last_time_travel = time.time()
        return f"{era['prefix']} {era['tone'].format(command=command)}"

    def _mood_music(self, state: Dict[str, Any]) -> str:
        vibes = [
            "🎵 Intense boss-battle strings surge!",
            "🎶 Soft lo-fi beats wrap around the terminal.",
            "🥁 Drumline of productivity rattles on your desk.",
            "🎷 Jazzy improv while you debug.",
        ]
        return random.choice(vibes)

    def _chat_animation(self) -> str:
        return random.choice(ASCII_ANIMATIONS)

    def _npc_line(self, state: Dict[str, Any]) -> str:
        npc = NPC_POOL[state["npc_index"] % len(NPC_POOL)]
        state["npc_index"] = state["npc_index"] + 1
        return f"{npc} pops in: 'Need backup on this command?'"

    def _chaos_event(self) -> str:
        return random.choice(CHAOS_EVENTS)

    def _meme_injection(self) -> str:
        return random.choice(MEME_REACTIONS)

    def _reaction_gif(self) -> str:
        return random.choice(REACTION_GIFS)

    def _maybe_prank(self, state: Dict[str, Any]) -> Optional[str]:
        pranks = [
            "Fake error: 410 Coffee Gone. Just kidding ☕",
            "Typing delay engaged... nah, instant reply!",
            "Misleading tip: Always debug by deleting your code. (Please don't).",
        ]
        return random.choice(pranks) if random.random() < 0.3 else None

    def _secret_reference(self, lower: str) -> Optional[str]:
        for key, msg in SECRET_REFERENCES.items():
            if key in lower:
                return msg
        return None

    def _command_roulette(self, cmd: str, lower: str, state: Dict[str, Any]) -> Optional[str]:
        if not cmd.startswith("/"):
            return None
        base = cmd[1:]
        state["reputation"]["commands_glitched"] += 1
        options = [
            f"Roulette twist! Instead of {cmd}, Draco hands you a riddle: What runs but never walks?",  # answer: river
            f"{cmd} detonated! Your todo list turns into paper airplanes.",
            f"{cmd} morphs into a motivational speech about rubber ducks.",
            f"{cmd}? Nah. Have a wholesome compliment: you're crushing this quest.",
        ]
        return random.choice(options)

    def _update_reputation(self, lower: str, state: Dict[str, Any]) -> None:
        if "joke" in lower or "meme" in lower:
            state["reputation"]["jokes"] += 1
        if "todo" in lower:
            state["reputation"]["todos_exploded"] += random.randint(0, 1)

    def _grant_xp(self, state: Dict[str, Any], amount: int) -> str:
        state["xp"] += amount
        cutscene = ""
        threshold = 25 + (state["level"] * 10)
        if state["xp"] >= threshold:
            state["xp"] -= threshold
            state["level"] += 1
            cutscene = (
                f"[Level Up Cutscene] Streaks of light swirl as you reach Level {state['level']}! "
                "NPCs cheer, confetti cannons fire, and Draco salutes heroically."
            )
        return cutscene

    def _rpg_battle(self, lower: str, state: Dict[str, Any]) -> Optional[str]:
        triggers = ("fight" in lower or "monster" in lower or "rpg" in lower or "boss" in lower)
        if not triggers and random.random() > 0.18:
            return None
        monsters = [
            ("Bug Hydra", 12),
            ("Deadline Dragon", 15),
            ("Syntax Slime", 8),
        ]
        monster, hp = random.choice(monsters)
        dmg = random.randint(2, 7)
        hp -= dmg
        xp_gain = random.randint(6, 15)
        coins = random.randint(1, 5)
        loot = random.choice(["Glowing Typo Crystal", "Quantum Sticky Note", "Debugging Cape"])
        state["coins"] += coins
        state["inventory"].append(loot)
        cutscene = self._grant_xp(state, xp_gain)
        battle = (
            f"Mini RPG: You slash at {monster} for {dmg} dmg. It flees with {max(hp,0)} HP. "
            f"Loot: {loot} (+{coins} coins, +{xp_gain} XP)."
        )
        return "\n".join(filter(None, [battle, cutscene]))

    def _apply_mood_swaps(self, segments: List[str]) -> str:
        mixed = []
        moods = MOOD_STYLES.copy()
        random.shuffle(moods)
        for seg in segments:
            tag = moods[random.randint(0, len(moods) - 1)]
            mixed.append(f"{tag} {seg}")
        return "\n".join(mixed)

    def _maybe_glitch_response(self, text: str, lower: str) -> str:
        if "glitch" in lower or random.random() < 0.15:
            return self._glitch_text(text)
        return text

    def _reputation_summary(self, state: Dict[str, Any]) -> str:
        rep = state["reputation"]
        return (
            f"Reputation stats → jokes asked: {rep['jokes']}, "
            f"todo chaos: {rep['todos_exploded']}, cmds glitched: {rep['commands_glitched']}"
        )

    # -------------------- public API --------------------
    def handle(self, cmd: str, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        lower = cmd.lower()
        state = self._ensure_state(profile)
        self._update_reputation(lower, state)

        segments: List[str] = []
        triggered = False

        roulette = self._command_roulette(cmd, lower, state)
        if roulette:
            segments.append(roulette)
            triggered = True

        if "time travel" in lower or (time.time() - self.last_time_travel > 90 and random.random() < 0.25):
            segments.append(self._time_travel_line(cmd, state))
            triggered = True

        rpg = self._rpg_battle(lower, state)
        if rpg:
            segments.append(rpg)
            triggered = True

        if "meme" in lower or random.random() < 0.2:
            segments.append(self._meme_injection())
            triggered = True

        if "npc" in lower or random.random() < 0.25:
            segments.append(self._npc_line(state))
            triggered = True

        if "chaos" in lower or random.random() < 0.1:
            segments.append(self._chaos_event())
            triggered = True

        prank = self._maybe_prank(state)
        if prank:
            segments.append(prank)
            triggered = True

        secret = self._secret_reference(lower)
        if secret:
            segments.append(secret)
            triggered = True

        if not triggered:
            return None

        segments.append(self._chat_animation())
        segments.append(self._mood_music(state))
        segments.append(self._reaction_gif())
        segments.append(self._reputation_summary(state))

        text = self._apply_mood_swaps(segments)
        final = self._maybe_glitch_response(text, lower)
        return {"text": final, "updated_profile": profile}
