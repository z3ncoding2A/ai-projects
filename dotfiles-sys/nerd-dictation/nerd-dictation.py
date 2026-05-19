# User configuration file typically located at `~/.config/nerd-dictation/nerd-dictation.py`
import re

CLOSING_PUNCTUATION = {
    "period": ".",
    "comma": ",",
    "question mark": "?",
    "exclamation mark": "!",
    "exclamation point": "!",
    "close quote": "\"",
    "close parenthesis": ")",
    "close bracket": "]",
    "close brace": "}",
    "colon": ":",
    "semicolon": ";",
    "hyphen": "-",
    "dash": "-",
    "slash": "/",
    "backslash": "\\",
}

OPENING_PUNCTUATION = {
    "open quote": "\"",
    "open parenthesis": "(",
    "open bracket": "[",
    "open brace": "{",
}

WORD_REPLACE = {
    "i": "I",
    "api": "API",
    "linux": "Linux",
    "um": "",
}

def nerd_dictation_process(text):
    for match, replacement in CLOSING_PUNCTUATION.items():
        text = text.replace(" " + match, replacement)
        if text.startswith(match):
            text = text.replace(match, replacement, 1)

    for match, replacement in OPENING_PUNCTUATION.items():
        text = text.replace(match + " ", replacement)
        if text.endswith(match):
            text = replacement.join(text.rsplit(match, 1))

    words = text.split(" ")

    for i, w in enumerate(words):
        w_init = w
        w_test = WORD_REPLACE.get(w)
        if w_test is not None:
            w = w_test
        words[i] = w

    words[:] = [w for w in words if w]

    return " ".join(words)
