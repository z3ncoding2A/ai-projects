Role: Senior Linux Software Engineer and UI/UX Developer. Task: Build a fast, Wayland-native Text-to-Speech (TTS) GUI pop-up tailored specifically for the Hyprland window manager.
Context & Workflow: The user will highlight text in any application and press SUPER + SHIFT + M. This must instantly spawn a lightweight GUI pop-up that captures the highlighted text (primary selection) and immediately begins reading it aloud using a local neural TTS engine.
Technical Constraints & Requirements:
• Programming Stack: Use Python with a modern GUI framework (PyQt6 or GTK4) for fast execution and a native appearance.

• Clipboard Handling: Use Wayland's primary selection via wl-clipboard (e.g., wl-paste -p executed via subprocess) to grab the highlighted text without requiring a manual Ctrl+C.

• TTS Engine (Strictly Offline): Implement piper TTS to ensure entirely local, low-latency, and high-fidelity speech generation. The script should look for local .onnx model files. Limit the configuration to use only Female UK voice models.

• GUI Elements & Threading: * A dropdown menu to switch between the available local Female UK voices.
◇ A slider to adjust playback speed.

◇ A 'Stop/Close' button to interrupt playback immediately.

◇ Crucial: Audio processing and playback must not block the main GUI thread.



• Window Lifecycle: The application must automatically terminate (close the UI and kill processes) the exact moment the audio stream finishes playing, unless manually dismissed earlier.

• Hyprland Integration: Provide the exact hyprland.conf lines needed to bind the key (SUPER + SHIFT + M) and the windowrulev2 parameters to ensure the app opens floating, centered, and sized appropriately.


Deliverables:
1. The complete, well-commented Python source code.

2. Step-by-step terminal instructions for installing dependencies (e.g., python-pyqt6, piper-tts, wl-clipboard) and downloading the required voice models.

3. The specific lines to add to hyprland.conf.

