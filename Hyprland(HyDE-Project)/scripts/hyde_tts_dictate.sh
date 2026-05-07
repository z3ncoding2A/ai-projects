#!/bin/bash

# Text-to-Speech and Dictation Application for Hyprland

# --- Configuration ---
# TTS Model path (adjust if you have a different model)
# Assumes piper is in PATH and model is accessible. Adjust path if needed.
TTS_MODEL="/usr/share/piper/en_US-lessac-medium.onnx"

# Path to whisper.cpp executable (assuming it's compiled as 'main' and in PATH)
WHISPER_CMD="main"

# STT Model path for whisper.cpp (ensure it's downloaded and accessible)
# IMPORTANT: User needs to set this path correctly if not in default location
WHISPER_MODEL="/home/z3ncoding123/.local/share/whisper.cpp/models/ggml-base.en.bin"

# Audio recording command and format
# Using arecord for simplicity, ensure it's installed and configured
# '-d 5' sets a default recording duration of 5 seconds if user doesn't manually stop.
# User can press Enter to stop recording manually.
RECORD_CMD="arecord -r 16000 -f S16_LE -c 1 -d 5"
AUDIO_TEMP_FILE="/tmp/hyde_tts_dictate_recording.wav"

# Audio player for TTS output
# Using ffplay for broad compatibility, ensure it's installed. Needs to match Piper model sample rate.
AUDIO_PLAYER="ffplay -nodisp -autoexit -f s16le -ar 16000 -ac 1 -loglevel quiet"

# Zenity dialog settings
DIALOG_TITLE="Hyprland TTS & Dictation"

# --- Helper Functions ---

# Function to speak text using Piper TTS
speak_text() {
    local text="$1"
    echo "Speaking: '$text'" >&2 # Log to stderr for debugging
    # Use echo to pipe text to piper, then pipe raw PCM to ffplay
    # Ensure the sample rate (-ar) in ffplay matches the model (16000 Hz for en_US-lessac-medium.onnx)
    echo -n "$text" | piper --model "$TTS_MODEL" --output-raw | $AUDIO_PLAYER - 
}

# Function to dictate audio using whisper.cpp
dictate_audio() {
    # Use zenity to prompt for recording duration or to start recording
    # For now, we'll use arecord default duration and prompt user to press Enter
    zenity --info --text="Recording started. Speak clearly. Press Enter to stop." --timeout=5 & # Show a brief notification, run in background
    RECORD_PID=$!

    # Record audio to a temporary file
    # The '-d 5' in RECORD_CMD is a fallback duration, user can press Enter to stop earlier.
    $RECORD_CMD "$AUDIO_TEMP_FILE" </dev/null # Redirect stdin to avoid arecord waiting for input
    
    # Kill the zenity notification if it's still running
    kill $ZENITY_NOTIF_PID 2>/dev/null

    if [ $? -eq 0 ] && [ -s "$AUDIO_TEMP_FILE" ]; then
        echo "Processing audio with Whisper..." >&2 # Log to stderr
        # Transcribe using whisper.cpp (assuming output to stdout is plain text)
        # Using '-nt' to disable timestamps for simpler integration into text area
        # Using '-l en' for English, adjust if multilingual is needed
        # Using '--output json' and jq to extract text
        local transcription=$($WHISPER_CMD -m "$WHISPER_MODEL" -f "$AUDIO_TEMP_FILE" -nt -l en --output json 2>/dev/null | jq -r '.text')
        
        if [ $? -eq 0 ] && [ -n "$transcription" ]; then
            echo "Transcription: $transcription" >&2 # Log to stderr
            echo "$transcription" # Output transcription to zenity for selection
        else
            # Check if whisper command itself failed or if jq failed
            if ! command -v jq >/dev/null 2>&1; then
                zenity --error --text="jq is not installed. Please install jq for JSON parsing."
            else
                zenity --error --text="Error during transcription. Ensure whisper.cpp is installed and model path is correct."
            fi
            return 1
        fi
        # Clean up temporary audio file
        rm -f "$AUDIO_TEMP_FILE"
    else
        # If recording failed or file is empty
        if [ -f "$AUDIO_TEMP_FILE" ]; then
             rm -f "$AUDIO_TEMP_FILE"
        fi
        zenity --error --text="Error during audio recording or file is empty. Ensure microphone is working."
        return 1
    fi
}

# --- Prerequisite Checks ---

check_command() {
    command -v "$1" >/dev/null 2>&1 || { echo "Error: '$1' command not found. Please install it."; return 1; }
}

check_file() {
    [ ! -f "$1" ] && { echo "Error: File not found at '$1'. Please set the correct path."; return 1; }
}

