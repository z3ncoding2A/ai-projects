#!/bin/bash

# Configuration file for storing the selected model
CONF_FILE="$HOME/.config/rofi/rofi-ai.conf"

# Read the current model from the config file, or use a default
current_model=$(cat "$CONF_FILE" 2>/dev/null || echo "gemini-pro")

# Rofi prompt with the current model
prompt="Ask AI ($current_model):"

# Get user input from Rofi
question=$(rofi -dmenu -p "$prompt")

# Check if the user wants to select a model
if [ "$question" == ":model" ]; then
    # List of available models (you can add more here)
    models="gemini-pro
gemini-1.5-pro-latest
gemini-ultra
gemini-pro-vision"

    # Show the model selection menu
    selected_model=$(echo -e "$models" | rofi -dmenu -p "Select a model")

    # If a model was selected, save it to the config file
    if [ -n "$selected_model" ]; then
        echo "$selected_model" > "$CONF_FILE"
        rofi -e "Model set to: $selected_model"
    fi
    exit
fi

# If the user asked a question, proceed to call the AI
if [ -n "$question" ]; then
    # Call the gemini command with the selected model
    output=$(gemini --model "$current_model" "$question" 2>&1)
    exit_code=$?

    # Check if the command was successful
    if [ $exit_code -eq 0 ]; then
        # Success, show the answer
        echo -e "$output" | rofi -dmenu -p "AI Response"
    else
        # Error, show the error message
        echo -e "An error occurred:
$output" | rofi -dmenu -p "Error"
    fi
fi
