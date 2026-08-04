# Directive: Hyprland Control + Operations SOP

Desktop control, window rules, systemd install, and Piper voice install for the
sovereign Hyprland voice assistant. Matches the actual implementation in
`execution/hypr.py`, `execution/tools.py`, `execution/tts.py`,
`execution/ui_overlay.py`, `execution/daemon.py`, `config.toml`, and
`voice-assistant.service`. Keep this in sync when those change.

## 1. Hyprland control (`hyprctl` wrappers)

All desktop side effects go through `execution/hypr.py`, thin GUI-free
subprocess wrappers around the `hyprctl` CLI. They raise `HyprError` on nonzero
exit (or unparseable JSON); the daemon catches it, logs, and re-arms.

- `dispatch_exec(command: str) -> None`
  Runs `hyprctl dispatch exec -- <command>`. The `--` separator passes the
  command verbatim so it is never reparsed as hyprctl flags; the compositor runs
  it through its own shell. This is the launch path used by the `launch_application`
  tool (`tools.py`).
- `dispatch(args: list[str]) -> str`
  Runs `hyprctl dispatch <args...>` and returns stdout. `args` is the dispatcher
  name plus parameters, e.g. `dispatch(["workspace", "3"])`,
  `dispatch(["killactive"])`, `dispatch(["fullscreen", "1"])`.
- `active_window() -> dict`
  Parses `hyprctl activewindow -j`. Returns `{}` when nothing is focused.
- `clients() -> list[dict]`
  Parses `hyprctl clients -j`. Returns `[]` on non-list output.

Requirement: `hyprctl` must be on the daemon's `PATH` (it is part of Hyprland).
A missing binary surfaces as `HyprError("hyprctl not found on PATH")`.

Smoke test the wrappers standalone (inside a running Hyprland session):

```
.venv/bin/python -m execution.hypr      # prints active window title + client count
```

Adding more desktop actions = add a `@register_tool` function in `tools.py` that
calls `dispatch`/`dispatch_exec`; no other change (schemas are auto-derived).

## 2. Hyprland window rules (add to `hyprland.conf`)

The PyQt6 overlay is matched by its Wayland `app_id` (XWayland `WM_CLASS`), which
Qt derives from the application/desktop-file name. The daemon sets it via
`QApplication.setApplicationName(...)` and `QApplication.setDesktopFileName(...)`
to `settings.ui_window_class` (default `voice_assistant`, from `config.toml`
`[ui] window_class`). The window title/object name do NOT drive the match.

If you change `[ui] window_class`, update the `class:` regex below to match.

Add this `windowrule` block to your Hyprland config (Hyprland v0.53+ block syntax).
With HyDE, put it in `~/.config/hypr/windowrules.conf`:

```
windowrule {
    name = voice_assistant_config
    match:class = ^(voice_assistant)$
    float = true
    pin = true
    decorate = false
    move = (100%-520) 40
    size = 500 300
}
```

Notes:
- `size 500 300` should match `[ui] width`/`height` in `config.toml`; the overlay
  also self-sizes via `resize(width, height)`, but the rule pins the compositor
  geometry. `move (100%-520) 40` parks it near the top-right (width 500 + ~20 px
  margin); adjust to taste.
- `float = true` is required — without it the overlay tiles. `pin = true` keeps it on all
  workspaces. `decorate = false` removes borders and keeps it visually clean (it is a
  translucent painted indicator).
- Reload after editing: `hyprctl reload`.

## 3. systemd user unit install

The unit lives in the repo at `voice-assistant.service`. It is a **user** unit
(not system) so it inherits your Wayland/PipeWire session. It runs the daemon as
`%h/ai-projects/ai-voice-assistant/.venv/bin/python -m execution.daemon` with
`WorkingDirectory=%h/ai-projects/ai-voice-assistant` (the `-m` form requires the
repo root as CWD), `Restart=on-failure`, and is bound to `graphical-session.target`.

Install and enable:

```
mkdir -p ~/.config/systemd/user
cp ~/ai-projects/ai-voice-assistant/voice-assistant.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now voice-assistant
```

Operate:

