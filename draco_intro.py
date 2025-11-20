"""Draco intro / identity responses."""
from typing import Optional

INTRO_KEYWORDS = [
    "tell me about yourself",
    "introduce yourself",
    "who is your creator",
    "about draco",
    "who built you",
    "what can you do",
    "who are you",
]

INTRO_TEMPLATE = (
    "Hey, I'm Draco — a gamer-inspired productivity AI built by Aryan Sonsurkar with Kaustubh and Ritesh.\n"
    "I run the Pomodoro cup dashboard, chaos-ready BossLevel engine, mood-shifting chat, DuckDuckGo intel, and automation tricks.\n"
    "Core abilities: study timers, coding prompts, XP tracking, quests, meme/NPC events, reminders, and instant web lookups.\n"
    "Need something done? Just say the vibe (focus, break, quest, info) and I'll spin it up."
)

FUN_NOTES = [
    "Fun fact: I gamify tasks with XP, badges, and cutscenes when you level up.",
    "Fun fact: I can spawn NPC helpers like Flux or Byte when you need morale.",
    "Fun fact: my BossLevel mode swaps eras, moods, and glitch text for extra drama.",
]


def handle_intro(command: str) -> Optional[str]:
    """Return Draco's identity blurb if the command asks for it."""
    if not command:
        return None
    lower = command.lower()
    if any(key in lower for key in INTRO_KEYWORDS):
        import random

        body = INTRO_TEMPLATE
        bonus = random.choice(FUN_NOTES)
        return f"{body}\n{bonus}"
    return None
