"""Tool registry for LLM tool-calling (Gemini Live API and Anthropic).

A lightweight, dependency-free registry that turns a plain Python function plus its
signature and docstring into tool schemas. Register a tool by decorating
it with ``@register_tool``; the daemon/LLM router pulls schemas via
``get_gemini_tools()`` for Gemini Live API, or ``get_tool_schemas()`` for Anthropic,
and dispatches model tool calls through ``call_tool()``.

Adding a new tool later requires only:

    @register_tool
    def my_tool(some_arg: str) -> str:
        \"\"\"One-line description shown to the model. Say WHEN to use it.\"\"\"
        ...
        return "human-readable result"

No other change is needed -- the schema is derived automatically.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Callable

from execution.hypr import dispatch_exec

logger = logging.getLogger(__name__)

# Map Python type hints to JSON Schema primitive types. Anything not listed
# (custom classes, etc.) falls back to "string", which Anthropic accepts.
_JSON_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


@dataclass(frozen=True)
class _Tool:
    """A registered tool: the callable plus its precomputed Anthropic schema."""

    func: Callable[..., str]
    schema: dict[str, Any]


# Name -> _Tool. Insertion order is preserved so schemas come out deterministically.
_REGISTRY: dict[str, _Tool] = {}


def _json_type_for(annotation: Any) -> str:
    """Best-effort mapping of a parameter's type hint to a JSON Schema type string."""
    # Direct type match (the common case: str, int, ...).
    if isinstance(annotation, type) and annotation in _JSON_TYPE_MAP:
        return _JSON_TYPE_MAP[annotation]
    # Unannotated or exotic hint -> treat as free-form string.
    return "string"


def _build_schema(func: Callable[..., str]) -> dict[str, Any]:
    """Introspect ``func`` to build an Anthropic tool schema.

    - name: the function's ``__name__``.
    - description: the function's docstring (required -- it tells the model when to
      use the tool).
    - input_schema: an object schema whose properties come from the parameters with
      their JSON types; a parameter is "required" iff it has no default value.
    """
    doc = inspect.getdoc(func)
    if not doc:
        raise ValueError(
            f"Tool {func.__name__!r} must have a docstring describing when to use it."
        )

    signature = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in signature.parameters.items():
        # Reject *args/**kwargs -- the model can't sensibly fill those, and the
        # schema can't represent them.
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            raise ValueError(
                f"Tool {func.__name__!r} parameter {param_name!r} uses *args/**kwargs, "
                "which is unsupported."
            )

        properties[param_name] = {"type": _json_type_for(param.annotation)}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "name": func.__name__,
        "description": doc,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


def register_tool(func: Callable[..., str]) -> Callable[..., str]:
    """Decorator: register ``func`` as a callable tool, building its schema from
    its signature and docstring. Returns the function unchanged so it stays
    directly callable in tests."""
    schema = _build_schema(func)
    name = schema["name"]
    if name in _REGISTRY:
        # Re-registration (e.g. module reload) overwrites -- log so it's visible.
        logger.warning("Tool %r is already registered; overwriting.", name)
    _REGISTRY[name] = _Tool(func=func, schema=schema)
    logger.debug("Registered tool %r with params %s", name, list(schema["input_schema"]["properties"]))
    return func


def get_tool_schemas() -> list[dict]:
    """Return the Anthropic tool schema for every registered tool."""
    return [tool.schema for tool in _REGISTRY.values()]


def get_gemini_tools() -> list:
    """Return the google-genai types.Tool list for every registered tool.

    Converts the internal Anthropic-style schema into Gemini
    ``types.FunctionDeclaration`` objects wrapped in a single ``types.Tool``.
    This keeps the registry format-agnostic; the same ``@register_tool``
    decorators and docstrings serve both Anthropic and Gemini backends.
    """
    from google.genai import types as gtypes

    declarations = []
    for tool in _REGISTRY.values():
        s = tool.schema
        input_schema = s["input_schema"]
        # Build per-parameter schema dicts (Gemini uses the same JSON Schema subset).
        properties: dict[str, Any] = {
            name: {"type": spec["type"]}
            for name, spec in input_schema["properties"].items()
        }
        declarations.append(
            gtypes.FunctionDeclaration(
                name=s["name"],
                description=s["description"],
                parameters=gtypes.Schema(
                    type="OBJECT",
                    properties={
                        name: gtypes.Schema(type=spec["type"].upper())
                        for name, spec in input_schema["properties"].items()
                    },
                    required=input_schema.get("required", []),
                ),
            )
        )
    return [gtypes.Tool(function_declarations=declarations)]


def call_tool(name: str, arguments: dict) -> str:
    """Execute the registered tool ``name`` with keyword ``arguments`` and return a
    short result string for the model.

    Any failure (unknown tool, bad arguments, exception inside the tool) is caught
    and returned as ``"Error: ..."`` so a single bad tool call never crashes the
    pipeline -- the model sees the error and can recover.
    """
    tool = _REGISTRY.get(name)
    if tool is None:
        logger.error("Model requested unknown tool %r", name)
        return f"Error: unknown tool {name!r}"

    try:
        result = tool.func(**arguments)
    except TypeError as exc:
        # Almost always wrong/missing arguments from the model.
        logger.exception("Bad arguments for tool %r: %s", name, arguments)
        return f"Error: invalid arguments for {name}: {exc}"
    except Exception as exc:  # noqa: BLE001 -- deliberately broad; report to model.
        logger.exception("Tool %r raised", name)
        return f"Error: {exc}"

    # Tools are typed to return str, but be defensive in case one returns None/etc.
    return result if isinstance(result, str) else str(result)


# --------------------------------------------------------------------------- #
# MVP tools
# --------------------------------------------------------------------------- #


@register_tool
def launch_application(target: str) -> str:
    """Launch a desktop application or run a command.

    Use for any 'open/launch/start X' request. The target should be the program's
    command as you would type it in a terminal.
    Example: 'kitty' or 'google-chrome-stable'
    """
    dispatch_exec(target)
    return f"Launched {target}."


@register_tool
def open_website(url: str) -> str:
    """Open a website or search query in the user's web browser (Google Chrome).

    Use this when the user asks to open a specific website, search for something,
    or look up videos. Provide a full valid URL (e.g. 'https://youtube.com/results?search_query=ai').
    """
    import shlex

    if not url.startswith("http"):
        url = "https://" + url

    # We use google-chrome-stable as per user preference
    dispatch_exec(f"google-chrome-stable {shlex.quote(url)}")
    return f"Opened website: {url}"


if __name__ == "__main__":
    # Manual smoke test: python -m execution.tools
    import json

    logging.basicConfig(level=logging.DEBUG)
    print(json.dumps(get_tool_schemas(), indent=2))
    print(call_tool("launch_application", {"target": "kitty"}))
    print(call_tool("does_not_exist", {}))
    print(call_tool("launch_application", {"wrong": "arg"}))
