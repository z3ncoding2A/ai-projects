import json
import logging
import queue
import threading
import time
from pathlib import Path

import sounddevice as sd
import vosk

logger = logging.getLogger(__name__)

class WakeWordListener:
    def __init__(self, wake_words: str, sensitivity: float, on_detected_callback):
        self.wake_words = wake_words.lower().strip()
        self.sensitivity = sensitivity
        self.on_detected_callback = on_detected_callback
        
        self.model_path = Path.home() / ".local" / "share" / "hyprwhspr" / "models" / "vosk-model-small-en-us-0.15"
        self.model = None
        self.recognizer = None
        
        self._audio_queue = queue.Queue()
        self._listen_thread = None
        self._stop_event = threading.Event()
        self._is_paused = threading.Event()
        
        self.device = None  # Use default input device
        try:
            device_info = sd.query_devices(sd.default.device[0], 'input')
            self.samplerate = int(device_info['default_samplerate'])
            logger.info(f"[WAKE_WORD] Using default device sample rate: {self.samplerate}")
        except Exception as e:
            logger.warning(f"[WAKE_WORD] Could not determine default sample rate, falling back to 16000: {e}")
            self.samplerate = 16000
        
        # Parse multiple wake words if comma separated
        self.target_words = [w.strip() for w in self.wake_words.split(',')]
        
    def initialize(self) -> bool:
        """Initialize the Vosk model and recognizer"""
        try:
            if not self.model_path.exists():
                logger.error(f"[WAKE_WORD] Vosk model not found at {self.model_path}")
                return False
                
            logger.info(f"[WAKE_WORD] Loading Vosk model from {self.model_path}")
            # Reduce Vosk log spam
            vosk.SetLogLevel(-1)
            
            self.model = vosk.Model(str(self.model_path))
            
            # We initialize without a grammar constraint.
            # Using a constrained grammar (like just "speak") causes Vosk to forcefully map
            # any background speech (e.g., from a YouTube video) into the target word,
            # resulting in massive false positives. Allowing free transcription prevents this.
            self.recognizer = vosk.KaldiRecognizer(self.model, self.samplerate)
            return True
        except Exception as e:
            logger.error(f"[WAKE_WORD] Initialization failed: {e}")
            return False

    def start(self):
        """Start the background listening thread"""
        if not self.model:
            if not self.initialize():
                return False
                
        self._stop_event.clear()
        self._is_paused.clear()
        
        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="WakeWordListener"
        )
        self._listen_thread.start()
        logger.info(f"[WAKE_WORD] Started listening for: {self.target_words}")
        return True
        
    def stop(self):
        """Stop the background listener entirely"""
        self._stop_event.set()
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=2.0)
            
    def pause(self):
        """Temporarily pause listening (e.g., when dictation starts)"""
        logger.info("[WAKE_WORD] Pausing listener")
        self._is_paused.set()
        # Clear the queue to discard any buffered audio
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
                
    def resume(self):
        """Resume listening after a pause"""
        logger.info("[WAKE_WORD] Resuming listener")
        self._is_paused.clear()
        
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for sounddevice to feed audio into our queue"""
        if status:
            logger.debug(f"[WAKE_WORD] Audio status: {status}")
            
        if not self._is_paused.is_set():
            self._audio_queue.put(bytes(indata))
            
    def _listen_loop(self):
        """Main listening loop that processes audio through Vosk"""
        try:
            with sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=8000,
                device=self.device,
                dtype='int16',
                channels=1,
                callback=self._audio_callback
            ):
                while not self._stop_event.is_set():
                    if self._is_paused.is_set():
                        time.sleep(0.1)
                        continue
                        
                    try:
                        # Wait for audio data with a timeout to allow checking stop_event
                        data = self._audio_queue.get(timeout=0.5)
                        
                        if self.recognizer.AcceptWaveform(data):
                            result = json.loads(self.recognizer.Result())
                            self._process_result(result.get('text', ''))
                        else:
                            # Also check partial results for faster response
                            partial = json.loads(self.recognizer.PartialResult())
                            self._process_result(partial.get('partial', ''))
                            
                    except queue.Empty:
                        pass
                    except Exception as e:
                        logger.error(f"[WAKE_WORD] Error processing audio: {e}")
                        time.sleep(0.1)
                        
        except Exception as e:
            logger.error(f"[WAKE_WORD] InputStream failed: {e}")
            
    def _process_result(self, text: str):
        """Check if recognized text contains our wake word"""
        if not text:
            return
            
        text_lower = text.lower()
        import re
        
        for word in self.target_words:
            if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
                logger.info(f"[WAKE_WORD] Trigger word detected: '{word}'")
                # Reset recognizer to clear the partial state
                self.recognizer.Reset()
                # Pause ourselves so we don't double-trigger
                self.pause()
                # Fire the callback asynchronously
                threading.Thread(target=self.on_detected_callback, daemon=True).start()
                return
