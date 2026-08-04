# Directive: Command Routing (Cognitive Layer SOP)

SOP for the assistant's cognitive layer: the Claude tool-calling loop in
`execution/llm_router.py` and the tool registry in `execution/tools.py`. This is
the layer between transcription and TTS — it turns a transcribed utterance into
spoken text and/or desktop actions. Read alongside
`directives/voice_assistant_flow.md` (master contract).

## Where it sits in the flow

```
transcribe → LLMRouter.run(text) → [tool-use loop] → yield spoken sentences → tts.speak_stream
```

The daemon constructs `router = LLMRouter(settings)` once and, per utterance,
pipes `router.run(text)` straight into `tts.speak_stream(...)`. `run` is a
generator: it yields complete sentences as they stream so Piper starts speaking
sentence 1 while later sentences are still synthesizing.

## The tool-calling loop (`llm_router.py`)

`LLMRouter.run(user_text) -> Iterator[str]` drives a manual streaming tool-use
loop over the Anthropic Messages API:

1. Seed `messages = [{"role": "user", "content": user_text}]`.
2. Open `client.messages.stream(model, max_tokens, system=SYSTEM_PROMPT,
   tools=get_tool_schemas(), messages=messages)`.
3. Consume `stream.text_stream`, buffering text and yielding on sentence
   boundaries (`_SENTENCE_END` = `.*?[.!?](?:\s+|$)`). Flush the remainder after
   the turn.
4. `msg = stream.get_final_message()`; append the assistant turn **verbatim**
   (`{"role":"assistant","content": msg.content}`) so `tool_use` blocks survive.
5. Branch on `msg.stop_reason`:
   - `tool_use` → for every `tool_use` block, call `call_tool(block.name,
     block.input)`, collect `{"type":"tool_result","tool_use_id":block.id,
     "content": <result str>}`, append them as a single
     `{"role":"user","content": results}` message, and loop again.
   - `refusal` → yield `_REFUSAL_REPLY` ("Sorry, I can't help with that.") and stop.
   - `end_turn` / anything else → stop.

`respond(user_text) -> str` is a non-streaming convenience that joins all yielded
sentences — used by the CLI and tests.

### Parameter contract (do not violate)

The `stream(...)` call passes ONLY: `model`, `max_tokens`, `system`, `tools`,
`messages`. Do **not** add `thinking`, `output_config`/`effort`, `temperature`,
`top_p`, or `top_k`. This keeps the router valid across Haiku 4.5 (rejects
`effort`) and Opus-class models (reject sampling params). Note: `config.toml`
defines `[llm] temperature` and `Settings.llm_temperature` exists, but the router
intentionally does **not** send it.

## SYSTEM_PROMPT intent

`SYSTEM_PROMPT` (top of `llm_router.py`) does two jobs:

- **Act, don't narrate.** Tells the model it is a Hyprland desktop assistant and
  must *use the tools* to perform desktop actions (open/launch/run), not just
  describe them.
- **Speak-friendly output.** Replies are read aloud by Piper, so it must output
  ONE short, natural spoken sentence — no markdown, code fences, bullets,
  asterisks, or backticks. (TTS also strips syntax chars as a second guard.)

Keep edits to the prompt consistent with both constraints; long or formatted
replies break the spoken UX.

## The tool registry (`tools.py`)

A dependency-free registry that derives Anthropic tool schemas from plain Python
functions via `inspect`.

- `@register_tool` — decorates a function: builds its schema and stores it in
  `_REGISTRY` (insertion-ordered). Returns the function unchanged, so it stays
  directly callable in tests.
- Schema build (`_build_schema`): `name` = `func.__name__`; `description` = the
  **docstring (required** — raises `ValueError` if missing); `input_schema` is an
  object whose `properties` come from parameters mapped via `_JSON_TYPE_MAP`
  (`str→string`, `int→integer`, `float→number`, `bool→boolean`, `list→array`,
  `dict→object`; unknown/unannotated → `string`). A parameter is `required` iff
  it has no default. `additionalProperties: False`. `*args`/`**kwargs` are
  rejected.
- `get_tool_schemas() -> list[dict]` — every registered schema, for the router.
- `call_tool(name, arguments) -> str` — dispatch by name with keyword args.
  Catches everything: unknown tool, `TypeError` (bad/missing args), or any
  exception inside the tool, returning `"Error: ..."` so one bad call never
  crashes the pipeline — the model sees the error and can recover.

### MVP tool

`launch_application(target: str) -> str` — calls `hypr.dispatch_exec(target)`
(`hyprctl dispatch exec -- <target>`) and returns `"Launched <target>."`.

## How to add a new tool

No router or registry changes are needed — just define a function and decorate it:

```python
from execution.tools import register_tool
from execution.hypr import dispatch  # or whatever the tool needs

@register_tool
def switch_workspace(number: int) -> str:
    """Switch to Hyprland workspace NUMBER. Use when the user asks to go to or
    switch workspaces/desktops."""
    dispatch(["workspace", str(number)])
    return f"Switched to workspace {number}."
```

Rules that make a tool work:

- **Docstring is mandatory** and is the model's only guidance — state plainly
  *what it does and WHEN to use it*.
- **Type-hint every parameter** so the JSON Schema type is right; give optional
  params defaults (they become non-required).
- **Return a short string** describing the outcome (spoken/relayed to the model).
- Define it where `register_tool` runs at import — i.e. in `tools.py`, or in a
  module that `tools.py`/the router imports, so it is registered before
  `get_tool_schemas()` is called.

## Testing `llm_router` with text input

Skip the mic/STT layers entirely and feed text directly. Run from the repo root
with the venv active (or via `.venv/bin/python`); needs `ANTHROPIC_API_KEY` in
`.env`.

- **Router end-to-end (real Claude call + tool execution):**
  ```bash
  python -m execution.llm_router "open firefox"
  ```
  Prints the full spoken reply (`respond()`); the default prompt is `"open
  firefox"` if no args. This actually dispatches tools, so `launch_application`
  will really launch the app via `hyprctl`.

- **Registry only (no API call):**
  ```bash
  python -m execution.tools
  ```
  Dumps all tool schemas as JSON, then exercises `call_tool` with a good call, an
  unknown tool, and bad arguments — useful for checking a newly added tool's
  generated schema and error handling. (No API call, but the good call really
  dispatches the MVP tool, i.e. launches `kitty` via `hyprctl`.)

- **Inspect config the router uses (key redacted):**
  ```bash
  python -m execution.config
  ```

To test streaming/sentence chunking specifically, iterate `router.run(text)` in a
REPL and observe the per-sentence yields:

```python
from execution.config import load_settings
from execution.llm_router import LLMRouter
for s in LLMRouter(load_settings()).run("what time is it"):
    print(repr(s))
```

## Self-annealing

If a tool call misbehaves at runtime, read the `Calling tool ...` log line and the
`Error: ...` result, fix the function or its docstring in `tools.py`, re-run
`python -m execution.tools` and `python -m execution.llm_router "<utterance>"`,
then update this directive with the learning.
