#!/usr/bin/env python3
import asyncio
import json
import os
import shutil
import subprocess
import sys

CONFIG_DIR = os.path.expanduser("~/.config/hypr-tts")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Default configuration
DEFAULT_CONFIG = {
    "voice": "en-GB-SoniaNeural",
    "rate_multiplier": 1.35,  # e.g., 1.05 for +5%, 0.95 for -5%
    "volume": 1.25,
    "_available_female_uk_voices_info": [
        "en-GB-SoniaNeural  (Very clear and professional)",
        "en-GB-LibbyNeural  (Slightly deeper and formal)",
        "en-GB-MaisieNeural (Brighter and friendly)",
        "en-GB-MiaNeural    (Soft and conversational)"
    ]
}

# List of high quality English (UK) Female voices from edge-tts
UK_FEMALE_VOICES = [
    "en-GB-SoniaNeural",
    "en-GB-LibbyNeural",
    "en-GB-MaisieNeural",
    "en-GB-MiaNeural"
]

def load_config():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)
    
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Ensure safe fallback for missing keys
            for k, v in DEFAULT_CONFIG.items():
                if k not in config:
                    config[k] = v
            return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG

def get_selected_text():
    # 1. Try primary selection (wl-paste -p) first (highlighted text with mouse in Kitty / Wayland apps)
    try:
        res = subprocess.run(['wl-paste', '-p'], capture_output=True, text=True, check=True, timeout=1)
        text = res.stdout.strip()
        if text:
            return text
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # 2. Fallback to standard clipboard (wl-paste)
    try:
        res = subprocess.run(['wl-paste'], capture_output=True, text=True, check=True, timeout=1)
        text = res.stdout.strip()
        if text:
            return text
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return ""

def kill_previous():
    # Kill any previously running hypr-tts mpv or ffplay processes
    subprocess.run(["pkill", "-f", "hypr-tts-mpv-player"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "ffplay.*-nodisp"], stderr=subprocess.DEVNULL)

def split_into_chunks(text, max_chars=1500):
    """
    Split text into chunks of at most max_chars characters, breaking only on
    sentence boundaries (. ! ?) so edge-tts never gets truncated input.
    """
    import re
    # Split on sentence-ending punctuation, keeping the delimiter
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current = ""

    for sentence in sentences:
        # If a single sentence is itself too long, hard-split it at word boundaries
        while len(sentence) > max_chars:
            split_at = sentence.rfind(' ', 0, max_chars)
            if split_at == -1:
                split_at = max_chars
            part = sentence[:split_at].strip()
            if part:
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.append(part)
            sentence = sentence[split_at:].strip()

        if len(current) + len(sentence) + 1 > max_chars:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip() if current else sentence

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c]

async def stream_chunk_to_mpv(communicate, mpv_stdin):
    """Stream a single edge-tts Communicate object into an already-open mpv stdin."""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mpv_stdin.write(chunk["data"])
            mpv_stdin.flush()

async def main():
    config = load_config()
    text = get_selected_text()

    if not text:
        return

    # Clean text to remove common syntax characters (like asterisks, markdown, brackets)
    # so the TTS doesn't read them out loud ("asterisk", "left bracket", etc.)
    import re
    text = re.sub(r'[*_`~#\[\]<>{}]', '', text)

    kill_previous()

    # Calculate rate string for edge-tts
    rate_mult = config.get("rate_multiplier", 1.0)
    rate_percent = int(round((rate_mult - 1.0) * 100))
    rate_str = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"

    voice = config.get("voice", "en-GB-SoniaNeural")

    try:
        import edge_tts
    except ImportError:
        print("Error: edge-tts is not installed. Please install it.")
        sys.exit(1)

    # Check for available audio player (mpv, ffplay, paplay)
    player_cmd = None
    if shutil.which("mpv"):
        player_cmd = ["mpv", "--no-video", "--title=hypr-tts-mpv-player", "--no-terminal", "-"]
    elif shutil.which("ffplay"):
        player_cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-"]
    elif shutil.which("paplay"):
        player_cmd = ["paplay"]
    else:
        print("Error: No supported audio player found (mpv, ffplay, paplay). Please install one.")
        sys.exit(1)

    # Split text into safe-sized chunks to avoid edge-tts truncation
    chunks = split_into_chunks(text, max_chars=1500)

    # Open player process; stream all chunks into it sequentially
    mpv_process = subprocess.Popen(
        player_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    try:
        for chunk_text in chunks:
            communicate = edge_tts.Communicate(chunk_text, voice, rate=rate_str)
            await stream_chunk_to_mpv(communicate, mpv_process.stdin)
    except Exception as e:
        print(f"Error during TTS generation: {e}")
    finally:
        mpv_process.stdin.close()
        mpv_process.wait()

if __name__ == "__main__":
    asyncio.run(main())