```
systemctl --user status voice-assistant
systemctl --user restart voice-assistant
journalctl --user -u voice-assistant -f      # follow logs
```

### WAYLAND_DISPLAY / XDG_RUNTIME_DIR note (critical)

The daemon talks to the compositor (`hyprctl` and the PyQt6 overlay) and decides
headless vs. GUI by checking `WAYLAND_DISPLAY` / `DISPLAY` in its environment
(`daemon.py` line 51). systemd user services do NOT automatically see your
session's Wayland variables, so the unit can come up **headless** (no overlay)
and `hyprctl` may fail.

Preferred fix — have Hyprland import the variables into the user manager at
startup. Add to `hyprland.conf`:

```
exec-once = systemctl --user import-environment WAYLAND_DISPLAY XDG_RUNTIME_DIR HYPRLAND_INSTANCE_SIGNATURE
exec-once = systemctl --user start voice-assistant.service
```

(The unit's header comment documents this same expectation.) After this the unit
inherits `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, and the Hyprland instance signature
that `hyprctl` needs.

Fallback — if the daemon still cannot reach the compositor, set the values
explicitly in the unit (the commented lines are already present in
`voice-assistant.service`; uncomment and adjust). `XDG_RUNTIME_DIR` is normally
`/run/user/$(id -u)` and `WAYLAND_DISPLAY` is typically `wayland-1`:

```
Environment=WAYLAND_DISPLAY=wayland-1
Environment=XDG_RUNTIME_DIR=/run/user/1000
```

Verify the active values from a terminal inside the session with
`echo $WAYLAND_DISPLAY $XDG_RUNTIME_DIR`. Re-run `systemctl --user daemon-reload`
after editing the unit.

## 4. Piper voice install

`config.toml` `[tts]` points at the voice model and its sidecar config:

```
model_path  = "~/.local/share/piper/en_US-lessac-high.onnx"
config_path  = "~/.local/share/piper/en_US-lessac-high.onnx.json"
sample_rate  = 22050        # advisory only; tts.py reads the true rate from the .json
player       = "aplay"      # "aplay" | "pw-play"
```

`tts.py` invokes the **`piper` binary on PATH** (the rhasspy build), not
`python -m piper`. It runs `piper -m <model> -c <config> --output_raw -q` and pipes
raw S16_LE mono PCM into the player. Flags use **underscores** (`--output_raw`),
verified against `piper --help` — do not "fix" to hyphens. The true sample rate is
read from the voice `.json` `audio.sample_rate`; `[tts] sample_rate` is only a
fallback if that file is missing.

Install the binary, a player, and the voice:

```
# 1. piper binary on PATH (rhasspy release). Either a distro/AUR package
#    providing `piper`, or download a release and put `piper` on PATH:
#    https://github.com/rhasspy/piper/releases
which piper                       # must resolve

# 2. an audio player on PATH
which aplay                       # ALSA (alsa-utils); or set player="pw-play"
which pw-play                     # PipeWire (pipewire-audio / pipewire-pulse)

# 3. the voice model + its .json sidecar (BOTH files required)
mkdir -p ~/.local/share/piper
cd ~/.local/share/piper
VOICE=en_US-lessac-high
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high
curl -L -o "$VOICE.onnx"       "$BASE/$VOICE.onnx"
curl -L -o "$VOICE.onnx.json"  "$BASE/$VOICE.onnx.json"
```

`tts.py` preflights all three (piper binary, player, model file, config file) and
degrades gracefully — logs an error and speaks nothing rather than crashing — if
any is missing. A missing `.json` config makes piper abort with silence, so it is
validated explicitly. To use a different voice, download both files and update
`[tts] model_path`/`config_path` (`~` is expanded by `config.load_settings`).

Verify TTS end to end (from the repo root):

```
.venv/bin/python -m execution.tts "Hyprland voice assistant online."
```

## Self-annealing

If desktop control or audio breaks at runtime, read the trace, fix the relevant
`execution/` module, re-test that layer with the standalone commands above, then
update this directive with the learning (a `hyprctl` quirk, a window-rule that was
needed, an env var the unit was missing). Do not discard directives.
