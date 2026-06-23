import os
import sys
import time
import socket
import argparse
import subprocess
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from google import genai
from google.genai import types

# Configuration
SOCKET_PATH = "/tmp/hyper_commander.sock"
MODEL_SIZE = "tiny.en"
SAMPLE_RATE = 16000
CHUNK_DURATION = 0.5
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)

class DesktopAssistant:
    def __init__(self):
        if not os.environ.get("GEMINI_API_KEY"):
            print("ERROR: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
            sys.exit(1)
            
        print("Initializing Gemini client...")
        self.gemini_client = genai.Client()
        
        print(f"Loading Whisper model ({MODEL_SIZE}) for Hyper Commander...")
        self.model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        
        self.is_recording = False
        self.recording_buffer = []
        self.ui_process = None
        self.stream = None

    def show_ui(self):
        if self.ui_process is None:
            ui_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mic_ui.py")
            self.ui_process = subprocess.Popen(["/usr/bin/python3", ui_script])

    def hide_ui(self):
        if self.ui_process is not None:
            self.ui_process.kill()
            self.ui_process.wait()
            self.ui_process = None

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            pass
        if self.is_recording:
            self.recording_buffer.append(indata.copy().flatten())

    def start_recording(self):
        if self.is_recording:
            return
        print("Recording started...")
        self.recording_buffer = []
        self.is_recording = True
        
        # Start the audio stream only when actively recording to avoid locking the mic
        self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32', callback=self.audio_callback, blocksize=CHUNK_SAMPLES)
        self.stream.start()
        
        self.show_ui()

    def stop_recording_and_process(self):
        if not self.is_recording:
            return
        print("Recording stopped. Processing...")
        self.is_recording = False
        
        # Stop and release the audio stream
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            
        self.hide_ui()
        
        if len(self.recording_buffer) == 0:
            return
            
        audio = np.concatenate(self.recording_buffer)
        segments, _ = self.model.transcribe(audio, language="en")
        text = " ".join([segment.text for segment in segments]).strip()
        
        if not text:
            print("No speech detected.")
            return
            
        print(f"Transcribed: '{text}'")
        self.execute_with_llm(text)

    def execute_with_llm(self, user_command):
        try:
            system_instruction = ""
            prompt_file = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
            if os.path.exists(prompt_file):
                with open(prompt_file, "r") as f:
                    system_instruction = f.read()
            else:
                system_instruction = "You are 'Hyper', an AI desktop assistant. Output ONLY raw bash/hyprctl commands."

            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_command,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.0,
                )
            )
            
            if not response:
                return
            
            llm_output = response.text.strip()
            if llm_output.startswith('#'):
                print(f"[Hyper responds]: {llm_output[1:].strip()}")
            else:
                print(f"[Gemini Action]: {llm_output}")
                subprocess.Popen(llm_output, shell=True, executable='/bin/bash')
                
        except Exception as e:
            print(f"Error: {e}")

    def run_daemon(self):
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
            
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(SOCKET_PATH)
        server.listen(1)
        print("Daemon listening for toggle commands...")
        print("Run 'python main.py toggle' to start/stop recording.")

        try:
            while True:
                conn, _ = server.accept()
                data = conn.recv(1024).decode().strip()
                if data == "toggle":
                    if self.is_recording:
                        self.stop_recording_and_process()
                    else:
                        self.start_recording()
                conn.close()
        except KeyboardInterrupt:
            pass
        finally:
            server.close()
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)

def send_command(cmd):
    if not os.path.exists(SOCKET_PATH):
        print("Daemon is not running. Please start it first.")
        sys.exit(1)
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(SOCKET_PATH)
    client.sendall(cmd.encode())
    client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hyper Commander")
    parser.add_argument("command", nargs="?", choices=["daemon", "toggle"], default="daemon", help="Command to run")
    args = parser.parse_args()

    if args.command == "toggle":
        send_command("toggle")
    else:
        assistant = DesktopAssistant()
        assistant.run_daemon()
