#!/usr/bin/env python3
import sys
import os
import subprocess
import faulthandler
import logging

# --- Setup Logging ---
LOG_FILE = "/tmp/read_aloud_gui_debug.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=LOG_FILE,
    filemode='w' # Overwrite the log file on each run
)

faulthandler.enable()
from PyQt6.QtWidgets import (QApplication, QWidget, QHBoxLayout, 
                             QPushButton, QMenu, QStyle, QFrame,
                             QSizePolicy, QVBoxLayout, QLabel)
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import Qt, QUrl, QProcess, pyqtSignal, QTimer, QPoint, QSize

os.environ['QT_QPA_PLATFORM'] = 'xcb'

# --- Configuration ---
EDGE_TTS_PATH = os.path.expanduser("~/.local/share/read-aloud-venv/bin/edge-tts")
FFPLAY_PATH = "ffplay" # Assuming ffplay is in the system's PATH

BRITISH_VOICES = [
    ("Sonia (Female)", "en-GB-SoniaNeural"),
    ("Ryan (Male)", "en-GB-RyanNeural"),
    ("Libby (Female)", "en-GB-LibbyNeural"),
    ("Maisie (Female)", "en-GB-MaisieNeural"),
    ("Thomas (Male)", "en-GB-ThomasNeural"),
]

