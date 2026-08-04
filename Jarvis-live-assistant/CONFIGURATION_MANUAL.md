# J.A.R.V.I.S. (MARK XLVI) - Configuration & Customization Manual

Welcome to the **J.A.R.V.I.S. (Mark XLVI)** Configuration and Deployment Manual. This guide details how to configure, customize, run, and maintain your highly persistent, remote-accessible personal AI assistant inside the `Jarvis-live-assistant` workspace.

---

## 📁 Directory Structure

The merged project contains the following structural layout:
* **`main.py`**: The main entrypoint. Manages client-side Gemini Live API connections, schedules dashboard background tasks, coordinates input/output streams, and manages UI states.
* **`ui.py`**: A futuristic PyQt6 application depicting Stark-themed interactive HUD animations, real-time system metric trackers, file drop-zones, and graphical terminal widgets.
* **`actions/`**: Module tools written to automate computer features (e.g. `browser_control.py` for Chrome automation, `game_updater.py` for Steam, `file_processor.py` for analyzing files up to 500 MB).
* **`core/`**: Deep plumbing, consisting of the system prompt (`prompt.txt`), Speech-to-Text (`stt.py`), Text-to-Speech (`tts.py`), and a local LLM gateway (`llm_client.py`).
* **`config/`**: Holds API keys, active OS profile settings, and local SSL certificates (`certs/jarvis.crt`, `certs/jarvis.key`).
* **`dashboard/`**: Contains the FastAPI server, static HTML templates, and the WebSocket interfaces that enable wireless remote pairing, file uploads, and phone mic streaming.
* **`memory/`**: Long-term memory logic maintaining facts, preferences, and workspace stats in JSON format (`long_term.json`).

---

## 🗝️ Core Configuration (API Keys & OS Profile)

All key settings are parsed either from environment variables or from the workspace's JSON configuration file.

### Option A: Using `config/api_keys.json` (Recommended)
Create/edit the file located at `config/api_keys.json`:
```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE",
  "os_system": "linux"
}
```
* **`gemini_api_key`**: Your free Google Gemini API Key.
* **`os_system`**: Can be set to `"linux"`, `"windows"`, or `"mac"`. It governs target paths for applications, scripts, and OS-specific terminal instructions.

### Option B: Using Environment Variables (`.env`)
You can store your keys in a `.env` file at the root of `Jarvis-live-assistant/`:
```env
GEMINI_API_KEY=AIzaSy...
```
`main.py` is fully optimized to look for the `GEMINI_API_KEY` system environment variable first, with a fallback to `api_keys.json`.

---

## 🧠 Customizing System Behavior (System Prompt)

The core personality, limits, and rules are specified in **`core/prompt.txt`**. 
You can edit this file to suit your exact preferences. The rules enforced in this file dictate:
1. **Response Style**: Enforces short, direct, 2-3 sentence replies (no unnecessary wordiness).
2. **Iron Man Roleplay**: Responds to Stark-themed inputs like *"Daddy's home"* with *"Welcome home, sir."*
3. **Tool Routing Guidelines**: Instructs J.A.R.V.I.S. on when to trigger web browser tools, complex multi-step planning tasks, or file processing.

---

## 🔒 Securing & Running the Remote Access Dashboard

The FastAPI local dashboard allows you to send commands, upload files up to 500 MB, and stream your phone's microphone directly into the computer's Gemini Live session.

### SSL Certificates (Enabling HTTPS)
By default, the server runs on standard insecure HTTP on port `8000`. To access the dashboard and stream your microphone from modern browsers (Chrome/Safari), the browser requires a secure context (HTTPS).
1. Place your self-signed or CA-signed certificates inside the `config/certs/` directory as:
   * `config/certs/jarvis.crt`
   * `config/certs/jarvis.key`
2. Once both files are present, the FastAPI server will automatically boot in secure HTTPS mode. It also fires up an HTTPS alias server on **Port 8001** to allow easy manual browser entry, bypassing mixed-content limitations.

### Bypassing Mobile Browser SSL Warnings (Microphone Access)
If you use self-signed certificates, mobile browsers will block microphone access due to untrusted HTTPS. You can easily bypass this on your mobile device (e.g., Google Chrome):
1. Navigate to: `chrome://flags` in your mobile browser.
2. Search for: **"Insecure origins treated as secure"**.
3. Enable the flag and paste your local PC IP and port (e.g., `http://192.168.1.50:8000`).
4. Tap **Relaunch** on Chrome. This treats the connection as fully secure and unlocks WebRTC microphone capture without requiring commercial CA certificates!

---

## 🛠️ Configuring Actions (Tools)

### 🌐 Browser Control (`actions/browser_control.py`)
Browser automation uses Playwright to navigate, capture screenshots, and query sites.
* By default, it targets **Google Chrome** (`google-chrome-stable` on Linux).
* You can change browser behavior (e.g., enable incognito mode, use custom user-data directories, or point to other browsers like `firefox`, `edge`, or `opera`) by adjusting the parameters in `browser_control.py` or sending explicit instructions to J.A.R.V.I.S.

### 🎮 Game Updates (`actions/game_updater.py`)
Provides deep Steam and Epic Games library automation.
* It auto-detects Steam installations across Windows, macOS, and Linux.
* To coordinate background downloads, it establishes native scheduling mechanisms (`launchd` on macOS, `Task Scheduler` on Windows, or cron/systemd timers on Linux).

---

## 🐧 Linux systemd User Service

The systemd user service `voice-assistant.service` allows JARVIS to start automatically in the background as soon as your graphical desktop session boots.

### Setup and Controls:
1. Symlink or copy the service file to your systemd user configuration directory:
   ```bash
   mkdir -p ~/.config/systemd/user/
   ln -sf /home/z3ncoding123/ai-projects/Jarvis-live-assistant/voice-assistant.service ~/.config/systemd/user/voice-assistant.service
   ```
2. Reload the user systemd daemon:
   ```bash
   systemctl --user daemon-reload
   ```
3. Enable and start the service (so it launches automatically on boot):
   ```bash
   systemctl --user enable --now voice-assistant
   ```
4. Check status and logs:
   ```bash
   systemctl --user status voice-assistant
   journalctl --user -u voice-assistant -f
   ```

---

## 🚀 Running J.A.R.V.I.S.

To run the assistant manually, activate the Python environment and run the main script:
```bash
# Navigate to the workspace
cd /home/z3ncoding123/ai-projects/Jarvis-live-assistant

# Activate the virtual environment
source .venv/bin/activate

# Launch systems
python main.py
```
Enjoy your fully integrated, remote-controllable, Stark-style J.A.R.V.I.S. desktop assistant!
