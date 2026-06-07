# GEMINI Context: Hyprwhspr (DIY Voice-to-Text Dictation System)

This directory manages the custom configurations, service files, and scripts for **Hyprwhspr**—a highly optimized, DIY voice-to-text dictation system running on Linux (Hyprland).

---

## Project Overview & Concept

Hyprwhspr is a highly resourceful, custom-built dictation pipeline designed for hands-free and on-demand voice-to-text. It operates under several unique parameters:

- **DIY Hardware (Speaker-as-Mic):** Repurposes an ordinary earbud from an old AUX headset as a functional microphone. 
- **Pipewire Audio Optimization:** Uses custom equalizer settings in Pipewire to compensate for the earbud's hardware limitations, specifically boosting vocal clarity and filtering noise.
- **Hands-Free Triggering (Wake Word):** Continuously monitors the input stream for the wake word `[speak]`. Once triggered, subsequent audio is transcribed to text.
- **Service Management:** Managed as a systemd user service (`hyprwhspr.service`) to run reliably in the background of the user session.
- **Waybar Integration:** Integrated with Waybar status indicators via `/usr/lib/hyprwhspr/config/hyprland/hyprwhspr-tray.sh`.

---

## Directory Structure

While core system files may reside in system locations (e.g., `/usr/lib/hyprwhspr`), this project directory acts as the developer's workspace and repository hub for local configurations, helper scripts, and tests.

```
hyprwhspr/
├── config/
│   └── settings.json         # General settings (e.g., target model, generation configs)
├── src/
├── tests/                    # Testing scripts for validation
├── .env                      # Local environment variable configs (API Keys)
├── share/
│   └── pipewire              # symlink to ~/.config/pipewire
│   └── hyprwhspr             # symlink to ~/.local/share/hyprwhspr
├── GEMINI.md                 # This system instruction and context file
└── requirements.txt          # Python dependencies
```

---

## Tech Stack & Core Integrations

- **OS Backend:** Arch Linux (Hyprland WM).
- **Audio Routing:** Pipewire (for audio stream routing, capture, and equalization).
- **Service Management:** Systemd User Unit (`hyprwhspr.service`).
- **Status Panel:** Waybar (uses the custom tray module `custom/hyprwhspr` mapped to `hyprwhspr-module.jsonc`).

---

## Development & Customization Guidelines

Any AI assistant helping with this project must strictly adhere to the following:

### 1. Handling the Hardware Constraint
- Remember that the hardware is a **physical earbud speaker converted into a microphone**. 
- Any audio-processing code, scripts, or Pipewire configurations must be designed to handle very low sensitivity and high noise floors, requiring clean equalization, noise gates, or high gain adjustments without clipping.

### 2. Service-Level Changes
- The dictation listener runs in the background as a user service (`hyprwhspr.service`).
- When modifying service configurations or operational states, always run commands with the `--user` flag:
  ```bash
  systemctl --user daemon-reload
  systemctl --user restart hyprwhspr.service
  ```

### 3. File Separation & Modularity
- Keep configurations distinct from execution. Store API credentials safely in `.env` and load them using standard env-loaders (e.g., `dotenv` in Python).
- Store UI variables or model configurations in `config/settings.json`.
