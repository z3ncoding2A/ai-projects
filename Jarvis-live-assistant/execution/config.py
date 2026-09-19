"""Configuration loading for the Hyprland voice assistant.

Loads ``config.toml`` (stdlib ``tomllib``) into a frozen ``Settings`` dataclass,
expands ``~`` in path fields, loads ``.env`` via python-dotenv, and reads the
Gemini API key from the environment. Modules receive a ``Settings`` instance
and MUST NOT read ``config.toml`` independently.

Run standalone for a quick dump:
    python -m execution.config
"""

from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# config.toml lives at the repo root, one directory up from this file (execution/).
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.toml"


@dataclass(frozen=True)
class Settings:
    """Flattened, immutable view of config.toml + the Anthropic key from env.

    Field names mirror the contract: each config.toml table is flattened with
    its table name as a prefix (e.g. [wake] model -> wake_model).
    """

    # [wake]
    wake_model: str
    wake_threshold: float
    wake_vad_threshold: float
    wake_inference_framework: str  # "onnx" | "tflite"

    # [audio]
    sample_rate: int  # 16000
    frame_size: int  # 1280
    input_device: str  # "" => system default input device

    # [recorder]
    silence_ms: int
    min_speech_ms: int
    max_record_ms: int
    recorder_vad_aggressiveness: int  # webrtcvad 0..3
    start_grace_ms: int

    # [whisper]
    whisper_model: str
    whisper_device: str  # "cuda" | "cpu"
    whisper_compute_type: str
    whisper_beam_size: int
    whisper_language: str

    # [llm]
    llm_provider: str          # "gemini"
    llm_model: str             # e.g. "gemini-3.1-flash-live-preview"
    llm_voice_name: str        # Prebuilt TTS voice name (e.g. "Kore")
    llm_silence_duration_ms: int  # Server VAD silence threshold in milliseconds
    llm_thinking_level: str    # "minimal" | "low" | "medium" | "high"
    llm_inactivity_timeout_s: int # Seconds of silence before Jarvis goes back to sleep
    gemini_api_key: str        # from GEMINI_API_KEY env, NOT config.toml

    # [tts]
    tts_engine: str  # "piper"
    tts_model_path: str  # ~ expanded
    tts_config_path: str  # ~ expanded
    tts_sample_rate: int  # 22050
    tts_player: str  # "aplay" | "pw-play"

    # [ui]
    ui_enabled: bool
    ui_window_class: str
    ui_width: int
    ui_height: int

    # [logging]
    log_level: str


def _expand(path: str) -> str:
    """Expand a leading ``~`` (and any ``$VARS``) in a path string.

    Empty strings (e.g. an unset input device) pass through untouched.
    """
    if not path:
        return path
    return os.path.expanduser(os.path.expandvars(path))


def load_settings(path: str | None = None) -> Settings:
    """Read config.toml and the environment into a frozen ``Settings``.

    Args:
        path: optional path to config.toml; defaults to ``ROOT/config.toml``
            (the repo root, relative to this file).

    Returns:
        A populated, immutable ``Settings`` instance.
    """
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH

    # tomllib requires a binary file handle.
    with open(config_path, "rb") as fh:
        data = tomllib.load(fh)

    # Load .env from the repo root so GEMINI_API_KEY is available in os.environ.
    # override=False keeps any key already set in the real environment authoritative.
    load_dotenv(ROOT / ".env", override=False)
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_api_key:
        logger.warning(
            "GEMINI_API_KEY is not set; the LLM router will fail to authenticate."
        )

    wake = data.get("wake", {})
    audio = data.get("audio", {})
    recorder = data.get("recorder", {})
    whisper = data.get("whisper", {})
    llm = data.get("llm", {})
    tts = data.get("tts", {})
    ui = data.get("ui", {})
    log = data.get("logging", {})

    return Settings(
        # [wake]
        wake_model=wake["model"],
        wake_threshold=float(wake["threshold"]),
        wake_vad_threshold=float(wake["vad_threshold"]),
        wake_inference_framework=wake["inference_framework"],
        # [audio]
        sample_rate=int(audio["sample_rate"]),
        frame_size=int(audio["frame_size"]),
        input_device=audio.get("input_device", ""),
        # [recorder]
        silence_ms=int(recorder["silence_ms"]),
        min_speech_ms=int(recorder["min_speech_ms"]),
        max_record_ms=int(recorder["max_record_ms"]),
        recorder_vad_aggressiveness=int(recorder["vad_aggressiveness"]),
        start_grace_ms=int(recorder["start_grace_ms"]),
        # [whisper]
        whisper_model=whisper["model"],
        whisper_device=whisper["device"],
        whisper_compute_type=whisper["compute_type"],
        whisper_beam_size=int(whisper["beam_size"]),
        whisper_language=whisper["language"],
        # [llm]
        llm_provider=llm["provider"],
        llm_model=llm["model"],
        llm_voice_name=llm.get("voice_name", "Kore"),
        llm_silence_duration_ms=int(llm.get("silence_duration_ms", 800)),
        llm_thinking_level=llm.get("thinking_level", "minimal"),
        llm_inactivity_timeout_s=int(llm.get("inactivity_timeout_s", 15)),
        gemini_api_key=gemini_api_key,
        # [tts]
        tts_engine=tts["engine"],
        tts_model_path=_expand(tts["model_path"]),
        tts_config_path=_expand(tts["config_path"]),
        tts_sample_rate=int(tts["sample_rate"]),
        tts_player=tts["player"],
        # [ui]
        ui_enabled=bool(ui["enabled"]),
        ui_window_class=ui["window_class"],
        ui_width=int(ui["width"]),
        ui_height=int(ui["height"]),
        # [logging]
        log_level=log["level"],
    )


def configure_logging(settings: Settings) -> None:
    """Configure the root logger's level and format from ``settings``.

    Safe to call once at daemon startup. Falls back to INFO if the configured
    level string is not a recognized logging level.
    """
    level = logging.getLevelName(settings.log_level.upper())
    if not isinstance(level, int):
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # If basicConfig already ran elsewhere, force our level onto the root logger.
    logging.getLogger().setLevel(level)


if __name__ == "__main__":
    # Minimal CLI: load settings and dump them (key redacted).
    s = load_settings()
    configure_logging(s)
    from dataclasses import asdict

    dumped = asdict(s)
    if dumped.get("gemini_api_key"):
        dumped["gemini_api_key"] = "<set>"
    for k, v in dumped.items():
        print(f"{k} = {v!r}")
