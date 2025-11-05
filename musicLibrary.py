import webbrowser
from typing import Optional

music = {
    "stealth": "https://www.youtube.com/watch?v=U47Tr9BB_wE",
    "march": "https://www.youtube.com/watch?v=Xqeq4b5u_Xw",
    "skyfall": "https://www.youtube.com/watch?v=DeumyOzKqgI&pp=ygUHc2t5ZmFsbA%3D%3D",
    "wolf": "https://www.youtube.com/watch?v=ThCH0U6aJpU&list=PLnrGi_-oOR6wm0Vi-1OsiLiV5ePSPs9oF&index=21",
    "stressed out": "https://www.youtube.com/watch?v=pXRviuL6vMY",
    "let me down slowly": "https://www.youtube.com/watch?v=KkGVmN68ByU",
    "it ain't me": "https://www.youtube.com/watch?v=DJyR0kJ0mT0",
    "bad liar": "https://www.youtube.com/watch?v=TvPx0c87PXI",
    "wolves": "https://www.youtube.com/watch?v=cHHLHGNpCSA",
    "friends": "https://www.youtube.com/watch?v=0yW7w8F2TVA",
    "let me love you": "https://www.youtube.com/watch?v=0yW7w8F2TVA",
    "there's nothing holding me back": "https://www.youtube.com/watch?v=6xKWiCMKKJg",
    "paris": "https://www.youtube.com/watch?v=ColJ1l7Trrg",
    "in the name of love": "https://www.youtube.com/watch?v=UxxajLWwzqY",
    "hate me": "https://www.youtube.com/watch?v=KxO0SKu0TnY",
    "faded": "https://www.youtube.com/watch?v=60ItHLz5WEA",
    "alone": "https://www.youtube.com/watch?v=1-xGerv5FOk",
    "lily": "https://www.youtube.com/watch?v=fQ9vQkJzz8s",
    "the spectre": "https://www.youtube.com/watch?v=wJnBTPUQS5A",
    "on my way": "https://www.youtube.com/watch?v=3QnD2c4Xovk",
    "sing me to sleep": "https://www.youtube.com/watch?v=2i2khp_npdE",
    "play": "https://www.youtube.com/watch?v=0ROxY4VnR6M",
    "darkside": "https://www.youtube.com/watch?v=M-P4QBt-FWk",
    "diamond heart": "https://www.youtube.com/watch?v=ihYplb7lI7c",
    "all falls down": "https://www.youtube.com/watch?v=UKzkz9bOG0E",
    "alone pt ii": "https://www.youtube.com/watch?v=HkH2B3jF7tQ",
    "ignite": "https://www.youtube.com/watch?v=H9tEvfIsDyo",
    "tired": "https://www.youtube.com/watch?v=ZJcKXyPtGfA",
    "unity": "https://www.youtube.com/watch?v=UKtkD6hR4fM",
    "fly away": "https://www.youtube.com/watch?v=8V1C1rYAmR0",
    "the calling": "https://www.youtube.com/watch?v=V4tV5l1mFvk",
    "monody": "https://www.youtube.com/watch?v=F7ZQ_6xEhJk",
    "rise up": "https://www.youtube.com/watch?v=G6f9jafhQEc",
    "jackpot": "https://www.youtube.com/watch?v=kXijq3aUuO0",
    "oblivion": "https://www.youtube.com/watch?v=Wlm2t4bq2kY",
    "no no no": "https://www.youtube.com/watch?v=fxeF8b2tqkQ",
    "arcadia": "https://www.youtube.com/watch?v=3VfZ7zGqazM",
    "stronger": "https://www.youtube.com/watch?v=RIwOKyq9A8A",
    "never be alone": "https://www.youtube.com/watch?v=9QpQs0M6mZc",
    "waiting for love": "https://www.youtube.com/watch?v=cHHLHGNpCSA",
    "wake me up": "https://www.youtube.com/watch?v=IcrbM1l_BoI",
    "the nights": "https://www.youtube.com/watch?v=UtF6Jej8yb4",
    "hey brother": "https://www.youtube.com/watch?v=4yJk9ayg3zs",
    "levels": "https://www.youtube.com/watch?v=_ovdm2yX4MA",
    "don't you worry child": "https://www.youtube.com/watch?v=1y6smkh6c-0",
    "something just like this": "https://www.youtube.com/watch?v=FM7MFYoylVs",
    "closer": "https://www.youtube.com/watch?v=0zGcUoRlhmw",
    "stay": "https://www.youtube.com/watch?v=h--P8HzYZ74",
    "ocean": "https://www.youtube.com/watch?v=5yU5Z6ky5D4",
    "animals": "https://www.youtube.com/watch?v=gCYcHz2k5x0",
    "scared to be lonely": "https://www.youtube.com/watch?v=6MX9s9vHSPw",
    "happier": "https://www.youtube.com/watch?v=7qFfFVSerQo",
    "shivers": "https://www.youtube.com/watch?v=pmxjzD8ZpPI",
    "savage love": "https://www.youtube.com/watch?v=gUci-tsiU4I",
    "pepperoni": "https://www.youtube.com/watch?v=Uj1ykZWtPYI",
    "cold heart": "https://www.youtube.com/watch?v=Fg6p3dU4s5k",
    "takeaway": "https://www.youtube.com/watch?v=GmYojESn0l8",
    "love me like you do": "https://www.youtube.com/watch?v=AJtDXIazrMo",
    "blinding lights": "https://www.youtube.com/watch?v=4NRXx6U8ABQ",
    "save your tears": "https://www.youtube.com/watch?v=XXYlFuWEuKI",
    "peaches": "https://www.youtube.com/watch?v=tQ0yjYUFKAE",
    "drivers license": "https://www.youtube.com/watch?v=ZmDBbnmKpqQ",
    "good 4 u": "https://www.youtube.com/watch?v=gNi_6U5Pm_o",
    "as it was": "https://www.youtube.com/watch?v=H5v3kku4y6Q",
    "abcdefu": "https://www.youtube.com/watch?v=1c8t4YlJ-7A",
    "faded pt ii": "https://www.youtube.com/watch?v=V8v8Rr1p5fQ",
    "midnight city": "https://www.youtube.com/watch?v=dX3k_QDnzHE",
    "sunflower": "https://www.youtube.com/watch?v=ApXoWvfEYVU",
    "levitate": "https://www.youtube.com/watch?v=cQx9DQydEOM",
    "swami": "https://www.youtube.com/watch?v=WY7mogD-o3I&list=RDWY7mogD-o3I&start_radio=1&pp=ygUFc3dhbWmgBwE%3D"
}

def _find_song_url_by_name(name: str) -> Optional[str]:
    key = name.strip().lower()
    if key in music:
        return music[key]
    # substring fuzzy match
    for k, url in music.items():
        if key in k:
            return url
    return None

def play(song_name: Optional[str] = None) -> str:
    if song_name:
        url = _find_song_url_by_name(song_name)
        if not url:
            return f"Song not found: {song_name}"
        webbrowser.open(url)
        return f"Playing: {song_name}"
    # default: open a random/first track
    first_url = next(iter(music.values()))
    webbrowser.open(first_url)
    return "Playing music."

def pause() -> None:
    # Not controllable from here when opened in a browser
    pass

def stop() -> None:
    # Not controllable from here when opened in a browser
    pass