# Check for essential commands
check_command piper || exit 1
check_command $WHISPER_CMD || exit 1
check_command ffplay || exit 1
check_command arecord || exit 1
check_command jq || exit 1
check_command zenity || exit 1

# Check for required model files
check_file "$TTS_MODEL" || exit 1
check_file "$WHISPER_MODEL" || exit 1

# --- Main Application Loop ---

# Variable to store the last spoken/dictated text for 'Play' functionality
LAST_PROCESSED_TEXT=""

# Variable to store the PID of the TTS playback process for stopping
TTS_PID=0

while true; do
    # Use zenity to create the dialog
    # --text-info: displays text, can be read-only or editable
    # --editable: makes the text area editable
    # --ok-label, --cancel-label, --extra-button: customizes buttons
    # Exit status: 0=OK (Speak), 1=Cancel (Dictate), 2=Play, 3=Clear, 4=Stop, <0=Closed

    # Capture the output from zenity, which includes the edited text if OK/Cancel is pressed
    # Use a temporary variable to build the text shown in the dialog
    DIALOG_TEXT_CONTENT="Last spoken/dictated:"
    if [ -n "$LAST_PROCESSED_TEXT" ]; then
        DIALOG_TEXT_CONTENT="$LAST_PROCESSED_TEXT"
    fi
    
    # Store the current text input before button presses for 'Play'/'Speak'
    CURRENT_INPUT_TEXT="$(echo "$LAST_PROCESSED_TEXT" | sed 's/^Last spoken\/dictated: //')"
    
    DIALOG_OUTPUT=$(zenity --width=600 --height=400 --text-info --editable --title="$DIALOG_TITLE" --text="$DIALOG_TEXT_CONTENT" --ok-label="Speak" --cancel-label="Dictate" --extra-button="Play" --extra-button="Clear" --extra-button="Stop" --buttons-layout=center 2>/dev/null)
    
    EXIT_STATUS=$?

    case $EXIT_STATUS in
        0) # Speak button pressed
            TEXT_TO_PROCESS="$(echo "$DIALOG_OUTPUT" | sed 's/^Last spoken\/dictated: //')"
            if [ -n "$TEXT_TO_PROCESS" ]; then
                LAST_PROCESSED_TEXT="Last spoken/dictated: $TEXT_TO_PROCESS"
                # Stop any previous TTS playback before starting new one
                if [ $TTS_PID -ne 0 ]; then pkill -x ffplay; fi
                speak_text "$TEXT_TO_PROCESS" &
                TTS_PID=$!
            fi
            ;;
        1) # Dictate button pressed
            # Record and transcribe
            TRANSCRIPTION=$(dictate_audio)
            if [ $? -eq 0 ] && [ -n "$TRANSCRIPTION" ]; then
                # Append transcription to the text area for editing/speaking
                # If LAST_PROCESSED_TEXT already contains content, append to it
                CURRENT_DIALOG_TEXT="$(echo "$DIALOG_OUTPUT" | sed 's/^Last spoken\/dictated: //')"
                if [ -n "$CURRENT_DIALOG_TEXT" ]; then
                    LAST_PROCESSED_TEXT="Last spoken/dictated: $CURRENT_DIALOG_TEXT
$TRANSCRIPTION"
                else
                    LAST_PROCESSED_TEXT="Last spoken/dictated: $TRANSCRIPTION"
                fi
            fi
            ;;
        2) # Play button pressed
            TEXT_TO_PLAY="$(echo "$DIALOG_OUTPUT" | sed 's/^Last spoken\/dictated: //')"
            if [ -n "$TEXT_TO_PLAY" ]; then
                # Stop previous playback if any
                if [ $TTS_PID -ne 0 ]; then pkill -x ffplay; fi
                speak_text "$TEXT_TO_PLAY" &
                TTS_PID=$!
            fi
            ;;
        3) # Clear button pressed
            LAST_PROCESSED_TEXT="Last spoken/dictated: "
            ;;
        4) # Stop button pressed
            if [ $TTS_PID -ne 0 ]; then
                pkill -x ffplay # Terminate any running ffplay processes
                TTS_PID=0
                echo "Playback stopped." >&2 # Log to stderr
            fi
            ;;
        *) # User closed the dialog (ESC, Window Close, etc.)
            echo "Dialog closed by user." >&2
            # Ensure any running TTS process is stopped
            if [ $TTS_PID -ne 0 ]; then pkill -x ffplay; fi
            exit 0
            ;;
    esac
    # Loop continues, redrawing the dialog with potentially updated LAST_PROCESSED_TEXT
done
