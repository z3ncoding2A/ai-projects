## Configuration File 

When you run AIChat for the first time, it will automatically generate a default configuration file for you.

```
$ aichat
> No config file, create a new one? Yes
> Platform: openai
? API Key: ***
✨ Saved config file to '/home/alice/.config/aichat.yaml'

```

The location of config file is `<user-config-dir>/aichat/config.yaml`:

The config file path for each operating system are as follows:

- Windows: `C:\Users\Alice\AppData\Roaming\aichat\config.yaml`
- macOS: `/Users/Alice/Library/Application Support/aichat/config.yaml`
- Linux: `/home/alice/.config/aichat/config.yaml`

You can also run the following command to get the config file path: `aichat --info | grep config_file`.

> AIChat REPL provides a command to directly edit config.yaml: `.edit config`.

You can modify the configuration file by referring to [config.example.yaml](https://github.com/sigoden/aichat/blob/main/config.example.yaml).

## LLM

These configurations mainly set the parameters of the LLM.

```yaml
model: openai:gpt-4o             # Specify the LLM to use
temperature: null                # Set default temperature parameter, range (0, 1)
top_p: null                      # Set default top-p parameter, with a range of (0, 1) or (0, 2) depending on the model
```

If we set the model to the client's name, such as `model: openai`, AIChat will choose the first chat model from the client's model list.

The range of temperature values is variable, mostly within `[0, 1)`, but some are within `[0, 2)`, such as Gemini and Qwen. Please pay attention to this when setting the values.

## Behavior

These configurations mainly control some of aichat's behavior.

```yaml
stream: true                     # Controls whether to use the stream-style API.
save: true                       # Indicates whether to persist the message
keybindings: emacs               # Choose keybinding style (emacs, vi)
editor: null                     # Specifies the command used to edit input buffer or session.yaml. env: EDITOR
wrap: no                         # Controls text wrapping (no, auto, <max-width>)
wrap_code: false                 # Enables or disables wrapping of code blocks
```

## Function calling

These configurations mainly for function calling.

```yaml
# Visit https://github.com/sigoden/llm-functions for setup instructions
function_calling: true           # Enables or disables function calling (Globally).
mapping_tools:                   # Alias for a tool or toolset
  fs: 'fs_cat,fs_ls,fs_mkdir,fs_rm,fs_write'
use_tools: null                  # Which tools to use by default
```

If we set `function_calling: false`, it globally disables all function calling.

The `mapping_tools` configures the grouping of tools for ease of use tools later. For example, we can create an `fs` group that includes all fs-related tools.

If we set `use_tools: fs`, it's easy to use all fs-related tools. 

## Prelude

AIChat also have many working states: normal, role, session, rag, and agent.

The prelude controls which state AIChat starts in.

The following are configuration items related to `*_prelude`:

```yaml
repl_prelude: null               # Set a default role or session for REPL mode (e.g. role:<name>, session:<name>, <session>:<role>)
cmd_prelude: null                # Set a default role or session for CMD mode (e.g. role:<name>, session:<name>, <session>:<role>)
agent_prelude: null              # Set a session to use when starting a agent. (e.g. temp, default)
```

If we want to start in a `%code%` role in REPL mode, we can set `repl_prelude: "role:%code%"`.

If we want to start in a `temp` session in REPL mode, we can set `repl_prelude: "session:temp"`.

If we want to start in a `temp` session and `coder` role in REPL mode, we can set `repl_prelude: "temp:coder"`.

If we want to start in a `%shell%` role in CMD mode, we can use `cmd_prelude: "role:%shell%"`.

The agent prelude only takes effect when entering the agent.  If we set `agent_prelude: default`, it means that the session named "default" will be automatically loaded when entering the agent.


## Session

These configurations mainly set the parameters of the session.

```yaml
# Controls the persistence of the session. if true, auto save; if false, not save; if null, asking the user
save_session: null
# Compress session when token count reaches or exceeds this threshold
compress_threshold: 4000
# Text prompt used for creating a concise summary of session message
summarize_prompt: '...'
# Text prompt used for including the summary of the entire session
summary_prompt: '...'
```

If leave `save_session` as null, AIChat will prompt you to save the session when you exit.

If `save_session: true` is set, AIChat will automatically save the session upon exit.

If `save_session: false` is set, AIChat will exit without saving the session.

When the chat history tokens exceed `compress_threshold`, AIChat automatically compresses the session. `summarize_prompt` is used to guide the LLM in summarizing the chat history, and `summary_prompt` is used to include the history summary.

## RAG

These configurations mainly set the parameters of the RAG.

```yaml
rag_embedding_model: null                   # Specifies the embedding model to use
rag_reranker_model: null                    # Specifies the rerank model to use
rag_top_k: 4                                # Specifies the number of documents to retrieve
rag_chunk_size: null                        # Specifies the chunk size
rag_chunk_overlap: null                     # Specifies the chunk overlap
# Defines the query structure using variables like __CONTEXT__ and __INPUT__ to tailor searches to specific needs
rag_template: |
  ...
# Define document loaders to control how RAG and `.file`/`--file` load files of specific formats.
document_loaders:
  ...
```

See [RAG-Guide](https://github.com/sigoden/aichat/wiki/RAG-Guide) for more details.

## Appearance

These configurations mainly affect the appearance.

```yaml
highlight: true                  # Controls syntax highlighting
theme: null                      # Color theme (possible value: dark/light)
# Custom REPL prompt, see https://github.com/sigoden/aichat/wiki/Custom-REPL-Prompt for more details
left_prompt: '...'
right_prompt: '...'
```

## Misc

```yaml
serve_addr: 127.0.0.1:8000                  # Serve listening address 
user_agent: null                            # Set User-Agent HTTP header, use `auto` for aichat/<current-version>
save_shell_history: true                    # Whether to save shell execution command to the history file
sync_models_url: <url>                      # URL to sync model changes from
```

## Agent-specific

The following are the unique configuration items for the agent:

```yaml
model: openai:gpt-4o             # Specify the LLM to use
temperature: null                # Set default temperature parameter, range (0, 1)
top_p: null                      # Set default top-p parameter, with a range of (0, 1) or (0, 2) depending on the model
use_tools: null                  # Which additional tools to use by agent. (e.g. 'fs,web_search')
agent_prelude: null              # Set a session to use when starting the agent. (e.g. temp, default)
instructions: null               # Override the instructions for the agent, have no effect for dynamic instructions
variables:                       # Custom default values for the agent variables
  <key>: <value>
```

The agent configuration file is located at `<aichat-config-dir>/agents/<agent-name>/config.yaml`, 

You can obtain the agent configuration directory by using the command `aichat --agent <agent-name> --info | grep data_dir`.

## Clients

The [config.example.yaml](https://github.com/sigoden/aichat/blob/main/config.example.yaml) provides detailed configuration examples for various API providers. You can copy and paste these examples directly into your configuration. 

### Add chat models

```yaml
clients:
  - type: <client-type>
    ...
    models:
      - name: xxxx                          # The only required field
        max_input_tokens: 100000

        supports_vision: true
        supports_function_calling: true

        no_stream: true                     # Add only if LLM does not support stream
        no_system_message: true             # Add only if LLM does not support system/developer message

        # Currently only used for OpenAI's `o1/o3-mini` to enable markdown format
        system_prompt_prefix: Formatting re-enabled
```

### Add embedding models

```yaml
  - type: <client-type>
    ...
    models:
      - name: xxxx
        type: embedding
        default_chunk_size: 1500                        
        max_batch_size: 100

        # The following are optional
        max_input_tokens: 200000
        max_tokens_per_chunk: 2000
```

> `type: embedding` indicates an embedding model.

### Add reranker models

```yaml
  - type: <client-type>
    ...
    models:
      - name: xxxx
        type: reranker

        # The following are optional
        max_input_tokens: 2048
```

> `type: reranker` indicates a reranking model.

### Set socks/http(s) proxy

```yaml
clients:
  - type: <client-type>
    ...
    extra:
      proxy: socks5://127.0.0.1:1080 # or http://127.0.0.1:8080
```

### Patch API request

AIChat supports patching request url, headers and body.  

```yaml
clients:
  - type: <client-type>
    ...
    patch:                                          # Patch api
      chat_completions:                             # Api type, possible values: chat_completions, embeddings, and rerank
        <regex>:                                    # The regex to match model names, e.g. '.*' 'gpt-4o' 'gpt-4o|gpt-4-.*'
          url: ''                                   # Patch request url
          body:                                     # Patch request body
            <json>
          headers:                                  # Patch request headers
            <key>: <value>
```

#### Patch `gemini` for using the most relaxed security settings

```yaml
clients:
  - type: gemini
    ...
    patch:
      chat_completions:
        '.*':
          body:
            safetySettings:
              - category: HARM_CATEGORY_HARASSMENT
                threshold: BLOCK_NONE
              - category: HARM_CATEGORY_HATE_SPEECH
                threshold: BLOCK_NONE
              - category: HARM_CATEGORY_SEXUALLY_EXPLICIT
                threshold: BLOCK_NONE
              - category: HARM_CATEGORY_DANGEROUS_CONTENT
                threshold: BLOCK_NONE
```

#### Patch `deepseek` for using the beta API usage

```yaml
clients:
  - type: openai-compatible
    name: deepseek
    ...
    patch:
      chat_completions:
        '.*':
          url: https://api.deepseek.com/beta/chat/completions
```

### Add client for openai-compatible API provider

```yaml
clients:
  - type: openai-compatible
    name: ollama
    api_base: http://localhost:11434/v1
    api_key: xxx                                      # Optional
    models:
      - name: deepseek-r1
        max_input_tokens: 131072
        supports_reasoning: true
      - name: llama3.1
        max_input_tokens: 128000
        supports_function_calling: true
      - name: llama3.2-vision
        max_input_tokens: 131072
        supports_vision: true
      - name: nomic-embed-text
        type: embedding
        max_tokens_per_chunk: 8192
        default_chunk_size: 1000
        max_batch_size: 50
```
