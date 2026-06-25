"""Text-to-speech via Piper, streamed and sentence-chunked into an audio player.

Pipeline per sentence:  piper --output_raw  ->  <player> (raw S16_LE PCM)

`--output_raw` makes Piper emit PCM on stdout *as it synthesizes*, so the player
begins playing before synthesis of that sentence finishes (intra-sentence overlap
is free). Across sentences we serialize: we wait for sentence N's player to exit
before starting N+1, otherwise two concurrent players garble the audio. The
early-start win in `speak_stream` comes from the LLM yielding sentence 1 while it
is still producing later ones -- not from concurrent playback.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
from typing import Iterable

# Absolute cross-module import form is mandatory (daemon wires by name).
from execution.config import Settings, load_settings

logger = logging.getLogger(__name__)

# Characters/sequences that are visual markdown/syntax noise and should not be
# spoken aloud. We strip the markers but keep the words they decorate.
_MARKDOWN_TOKENS = re.compile(r"[*_`~#>|]+")
# Fenced code blocks and inline backtick spans: drop the fence markers only.
_CODE_FENCE = re.compile(r"```[\w-]*")
# Markdown links [text](url) -> keep the visible text.
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
# Collapse runs of whitespace left behind after stripping.
_WS = re.compile(r"\s+")


def _strip_markdown(text: str) -> str:
    """Remove markdown/syntax characters so only speakable words remain."""
    text = _CODE_FENCE.sub(" ", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _MARKDOWN_TOKENS.sub("", text)
    text = _WS.sub(" ", text)
    return text.strip()


def _resolve_sample_rate(settings: Settings) -> int:
    """Return the voice's true sample rate.

    The authoritative value lives in the Piper voice `.json` under
    `audio.sample_rate`; read it rather than trusting the config default, which
    may not match the actual model. Fall back to `settings.tts_sample_rate` if
    the file is missing or unparseable.
    """
    cfg_path = settings.tts_config_path
    try:
        with open(cfg_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        sr = int(data["audio"]["sample_rate"])
        if sr != settings.tts_sample_rate:
            logger.debug(
                "Voice sample rate %d (from %s) overrides config %d",
                sr, cfg_path, settings.tts_sample_rate,
            )
        return sr
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.debug(
            "Could not read sample_rate from %s (%s); using config %d",
            cfg_path, exc, settings.tts_sample_rate,
        )
        return settings.tts_sample_rate


def _player_argv(player: str, sample_rate: int) -> list[str]:
    """Build the argv for the chosen player to consume raw 16-bit mono PCM.

    aplay and pw-play take entirely different flags, so dispatch on the name
    rather than assuming aplay syntax for both (pw-play would fail silently).
    """
    if player == "pw-play":
        return [
            "pw-play",
            "--rate", str(sample_rate),
            "--channels", "1",
            "--format", "s16",
            "--raw",
            "-",
        ]
    # Default / "aplay".
    return [
        "aplay",
        "-q",
        "-r", str(sample_rate),
        "-f", "S16_LE",
        "-c", "1",
        "-t", "raw",
        "-",
    ]


def _preflight(settings: Settings) -> tuple[str, str] | None:
    """Validate the piper binary, the player, and the model file exist.

    Returns (piper_path, player_path) on success, or None after logging a clear
    error -- callers degrade gracefully (speak nothing) rather than raise.
    """
    # NOTE: the rhasspy `piper` binary lives on PATH; `pip install piper-tts`
    # would instead expose it as `python -m piper`. Prefer the PATH binary.
    piper_path = shutil.which("piper")
    if not piper_path:
        logger.error("TTS unavailable: 'piper' binary not found on PATH.")
        return None

    player = settings.tts_player or "aplay"
    player_path = shutil.which(player)
    if not player_path:
        logger.error("TTS unavailable: player '%s' not found on PATH.", player)
        return None

    import os
    if not settings.tts_model_path or not os.path.isfile(settings.tts_model_path):
        logger.error(
            "TTS unavailable: piper model not found at '%s'.",
            settings.tts_model_path,
        )
        return None

    # piper is invoked with `-c <config>`; a missing/unreadable config makes the
    # binary abort (exit 134) and, since we discard stderr and never inspect the
    # exit code, the result is total silence with no log line. Validate it here.
    if not settings.tts_config_path or not os.path.isfile(settings.tts_config_path):
        logger.error(
            "TTS unavailable: piper voice config not found at '%s'.",
            settings.tts_config_path,
        )
        return None

    return piper_path, player_path


def _speak_one(sentence: str, settings: Settings, piper_path: str,
               player_path: str, sample_rate: int) -> None:
    """Synthesize and play a single (already-cleaned, non-empty) sentence.

    Builds  piper --output_raw  |  <player>  and blocks until playback ends.
    """
    # piper flags use UNDERSCORES on the installed binary (--output_raw,
    # --output_file) despite the contract's illustrative hyphen form; verified
    # against `piper --help`. Do not "fix" to hyphens -- it breaks at runtime.
    piper_cmd = [
        piper_path,
        "-m", settings.tts_model_path,
        "-c", settings.tts_config_path,
        "--output_raw",
        "-q",
    ]
    player_cmd = _player_argv(settings.tts_player or "aplay", sample_rate)

    piper_proc: subprocess.Popen | None = None
    player_proc: subprocess.Popen | None = None
    try:
        piper_proc = subprocess.Popen(
            piper_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        player_proc = subprocess.Popen(
            player_cmd,
            stdin=piper_proc.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Close our copy of piper's stdout so only the player holds the read
        # end; otherwise the player never sees EOF and we deadlock on wait().
        assert piper_proc.stdout is not None
        piper_proc.stdout.close()

        # Feed the sentence text to piper on stdin, then close to signal EOF.
        assert piper_proc.stdin is not None
        piper_proc.stdin.write(sentence.encode("utf-8"))
        piper_proc.stdin.close()

        # Serialize: wait for the player to fully drain before returning so the
        # next sentence does not start a second concurrent player.
        player_proc.wait()
        piper_proc.wait()
        # Surface post-preflight piper failures (bad model, missing espeak data,
        # etc.) which otherwise leave the player with an immediate EOF and
        # produce silence with no diagnostic.
        if piper_proc.returncode not in (0, None):
            logger.error(
                "piper exited %d for sentence; audio may be silent",
                piper_proc.returncode,
            )
    except OSError as exc:
        logger.error("TTS playback failed for one sentence: %s", exc)
    finally:
        # Best-effort cleanup if something raised mid-pipe.
        for proc in (player_proc, piper_proc):
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except OSError:
                    pass


def speak_stream(sentences: Iterable[str], settings: Settings) -> None:
    """Speak an iterable of sentences as they arrive, one pipe per sentence.

    Each sentence is markdown-stripped and skipped if empty. Playback of one
    sentence's audio overlaps synthesis of the *next* sentence only insofar as
    the producer (LLM) yields ahead; the players themselves run serially.
    Degrades gracefully (logs, speaks nothing) if piper/player/model is missing.
    """
    ready = _preflight(settings)
    if ready is None:
        return
    piper_path, player_path = ready
    sample_rate = _resolve_sample_rate(settings)

    for raw in sentences:
        cleaned = _strip_markdown(raw)
        if not cleaned:
            # Nothing speakable (e.g. a bare code fence) -- don't spawn piper.
            continue
        _speak_one(cleaned, settings, piper_path, player_path, sample_rate)


def speak(text: str, settings: Settings) -> None:
    """Synthesize and play the whole text, blocking until done.

    Delegates to `speak_stream` with a single-item iterable to stay DRY.
    """
    speak_stream([text], settings)


if __name__ == "__main__":
    # CLI: python -m execution.tts "<text>"
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if len(sys.argv) < 2:
        print("usage: python -m execution.tts \"<text to speak>\"",
              file=sys.stderr)
        sys.exit(2)
    _settings = load_settings()
    speak(" ".join(sys.argv[1:]), _settings)
