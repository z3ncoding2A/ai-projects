## Usage

```
Usage: aichat [OPTIONS] [TEXT]...

Arguments:
  [TEXT]...  Input text

Options:
  -m, --model <MODEL>                  Select a LLM model
      --prompt <PROMPT>                Use the system prompt
  -r, --role <ROLE>                    Select a role
  -s, --session [<SESSION>]            Start or join a session
      --empty-session                  Ensure the session is empty
      --save-session                   Ensure the new conversation is saved to the session
  -a, --agent <AGENT>                  Start a agent
      --agent-variable <NAME> <VALUE>  Set agent variables
      --rag <RAG>                      Start a RAG
      --rebuild-rag                    Rebuild the RAG to sync document changes
      --macro <MACRO>                  Execute a macro
      --serve [<ADDRESS>]              Serve the LLM API and WebAPP
  -e, --execute                        Execute commands in natural language
  -c, --code                           Output code only
  -f, --file <FILE>                    Include files, directories, or URLs
  -S, --no-stream                      Turn off stream mode
      --dry-run                        Display the message without sending it
      --info                           Display information
      --sync-models                    Sync models updates
      --list-models                    List all available chat models
      --list-roles                     List all roles
      --list-sessions                  List all sessions
      --list-agents                    List all agents
      --list-rags                      List all RAGs
      --list-macros                    List all macros
  -h, --help                           Print help
  -V, --version                        Print version
```

## Examples

```sh
aichat                                          # Enter REPL
aichat Tell a joke                              # Generate response

aichat -e install nvim                          # Execute command
aichat -c fibonacci in js                       # Generate code

aichat --serve                                  # Run server
aichat --serve 0.0.0.0:8080                     # Run server with addr

aichat -m openai:gpt-4o                         # Select LLM

aichat -r role1                                 # Use role 'role1'
aichat -s                                       # Begin a temp session
aichat -s session1                              # Use session 'session1'
aichat -a agent1                                # Use agent 'agent1'
aichat --rag rag1                               # Use RAG 'rag1'

aichat --info                                   # View system info
aichat -r role1 --info                          # View role info
aichat -s session1 --info                       # View session info
aichat -a agent1 --info                         # View agent info
aichat --rag rag1 --info                        # View RAG info

aichat --macro macro1                           # Execute macro 'macro1'
aichat --macro macro2 arg1 arg2                 # Execute macro 'macro2' with args

cat data.toml | aichat -c to json > data.json   # Pipe Input/Output
output=$(aichat -S $input)                      # Run in the script

aichat -f a.png -f b.png diff images            # Use files
```

## Shell Assistant

Simply input what you want to do in natural language, and aichat will prompt and run the command that achieves your intent.

![aichat-execute](https://github.com/user-attachments/assets/0c77e901-0da2-4151-aefc-a2af96bbb004)

**AIChat is aware of OS and shell you are using, it will provide shell command for specific system you have.**

## Shell Integration

Simply type `alt+e` to let `aichat` provide intelligent completions directly in your terminal.

![aichat-integration](https://github.com/sigoden/aichat/assets/4012553/873ebf23-226c-412e-a34f-c5aaa7017524)

AIChat offers shell integration scripts for for bash, zsh, PowerShell, fish, and nushell. You can find them on GitHub at [https://github.com/sigoden/aichat/tree/main/scripts/shell-integration](https://github.com/sigoden/aichat/tree/main/scripts/shell-integration).

## Shell Autocompletion

The shell autocompletion suggests commands, options, and filenames as you type, enabling you to type less, work faster, and avoid typos.

![aichat-autocompletions](https://github.com/sigoden/aichat/assets/4012553/29dd7497-441f-4b64-b36e-2bcbc5e66202)

AIChat offers shell completion scripts for bash, zsh, PowerShell, fish, and nushell. You can find them on GitHub at [https://github.com/sigoden/aichat/tree/main/scripts/completions](https://github.com/sigoden/aichat/tree/main/scripts/completions).

## Generate Code

By using the `--code` or `-c` parameter, you can specifically request pure code output.

![aichat-code](https://github.com/sigoden/aichat/assets/4012553/2bbf7c8a-3822-4222-9498-693dcd683cf4)

**The `-c/--code` with pipe ensures the extraction of code from Markdown.**

## Use Files & Urls

The `-f/--file` can be used to send files to LLMs. 

```sh
# Use local file
aichat -f data.txt
# Use image file
aichat -f image.png ocr
# Use multi files
aichat -f file1 -f file2 explain
# Use local dirs
aichat -f dir/ summarize
# Use remote URLs
aichat -f https://example.com/page summarize
```

## Run Server

AIChat comes with a built-in lightweight http server.

```
$ aichat --serve
Chat Completions API: http://127.0.0.1:8000/v1/chat/completions
Embeddings API:       http://127.0.0.1:8000/v1/embeddings
LLM Playground:       http://127.0.0.1:8000/playground
LLM Arena:            http://127.0.0.1:8000/arena?num=2
```

Change the listening address:
```
$ aichat --serve 0.0.0.0
$ aichat --serve 8080
$ aichat --serve 0.0.0.0:8080
```