# --- Main Application ---
class ReadAloudBubble(QWidget):
    def __init__(self):
        super().__init__()
        logging.info("Initializing ReadAloudBubble")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("read-aloud-gui")
        self.setFixedSize(270, 80)

        self.tts_process = None
        self.player_process = None
        self.current_text = ""
        self.config_path = os.path.expanduser("~/.config/read_aloud_voice.txt")
        self.load_voice_preference()
        self.oldPos = self.pos()
        self.setToolTip("Right-click to close")
        
        self.setup_ui()
        self.center_on_screen()
        logging.info("UI Initialized successfully")

    def setup_ui(self):
        self.container_layout = QVBoxLayout(self)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame(self)
        self.container_layout.addWidget(self.frame)
        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        self.status_label = QLabel("Ready", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFixedHeight(15)
        layout.addWidget(self.status_label)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        style = self.style()
        icon_play = style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        icon_voices = style.standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton)
        icon_restart = style.standardIcon(QStyle.StandardPixmap.SP_MediaSeekBackward)
        self.btn_restart = self.create_button(icon_restart, "Restart", self.restart_audio)
        self.btn_play = self.create_button(icon_play, "Play/Stop", self.toggle_playback)
        self.btn_voices = self.create_button(icon_voices, "Select Voice", None)
        self.btn_play.setIconSize(QSize(28, 28))
        self.btn_play.setFixedSize(60, 40)
        self.btn_restart.setFixedSize(45, 40)
        self.btn_voices.setFixedSize(45, 40)
        self.setup_voice_menu()
        self.btn_voices.setMenu(self.voice_menu)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_restart)
        button_layout.addWidget(self.btn_play)
        button_layout.addWidget(self.btn_voices)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        self.apply_stylesheet()

    def create_button(self, icon, tooltip, on_click):
        button = QPushButton(self)
        button.setIcon(icon)
        button.setIconSize(QSize(22, 22))
        button.setToolTip(tooltip)
        if on_click:
            button.clicked.connect(on_click)
        return button

    def setup_voice_menu(self):
        self.voice_menu = QMenu(self)
        self.voice_actions = []
        for name, code in BRITISH_VOICES:
            action = QAction(name, self)
            action.setCheckable(True)
            if code == self.current_voice:
                action.setChecked(True)
            action.triggered.connect(lambda checked, c=code, a=action: self.set_voice(c, a))
            self.voice_menu.addAction(action)
            self.voice_actions.append(action)

    def apply_stylesheet(self):
        # Stylesheet remains the same...
        self.frame.setStyleSheet("""
            QFrame { background-color: rgba(30, 32, 44, 245); border-radius: 18px; border: 2px solid #6272a4; }
            QPushButton { background-color: #44475a; color: #f8f8f2; border: 1px solid #3b3d50; border-radius: 20px; font-size: 16px; }
            QPushButton:hover { background-color: #5b5e73; border: 1px solid #7a88c5; }
            QPushButton:pressed { background-color: #bd93f9; }
            QLabel { color: #bd93f9; font-family: "Cantarell"; font-size: 11px; font-weight: bold; padding-bottom: 2px; }
            QMenu { background-color: #282a36; color: #f8f8f2; border: 1px solid #bd93f9; border-radius: 5px; }
            QMenu::item:selected { background-color: #6272a4; }
        """)

    def toggle_playback(self):
        logging.info("toggle_playback called.")
        if (self.tts_process and self.tts_process.state() == QProcess.ProcessState.Running) or 
           (self.player_process and self.player_process.state() == QProcess.ProcessState.Running):
            logging.info("Processes are running, stopping audio.")
            self.stop_audio()
        else:
            logging.info("No process running, starting read and play.")
            self.read_and_play_highlighted_text()

    def read_and_play_highlighted_text(self):
        logging.info("Attempting to read highlighted text.")
        self.stop_audio()
        
        text = ""
        try:
            result = subprocess.run(["wl-paste", "-p"], capture_output=True, text=True, check=True, timeout=1)
            text = result.stdout.strip()
            logging.info(f"Got primary selection: '{text[:50]}...'")
        except Exception as e:
            logging.warning(f"Failed to get primary selection: {e}")
            text = ""

        if not text:
            try:
                result = subprocess.run(["wl-paste"], capture_output=True, text=True, check=True, timeout=1)
                text = result.stdout.strip()
                logging.info(f"Got clipboard text: '{text[:50]}...'")
            except Exception as e:
                logging.warning(f"Failed to get clipboard text: {e}")
                text = ""
        
        if not text:
            logging.warning("No text found in selection or clipboard.")
            self.update_status("Selection is empty", 1500)
            return

        self.current_text = text
        self.play_audio()

    def play_audio(self):
        if not self.current_text:
            logging.error("play_audio called with no current_text.")
            return

        self.update_status("Generating...")
        logging.info("Starting audio playback processes.")

        self.tts_process = QProcess(self)
        self.player_process = QProcess(self)
        
        self.tts_process.setStandardOutputProcess(self.player_process)

        self.player_process.finished.connect(self.on_playback_finished)
        self.tts_process.readyReadStandardError.connect(self.log_tts_error)
        self.player_process.readyReadStandardError.connect(self.log_player_error)

        ffplay_args = ["-nodisp", "-autoexit", "-i", "-"]
        logging.info(f"Starting player_process: {FFPLAY_PATH} {' '.join(ffplay_args)}")
        self.player_process.start(FFPLAY_PATH, ffplay_args)

        tts_args = ["--text", self.current_text, "--voice", self.current_voice]
        logging.info(f"Starting tts_process: {EDGE_TTS_PATH} --voice {self.current_voice} --text '...'")
        self.tts_process.start(EDGE_TTS_PATH, tts_args)
        
        QTimer.singleShot(200, self.check_if_playing)

    def log_tts_error(self):
        error_output = self.tts_process.readAllStandardError().data().decode().strip()
        if error_output:
            logging.error(f"TTS Process stderr: {error_output}")

    def log_player_error(self):
        error_output = self.player_process.readAllStandardError().data().decode().strip()
        if error_output:
            logging.error(f"Player Process stderr: {error_output}")

    def check_if_playing(self):
        if self.player_process and self.player_process.state() == QProcess.ProcessState.Running:
            logging.info("check_if_playing: Confirmed player is running.")
            self.update_status("Playing...")
            self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))

    def on_playback_finished(self):
        logging.info("on_playback_finished called.")
        self.update_status("Finished")
        self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        
        self.stop_audio() # Ensure everything is cleaned up
        QTimer.singleShot(1500, lambda: self.update_status("Ready"))
        
    def stop_audio(self):
        logging.info("stop_audio called.")
        if self.tts_process and self.tts_process.state() != QProcess.ProcessState.NotRunning:
            self.tts_process.kill()
            logging.info("Killed tts_process.")
        if self.player_process and self.player_process.state() != QProcess.ProcessState.NotRunning:
            self.player_process.kill()
            logging.info("Killed player_process.")
        self.tts_process = None
        self.player_process = None

    def restart_audio(self):
        logging.info("restart_audio called.")
        self.stop_audio()
        QTimer.singleShot(100, self.play_audio)

    # Other methods (set_voice, load_voice_preference, etc.) remain largely the same...
    def set_voice(self, code, action):
        self.current_voice = code
        for a in self.voice_actions:
            if a is not action: a.setChecked(False)
        action.setChecked(True)
        try:
            with open(self.config_path, "w") as f: f.write(code)
            self.update_status(f"Voice set", 1500)
            logging.info(f"Set and saved voice: {code}")
        except IOError as e:
            logging.error(f"Error saving voice: {e}")
            self.update_status("Error saving voice", 1500)

    def load_voice_preference(self):
        self.current_voice = BRITISH_VOICES[0][1]
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    saved_voice = f.read().strip()
                    if any(saved_voice == code for name, code in BRITISH_VOICES):
                        self.current_voice = saved_voice
                logging.info(f"Loaded voice preference: {self.current_voice}")
            except IOError as e:
                logging.error(f"Error loading voice preference: {e}")
    
    def update_status(self, message, timeout=0):
        self.status_label.setText(message)
        if timeout > 0:
            QTimer.singleShot(timeout, lambda: self.status_label.setText("Ready"))
            
    def center_on_screen(self):
        try:
            screen_geometry = self.screen().geometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = screen_geometry.height() - self.height() - 60
            self.move(x, y)
        except Exception as e:
            logging.error(f"Could not center on screen: {e}")
            self.move(400, 800)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.oldPos = event.globalPosition().toPoint()
        elif event.button() == Qt.MouseButton.RightButton: self.close()

    def mouseMoveEvent(self, event):
        if self.oldPos:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def closeEvent(self, event):
        logging.info("Close event called. Stopping audio.")
        self.stop_audio()
        super().closeEvent(event)

if __name__ == '__main__':
    logging.info("Application starting.")
    app = QApplication(sys.argv)
    app.setApplicationName("read-aloud-gui")
    
    bubble = ReadAloudBubble()
    bubble.show()
    
    sys.exit(app.exec())
