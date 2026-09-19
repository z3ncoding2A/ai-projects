"""Hyprland control helpers built on the `hyprctl` CLI.

Thin, GUI-free wrappers around `hyprctl` invoked via subprocess. Everything here is
side-effecting against the running Hyprland compositor, so failures surface as
`HyprError` for the caller (the daemon) to catch, log, and recover from without
crashing the pipeline.

No GUI / Qt dependencies in this module by design.
"""

from __future__ import annotations

import json
import logging
import subprocess

logger = logging.getLogger(__name__)


class HyprError(Exception):
    """Raised when a `hyprctl` invocation fails (nonzero exit or unparseable output)."""


def dispatch_exec(command: str) -> None:
    """Launch `command` via Hyprland's `exec` dispatcher.

    Uses the explicit `--` separator so the command string is passed through verbatim
    and never reinterpreted as hyprctl flags. Raises `HyprError` on nonzero exit.
    """
    # Note: `command` is a single argument after `--`; hyprctl forwards it to the
    # compositor's exec dispatcher, which runs it through the shell on its side.
    argv = ["hyprctl", "dispatch", "exec", "--", command]
    logger.debug("dispatch_exec: %r", command)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise HyprError("hyprctl not found on PATH") from exc
    if proc.returncode != 0:
        raise HyprError(
            f"hyprctl dispatch exec failed (exit {proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}"
        )


def dispatch(args: list[str]) -> str:
    """Run `hyprctl dispatch <args...>` and return its stdout.

    Raises `HyprError` on nonzero exit. `args` is the dispatcher name plus its
    parameters, e.g. `["workspace", "3"]`.
    """
    argv = ["hyprctl", "dispatch", *args]
    logger.debug("dispatch: %s", args)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise HyprError("hyprctl not found on PATH") from exc
    if proc.returncode != 0:
        raise HyprError(
            f"hyprctl dispatch {' '.join(args)} failed (exit {proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    return proc.stdout


def _query_json(args: list[str]) -> object:
    """Run `hyprctl <args...> -j` and parse the JSON stdout.

    Raises `HyprError` on nonzero exit or invalid JSON.
    """
    argv = ["hyprctl", *args, "-j"]
    logger.debug("query_json: %s", args)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise HyprError("hyprctl not found on PATH") from exc
    if proc.returncode != 0:
        raise HyprError(
            f"hyprctl {' '.join(args)} -j failed (exit {proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    out = proc.stdout.strip()
    if not out:
        # Hyprland sometimes prints nothing instead of an empty JSON object.
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise HyprError(f"could not parse hyprctl {' '.join(args)} output as JSON") from exc


def active_window() -> dict:
    """Return the focused window as a dict (`hyprctl activewindow -j`).

    Returns `{}` when no window is focused (Hyprland emits `null`/empty in that case).
    """
    data = _query_json(["activewindow"])
    if not isinstance(data, dict):
        return {}
    return data


def clients() -> list[dict]:
    """Return all open windows as a list of dicts (`hyprctl clients -j`)."""
    data = _query_json(["clients"])
    if not isinstance(data, list):
        return []
    return data


if __name__ == "__main__":
    # Minimal smoke test: print the active window title and client count.
    logging.basicConfig(level=logging.INFO)
    try:
        win = active_window()
        print("active window:", win.get("title") if win else "(none)")
        print("client count:", len(clients()))
    except HyprError as err:
        print(f"HyprError: {err}")
