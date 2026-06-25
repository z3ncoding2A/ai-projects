---
name: hyprwhspr-audio-diagnostic
description: Diagnose and fix wake-word detection or audio routing issues in the Hyprwhspr system. Use when the wake word "speak" (or [speak]) fails to trigger dictation or when audio source changes are suspected.
---

# Hyprwhspr Audio Diagnostic

Procedure for troubleshooting wake-word detection failures, especially after configuration changes (e.g., Pipewire EQ adjustments).

## Diagnostic Procedure

1. **Check Service Status**
   Ensure the systemd user service is running and active:
   ```bash
   systemctl --user status hyprwhspr.service
   ```

2. **Inspect Application Logs**
   Check for the audio device being targeted and any initialization errors:
   ```bash
   journalctl --user -u hyprwhspr.service -n 50 --no-pager
   ```
   Look for lines like `Searching for device by name: <device_name>`.

3. **Verify Audio Input Node**
   Find the active Pipewire audio nodes to identify the correct source (especially if a virtual source is used for equalization):
   ```bash
   pw-cli list-objects Node | grep 'node.name'
   ```
   Or use `pactl`:
   ```bash
   pactl list sources | grep 'Name:'
   ```

4. **Validate Audio Levels**
   If the service is targeting the correct device but not triggering, check the signal level.
   Record a 5-second sample (request user to say the wake word):
   ```bash
   pw-record --target '<node_name>' --sample-count 240000 --container wav test.wav
   ```
   Analyze volume levels:
   ```bash
   ffmpeg -i test.wav -af volumedetect -f null /dev/null
   ```
   *Note: DIY earbud mic typically shows mean volume around -30dB and max around -8dB.*

5. **Verify Microphone Gain**
   Check current gain levels:
   ```bash
   pactl list sources
   ```
   Ensure volume is sufficient (often >100% for DIY hardware).

## Common Fixes

- **Audio Device Mismatch**: If `hyprwhspr` is targeting `"default"` but a virtual source (e.g., `"whisper dictation mic"`) exists, update the config.
- **Config Update**: Edit `~/.config/hyprwhspr/config.json` and set `"audio_device_name"` to the correct node name.
- **Service Restart**: Always restart after config changes:
  ```bash
  systemctl --user restart hyprwhspr.service
  ```

## Pitfalls
- **Logging Delay**: `journalctl` might not show logs immediately after a restart. If logs appear stale, wait a few seconds and check again.
- **Foreground Debugging**: If service logs are missing, stop the service and run the launcher directly to see output in real-time:
  ```bash
  systemctl --user stop hyprwhspr.service
  /usr/lib/hyprwhspr/bin/hyprwhspr
  ```
