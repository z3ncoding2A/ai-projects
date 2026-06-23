## How to log or debug?

Run `aichat` with the environment variable `AICHAT_LOG_LEVEL=debug`. Then check the log file at `<aichat-config-dir>/aichat.log`.

The log contains runtime details and API request and response data, which can help you troubleshoot.

## How to enable web search?

There are two ways to use web search in AIChat

1. **Use a model with built-in web search capabilities**: Some models have web search enabled by default, such as `perplexity:*`, `openrouter:*:oneline`. Some models do not support web search by default, but can be enabled via `patch`. See https://github.com/sigoden/llm-functions/blob/main/tools/web_search_aichat.sh for details.

2. **Use the `web_search` function calling**: Many models do not natively support web search, but their capabilities can be extended with function calling. This means they can use the `web_search` tool, and therefore indirectly gain web search capabilities.

## Why need compress session?

Sessions require context memory. However, The chat API is stateless. Therefore, each request needs to include the chat history.
Chat history grows rapidly with the conversation, leading to a rapid increase in data transmitted to the API server.

This presents two problems:

1. The amount of data the LLM needs to process for each request keeps increasing, resulting in longer response times and increased costs.
2. The data volume may exceed the LLM's processing capacity, leading to errors.

AICHat's strategy is to automatically compress the chat history when the number of tokens in the chat history exceeds a certain value (`compress_threshold`).

## Why LLMs don't call functions even though they support function calling?

There are several possible reasons for this, which need to be investigated one by one:

**1. The LLM doesn't support stream function calling, only non-stream function calling.**

SOLUTION: Add `-S` CLI option or Run `.set stream false` REPL command to switch to non-stream mode.

**2. The `<aichat-config-dir>/functions/functions.json` file is missing or empty.**

SOLUTION: Enter the `llm-functions` directory and rebuild the tools/agents.

**3: The input text is not related to the functions.**

SOLUTION: Adjust the input text to be relevant to the functions.

## What is the difference between agents and roles?

Roles act as a sort of prompt library, and agents are similar to OpenAI's GPTs.

An agent is a superset of a role; a role is equivalent to an agent with only the `instructions` field, while agents have additional features: variables, conversation starters, documents (RAG), and AI tools.
