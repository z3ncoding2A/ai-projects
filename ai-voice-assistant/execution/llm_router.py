"""Cloud Anthropic Claude router with tool-calling + streaming.

Implements the manual streaming tool-use loop for the voice assistant: each
turn streams assistant text (yielded sentence-by-sentence so TTS can start
early) and, when the model wants to act, executes the requested tools via the
tools registry and feeds the results back for another turn.

Wired by the daemon as ``LLMRouter(settings)`` -> ``router.run(text)``.
"""

from __future__ import annotations

import logging
import re
from typing import Iterator

import anthropic

from execution.config import Settings
from execution.tools import call_tool, get_tool_schemas

logger = logging.getLogger(__name__)

# Concise: replies are spoken aloud, so they must be short and plain-text.
SYSTEM_PROMPT = (
    "You are a voice-controlled assistant for a Hyprland Linux desktop. "
    "When the user asks you to do something on the desktop (open or launch an "
    "application, run a command, etc.), use the available tools to actually "
    "perform the action rather than just describing it. "
    "Your replies are spoken aloud by a text-to-speech engine, so reply with "
    "ONE short, natural spoken sentence. Never use markdown, code fences, "
    "bullet points, asterisks, backticks, or any formatting syntax — output "
    "only plain words that sound right when read aloud."
)

# Yield a chunk once it ends in sentence-final punctuation followed by space/end.
# Spoken replies are short, so this lightweight split is sufficient; we do not
# try to handle decimals or abbreviations.
_SENTENCE_END = re.compile(r".*?[.!?](?:\s+|$)", re.DOTALL)

# Spoken when the model refuses for safety reasons.
_REFUSAL_REPLY = "Sorry, I can't help with that."


def _split_sentences(buffer: str) -> tuple[list[str], str]:
    """Pull complete sentences out of ``buffer``.

    Returns the list of complete sentences (stripped) and the unconsumed
    remainder still being built.
    """
    sentences: list[str] = []
    pos = 0
    for match in _SENTENCE_END.finditer(buffer):
        sentence = match.group().strip()
        if sentence:
            sentences.append(sentence)
        pos = match.end()
    return sentences, buffer[pos:]


class LLMRouter:
    """Drives the Anthropic tool-use loop for a single user utterance."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # API key comes from settings (loaded from ANTHROPIC_API_KEY in .env).
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def run(self, user_text: str) -> Iterator[str]:
        """Run the tool-use loop, yielding assistant text by sentence.

        Each turn streams the assistant's text; complete sentences are yielded
        as soon as they form so TTS can begin while later sentences synthesize.
        On a ``tool_use`` turn the requested tools are executed and their
        results fed back for another turn. Yields nothing if the model only
        acted silently (no text) — the daemon may then speak a default
        confirmation.
        """
        settings = self._settings
        schemas = get_tool_schemas()
        messages: list[dict] = [{"role": "user", "content": user_text}]

        while True:
            buffer = ""
            # NOTE: do not pass thinking / output_config(effort) / temperature /
            # top_p / top_k — the contract forbids them, and omitting them keeps
            # the router valid across Haiku 4.5 and Opus-class models alike.
            with self._client.messages.stream(
                model=settings.llm_model,
                max_tokens=settings.llm_max_tokens,
                system=SYSTEM_PROMPT,
                tools=schemas,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    buffer += text
                    sentences, buffer = _split_sentences(buffer)
                    for sentence in sentences:
                        yield sentence
                msg = stream.get_final_message()

            # Flush any trailing text from this turn. A sentence never spans a
            # tool_use boundary, so a per-turn flush is safe.
            remainder = buffer.strip()
            if remainder:
                yield remainder

            # Append the assistant turn verbatim (preserves tool_use blocks).
            messages.append({"role": "assistant", "content": msg.content})

            if msg.stop_reason == "tool_use":
                # Execute every requested tool and return all results in a
                # single user message, as the API requires.
                results = []
                for block in msg.content:
                    if block.type == "tool_use":
                        logger.info("Calling tool %s with %s", block.name, block.input)
                        # block.input is already a parsed dict from the SDK.
                        results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": call_tool(block.name, block.input),
                            }
                        )
                messages.append({"role": "user", "content": results})
                continue

            if msg.stop_reason == "refusal":
                logger.warning("Model refused the request")
                yield _REFUSAL_REPLY

            # end_turn, refusal, or anything else: the turn is complete.
            break

    def respond(self, user_text: str) -> str:
        """Non-streaming convenience: the full final spoken text as one string."""
        return " ".join(self.run(user_text)).strip()


if __name__ == "__main__":
    import sys

    from execution.config import configure_logging, load_settings

    _settings = load_settings()
    configure_logging(_settings)

    prompt = " ".join(sys.argv[1:]).strip() or "open firefox"
    router = LLMRouter(_settings)
    print(router.respond(prompt))
