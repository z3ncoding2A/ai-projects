"""Gemini Live API router — real-time bidirectional audio session.

Replaces the previous Anthropic Claude router with a single persistent WebSocket
session to ``gemini-3.1-flash-live-preview``.  Audio captured by the wake listener
is streamed directly to Gemini over WebSockets; Gemini's audio response is
streamed to an audio player in real time.  Tool calls (e.g. launch_application)
are handled synchronously inside the receive loop.

Architecture inside run_live_session():
  ┌─────────────────────────────────────────────────────────────────────┐
  │                       run_live_session()                            │
  │  sounddevice.InputStream → send_realtime_input(audio) → Gemini      │
  │  Gemini → receive() → write PCM chunks to aplay/pw-play subprocess  │
  │           └→ tool_call → call_tool() → send_tool_response()         │
  │           └→ interrupted → kill player subprocess                   │
  └─────────────────────────────────────────────────────────────────────┘

Threading: the caller (daemon pipeline thread) runs asyncio.run() for the
lifetime of a single wake → respond → done cycle.  sounddevice's audio
callback enqueues raw int16 bytes into an asyncio.Queue that the send loop
drains.  The receive loop and send loop are concurrent asyncio tasks.

Run standalone (GEMINI_API_KEY must be set):
    python -m execution.llm_router
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from typing import Callable

import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types

from execution.config import Settings, load_settings, configure_logging
from execution.tools import call_tool, get_gemini_tools

logger = logging.getLogger(__name__)

# ─────────────────────────── system prompt ───────────────────────────────────

SYSTEM_PROMPT = (
    "You are a voice-controlled assistant for a Hyprland Linux desktop. "
    "When the user asks you to do something on the desktop (open or launch an "
    "application, search the web, etc.), you MUST use the available tools to actually "
    "perform the action. Never pretend or hallucinate that you have done it without "
    "invoking the tool. "
    "Always use Google Chrome as the web browser instead of Firefox. "
    "Your replies are spoken aloud, so be concise — one or two short sentences. "
    "Never use markdown, code fences, bullet points, or formatting syntax. "
    "Output only plain words that sound right when read aloud."
)

# ─────────────────────────── audio constants ─────────────────────────────────

_MIC_SAMPLE_RATE = 16_000   # Hz  (Live API native)
_MIC_CHANNELS = 1
_MIC_DTYPE = "int16"
_MIC_MIME = "audio/pcm;rate=16000"

_OUT_SAMPLE_RATE = 24_000   # Hz  (fixed by Live API)
_OUT_CHANNELS = 1
_OUT_FORMAT_APLAY = ("aplay", "-q", "-r", "24000", "-f", "S16_LE", "-c", "1", "-t", "raw", "-")
_OUT_FORMAT_PWPLAY = ("pw-play", "--rate", "24000", "--channels", "1", "--format", "s16", "--raw", "-")


# ─────────────────────────── helpers ─────────────────────────────────────────

def _player_cmd(settings: Settings) -> tuple[str, ...]:
    """Build the player argv for raw 24 kHz 16-bit mono PCM."""
    player = settings.tts_player or "aplay"
    if player == "pw-play":
        return _OUT_FORMAT_PWPLAY
    return _OUT_FORMAT_APLAY


def _check_player(settings: Settings) -> bool:
    """Return True if the configured audio player binary exists on PATH."""
    player = settings.tts_player or "aplay"
    if shutil.which(player) is None:
        logger.error("Audio player '%s' not found on PATH; output will be silent.", player)
        return False
    return True


# ─────────────────────────── core session ────────────────────────────────────

async def run_live_session(
    settings: Settings,
    set_state: Callable[[str], None] = lambda s: None,
) -> None:
    """Open one Gemini Live WebSocket session and run until the turn ends.

    This is the sole entry-point for the daemon pipeline.  It:
      1. Connects to ``gemini-3.1-flash-live-preview`` with audio I/O.
      2. Starts two concurrent async tasks:
           - ``_send_mic``: streams microphone audio to Gemini.
           - ``_receive_play``: receives Gemini audio, plays it, handles tools.
      3. Returns when the model completes its turn (``turn_complete`` or
         connection close).

    Args:
        settings: resolved Settings from config.py.
        set_state: callable that updates the PyQt6 overlay state; safe to call
                   from this coroutine (it emits a Qt signal under the hood).
    """
    client = genai.Client(api_key=settings.gemini_api_key)

    live_config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(
            parts=[types.Part(text=SYSTEM_PROMPT)]
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=settings.llm_voice_name
                )
            )
        ),
        tools=get_gemini_tools(),
        thinking_config=types.ThinkingConfig(
            thinking_level=settings.llm_thinking_level
        ),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                silence_duration_ms=settings.llm_silence_duration_ms,
                prefix_padding_ms=200,
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    player_proc: list[subprocess.Popen | None] = [None]  # mutable cell
    done_event = asyncio.Event()

    # ── mic send loop ────────────────────────────────────────────────────────

    async def _send_mic(session: genai.live.AsyncLiveSession) -> None:
        """Open the microphone and stream PCM chunks to Gemini."""
        loop = asyncio.get_running_loop()

        def _audio_callback(indata: np.ndarray, frames: int, time_info, status) -> None:
            if status:
                logger.debug("sounddevice status: %s", status)
            # indata is int16 shaped (frames, 1); send as raw bytes.
            loop.call_soon_threadsafe(audio_queue.put_nowait, indata.tobytes())

        device = settings.input_device or None  # None → system default
        try:
            with sd.InputStream(
                samplerate=_MIC_SAMPLE_RATE,
                channels=_MIC_CHANNELS,
                dtype=_MIC_DTYPE,
                blocksize=1600,  # 100 ms chunks
                device=device,
                callback=_audio_callback,
            ):
                set_state("listening")
                logger.debug("Microphone stream open; streaming to Gemini")
                while not done_event.is_set():
                    try:
                        chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.2)
                    except asyncio.TimeoutError:
                        continue
                    if chunk is None:
                        break
                    await session.send_realtime_input(
                        audio=types.Blob(data=chunk, mime_type=_MIC_MIME)
                    )
        except Exception:
            logger.exception("Mic send loop failed")
        finally:
            done_event.set()
            logger.debug("Mic send loop exited")

    # ── receive / play loop ──────────────────────────────────────────────────

    async def _receive_play(session: genai.live.AsyncLiveSession) -> None:
        """Receive server events; play audio, handle tools, handle interrupts."""
        player_argv = _player_cmd(settings)
        _player_ok = _check_player(settings)

        inactivity_task: asyncio.Task | None = None

        def _reset_inactivity() -> None:
            nonlocal inactivity_task
            if inactivity_task and not inactivity_task.done():
                inactivity_task.cancel()
            inactivity_task = None

        async def _timeout_waiter() -> None:
            try:
                await asyncio.sleep(settings.llm_inactivity_timeout_s)
                logger.info("Inactivity timeout reached, ending session")
                done_event.set()
            except asyncio.CancelledError:
                pass

        def _open_player() -> subprocess.Popen | None:
            if not _player_ok:
                return None
            try:
                return subprocess.Popen(
                    player_argv,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                logger.exception("Failed to open audio player")
                return None

        def _kill_player() -> None:
            proc = player_proc[0]
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=1.0)
                except Exception:
                    pass
            player_proc[0] = None

        try:
            async for response in session.receive():
                _reset_inactivity()
                server_content = response.server_content

                # ── audio output ─────────────────────────────────────────────
                if server_content and server_content.model_turn:
                    first_audio = True
                    for part in server_content.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            if first_audio:
                                set_state("speaking")
                                if player_proc[0] is None:
                                    player_proc[0] = _open_player()
                                first_audio = False
                            # Write PCM to player stdin.
                            proc = player_proc[0]
                            if proc is not None and proc.stdin:
                                try:
                                    proc.stdin.write(part.inline_data.data)
                                except (BrokenPipeError, OSError):
                                    logger.debug("Player stdin closed; reopening")
                                    _kill_player()
                                    player_proc[0] = _open_player()
                                    proc = player_proc[0]
                                    if proc and proc.stdin:
                                        proc.stdin.write(part.inline_data.data)

                # ── transcription (log only) ─────────────────────────────────
                if server_content:
                    if server_content.input_transcription:
                        logger.info("User said: %s", server_content.input_transcription.text)
                    if server_content.output_transcription:
                        logger.info("Gemini said: %s", server_content.output_transcription.text)

                # ── interruption ─────────────────────────────────────────────
                if server_content and server_content.interrupted:
                    logger.info("Interrupted by user; killing audio player")
                    _kill_player()
                    set_state("listening")

                # ── turn complete ─────────────────────────────────────────────
                if server_content and server_content.turn_complete:
                    logger.debug("Turn complete")
                    # Flush player stdin and wait for it to finish.
                    proc = player_proc[0]
                    if proc is not None and proc.stdin:
                        try:
                            proc.stdin.close()
                        except OSError:
                            pass
                    if proc is not None:
                        try:
                            proc.wait(timeout=10.0)
                        except Exception:
                            pass
                    player_proc[0] = None
                    set_state("listening")
                    inactivity_task = asyncio.create_task(_timeout_waiter())

                # ── synchronous function / tool calls ─────────────────────────
                if response.tool_call:
                    function_responses = []
                    for fc in response.tool_call.function_calls:
                        logger.info("Tool call: %s(%s)", fc.name, dict(fc.args))
                        result = call_tool(fc.name, dict(fc.args))
                        logger.info("Tool result: %s", result)
                        function_responses.append(
                            types.FunctionResponse(
                                id=fc.id,
                                name=fc.name,
                                response={"result": result},
                            )
                        )
                    await session.send_tool_response(
                        function_responses=function_responses
                    )

        except Exception:
            logger.exception("Receive/play loop failed")
        finally:
            _kill_player()
            done_event.set()
            logger.debug("Receive/play loop exited")

    # ── connect and run ──────────────────────────────────────────────────────

    logger.info("Connecting to Gemini Live API (%s)", settings.llm_model)
    try:
        async with client.aio.live.connect(
            model=settings.llm_model,
            config=live_config,
        ) as session:
            set_state("listening")
            send_task = asyncio.create_task(_send_mic(session))
            recv_task = asyncio.create_task(_receive_play(session))
            wait_task = asyncio.create_task(done_event.wait())
            
            await asyncio.wait(
                [wait_task, recv_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            done_event.set()
            wait_task.cancel()
            recv_task.cancel()
            send_task.cancel()
            
            try:
                await send_task
            except asyncio.CancelledError:
                pass
    except Exception:
        logger.exception("Gemini Live session failed")
    finally:
        set_state("hidden")
        logger.info("Gemini Live session ended")


# ─────────────────────────── legacy shim ─────────────────────────────────────

class LLMRouter:
    """Thin shim retained for backwards compatibility with any test callers.

    The daemon no longer uses this class; it calls ``run_live_session`` directly.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def respond(self, user_text: str) -> str:
        """Blocking one-shot respond (non-streaming); used in standalone tests."""
        import asyncio as _asyncio
        _asyncio.run(run_live_session(self._settings))
        return ""


# ─────────────────────────── CLI smoke-test ──────────────────────────────────

if __name__ == "__main__":
    import sys

    _settings = load_settings()
    configure_logging(_settings)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    print("Starting a one-shot Gemini Live session.  Speak after the prompt.")
    print("Press Ctrl-C to stop.\n")

    try:
        asyncio.run(run_live_session(_settings))
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
