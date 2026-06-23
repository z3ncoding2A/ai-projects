The prompts can display information about the current context, such as the active role, session, RAG, or agent.

## States & Showcases

| STATE             | SHOWCASE                                                                                            |
| :---------------- | :-------------------------------------------------------------------------------------------------- |
| none              | <img src="https://github.com/sigoden/aichat/assets/4012553/083cf347-77aa-4601-b399-3c49d0665c71" /> |
| role              | <img src="https://github.com/sigoden/aichat/assets/4012553/052ecc9f-10d1-4cec-b2e8-4d80010185a3" /> |
| session           | <img src="https://github.com/sigoden/aichat/assets/4012553/af87c87e-4ee0-47c6-ac32-b88b86f8125a" /> |
| agent             | <img src="https://github.com/sigoden/aichat/assets/4012553/5961cff0-2561-4afc-b51c-ea7222d842e7" /> |
| rag               | <img src="https://github.com/sigoden/aichat/assets/4012553/b0b5e692-ff75-40ba-8090-5c1b0b10e080"/>  |
| session+role      | <img src="https://github.com/sigoden/aichat/assets/4012553/a6a04196-b55f-4937-97b9-c51327c83c41" /> |
| session+rag       | <img src="https://github.com/sigoden/aichat/assets/4012553/811be1b1-ad4a-4445-9b41-9024b734bc04"/>  |
| session+role+rag  | <img src="https://github.com/sigoden/aichat/assets/4012553/b0fd3f7a-c6cc-4510-9a46-2fdd6200b673"/>  |
| agent+session     | <img src="https://github.com/sigoden/aichat/assets/4012553/cdbb6217-926a-4527-ad82-c2ef7e8313fe" /> |
| agent+rag         | <img src="https://github.com/sigoden/aichat/assets/4012553/47c8d1d2-e090-4a1d-95fb-fa40764ae0da" /> |
| agent+session+rag | <img src="https://github.com/sigoden/aichat/assets/4012553/053d4ce5-3026-40e6-9686-5fb005d9ceb0" /> |

## Configuration

Edit the `left_prompt` and `right_prompt` configuration items to customize the REPL's left and right prompts.

The default configuration:
```yaml
# REPL left prompt
left_prompt: '{color.green}{?session {?agent {agent}>}{session}{?role /}}{!session {?agent {agent}>}}{role}{?rag @{rag}}{color.cyan}{?session )}{!session >}{color.reset} '
# REPL right prompt
right_prompt: '{color.purple}{?session {?consume_tokens {consume_tokens}({consume_percent}%)}{!consume_tokens {consume_tokens}}}{color.reset}'
```

## Syntaxes

The prompt template comprises plain text and `{...}`. 

The syntax of `{...}` is:
- `{var}` - Replace with value of `var`
- `{?var <template>}` - Eval `template` when `var` is evaluated as true
- `{!var <template>}` - Eval `template` when `var` is evaluated as false

## Variables

```yaml
# Model
model: openai:gpt-4
client_name: openai
model_name: gpt-4
max_input_tokens: 4096

# Config
temperature: 1.0
top_p: 0.9
dry_run: true
stream: false
save: true
wrap: 120

role: coder

# Session
session: temp
dirty: false
consume_tokens: 200
consume_percent: 1%
user_messages_len: 0

rag: temp

agent: todo-sh

# ANSI COLORS
color.reset:
color.black:
color.dark_gray:
color.red:
color.light_red:
color.green:
color.light_green:
color.yellow:
color.light_yellow:
color.blue:
color.light_blue:
color.purple:
color.light_purple:
color.magenta:
color.light_magenta:
color.cyan:
color.light_cyan:
color.white:
color.light_gray:
```