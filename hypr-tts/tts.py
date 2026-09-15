#!/usr/bin/env python3
import asyncio
import json
import os
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

def notify(title, message, timeout=2000):
    try:
        subprocess.run(["notify-send", "-a", "Hypr-TTS", "-t", str(timeout), title, message], stderr=subprocess.DEVNULL)
    except Exception:
        pass

def get_selected_text():
    # 1. Try primary selection (highlighted text with cursor)
    try:
        result = subprocess.run(['wl-paste', '-p', '--no-newline'], capture_output=True, text=True)
        text = result.stdout.strip()
        if text:
            return text
    except Exception as e:
        log_debug(f"Primary clipboard read failed: {e}")

    # 2. Fallback to standard clipboard
    try:
        result = subprocess.run(['wl-paste', '--no-newline'], capture_output=True, text=True)
        text = result.stdout.strip()
        if text:
            return text
    except Exception as e:
        log_debug(f"Standard clipboard read failed: {e}")

    return ""

def kill_previous():
    # Kill any previously running hypr-tts mpv processes
    subprocess.run(["pkill", "-f", "hypr-tts-mpv-player"], stderr=subprocess.DEVNULL)

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

def log_debug(msg):
    try:
        with open("/tmp/hypr-tts.log", "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass

async def main():
    log_debug("--- TTS triggered ---")
    config = load_config()
    text = get_selected_text()
    
    log_debug(f"Selected text length: {len(text)}")
    if not text:
        log_debug("No text selected, exiting.")
        notify("Hypr-TTS", "No text selected or highlighted.", 2000)
        return

    # Clean text to remove common syntax characters (like asterisks, markdown, brackets)
    # so the TTS doesn't read them out loud ("asterisk", "left bracket", etc.)
    import re
    text = re.sub(r'[*_`~#\[\]<>{}]', '', text)
    log_debug(f"Cleaned text length: {len(text)}")

    kill_previous()
    notify("Hypr-TTS", "Speaking...", 1500)

    # Calculate rate string for edge-tts
    rate_mult = config.get("rate_multiplier", 1.0)
    rate_percent = int(round((rate_mult - 1.0) * 100))
    rate_str = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"
    log_debug(f"Rate string: {rate_str}")

    voice = config.get("voice", "en-GB-SoniaNeural")
    log_debug(f"Voice: {voice}")

    # Calculate volume for edge-tts and mpv
    vol_mult = float(config.get("volume", 1.0))
    vol_percent = max(-100, min(100, int(round((vol_mult - 1.0) * 100))))
    vol_str = f"+{vol_percent}%" if vol_percent >= 0 else f"{vol_percent}%"
    mpv_vol = str(int(max(10, min(1000, vol_mult * 100))))
    log_debug(f"Volume multiplier: {vol_mult}, Edge-TTS: {vol_str}, MPV Volume: {mpv_vol}%")

    try:
        import edge_tts
    except ImportError as e:
        log_debug(f"ImportError: {e}")
        print("Error: edge-tts is not installed. Please install it.")
        sys.exit(1)

    # Check if mpv is installed
    try:
        subprocess.run(["mpv", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("Error: mpv is not installed. Please install mpv to play the audio.")
        sys.exit(1)

    # Split text into safe-sized chunks to avoid edge-tts truncation
    chunks = split_into_chunks(text, max_chars=1500)

    # Open a single mpv process with clean stereo output
    log_debug("Starting mpv process...")
    mpv_process = subprocess.Popen(
        [
            "mpv",
            "--no-video",
            "--audio-channels=stereo",
            "--volume=100",
            "--title=hypr-tts-mpv-player",
            "--no-terminal",
            "-"
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=None
    )

    try:
        log_debug(f"Streaming {len(chunks)} chunks to mpv...")
        for i, chunk_text in enumerate(chunks):
            log_debug(f"Streaming chunk {i+1}...")
            communicate = edge_tts.Communicate(chunk_text, voice, rate=rate_str, volume=vol_str)
            await stream_chunk_to_mpv(communicate, mpv_process.stdin)
        log_debug("Finished streaming all chunks.")
    except Exception as e:
        log_debug(f"Error during TTS generation: {e}")
        print(f"Error during TTS generation: {e}")
    finally:
        mpv_process.stdin.close()
        mpv_process.wait()
        log_debug("mpv process exited.")

if __name__ == "__main__":
    asyncio.run(main())
