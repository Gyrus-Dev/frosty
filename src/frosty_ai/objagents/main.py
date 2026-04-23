import sys
import os
import re
import asyncio
import getpass
import logging
import threading
import time
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text
from prompt_toolkit.application import Application
from prompt_toolkit.widgets import TextArea, Frame as PTFrame
from prompt_toolkit.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PTStyle
from openai import OpenAI
import anthropic
import google.generativeai as genai
import requests

_console = Console()

_LAUNCH_ENV_KEYS = [
    "APP_USER_NAME",
    "APP_USER_ID",
    "APP_NAME",
    "SNOWFLAKE_USER_NAME",
    "SNOWFLAKE_USER_PASSWORD",
    "SNOWFLAKE_ACCOUNT_IDENTIFIER",
    "SNOWFLAKE_AUTHENTICATOR",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "MODEL_PROVIDER",
    "GOOGLE_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_API_BASE",
    "OPENROUTER_API_KEY",
    "OLLAMA_API_BASE",
    "MODEL_PRIMARY",
    "MODEL_THINKING",
]


def _is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    stripped = value.strip()
    return stripped.startswith("<YOUR_") or stripped in {
        "YOUR_PRIMARY_MODEL",
        "your_password",
        "your_openai_api_key",
    }


def _set_env_value(name: str, value: str | None) -> None:
    if value is None:
        return
    value = value.strip()
    if value:
        os.environ[name] = value


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _quote_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _env_line(name: str, value: str) -> str:
    return f"{name}={_quote_env_value(value)}"


def _persist_launch_env() -> None:
    env_path = _project_root() / ".env"
    existing_lines = env_path.read_text().splitlines() if env_path.exists() else []
    values = {name: os.environ.get(name, "") for name in _LAUNCH_ENV_KEYS}
    remaining = set(values)
    updated_lines: list[str] = []

    for line in existing_lines:
        stripped = line.lstrip()
        uncommented = stripped[1:].lstrip() if stripped.startswith("#") else stripped
        match = re.match(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", uncommented)
        if match and match.group(1) in remaining:
            name = match.group(1)
            updated_lines.append(_env_line(name, values[name]))
            remaining.remove(name)
        else:
            updated_lines.append(line)

    if remaining:
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        updated_lines.append("# Launch configuration")
        for name in _LAUNCH_ENV_KEYS:
            if name in remaining:
                updated_lines.append(_env_line(name, values[name]))

    env_path.write_text("\n".join(updated_lines).rstrip() + "\n")
    _console.print(f"[dim]Saved launch configuration to {env_path}[/dim]")


def _prompt_env_value(name: str, label: str, *, default: str | None = None, secret: bool = False, required: bool = False) -> None:
    current = os.environ.get(name)
    fallback = default if _is_placeholder(current) else current

    # Mark required fields with red indicator
    required_marker = " [red](REQUIRED)[/red]" if required else ""
    label_with_marker = f"{label}{required_marker}"

    if secret:
        suffix = " (press Enter to keep current)" if fallback else ""
        value = getpass.getpass(f"{label_with_marker}{suffix}: ")
        if value:
            _set_env_value(name, value)
        elif fallback:
            os.environ[name] = fallback
        return

    value = Prompt.ask(label_with_marker, default=fallback or "")
    _set_env_value(name, value)


def _prompt_env_choice(name: str, label: str, choices: list[tuple[str, str]], *, default: str) -> str:
    current = os.environ.get(name)
    selected_value = default if _is_placeholder(current) else current
    valid_values = {value for value, _ in choices}
    if selected_value not in valid_values:
        selected_value = default

    default_index = next(
        index for index, (value, _description) in enumerate(choices, 1)
        if value == selected_value
    )

    _console.print(f"\n[bold]{label}[/bold]")
    for index, (value, description) in enumerate(choices, 1):
        marker = " [dim](current)[/dim]" if value == selected_value else ""
        value_label = value or "none"
        _console.print(f"  {index}. {value_label} [dim]- {description}[/dim]{marker}")

    answer = Prompt.ask(
        f"Choose {label.lower()}",
        choices=[str(index) for index in range(1, len(choices) + 1)],
        default=str(default_index),
    )
    value = choices[int(answer) - 1][0]
    if value:
        os.environ[name] = value
    else:
        os.environ.pop(name, None)
    return value


def _prompt_model_choice(name: str, label: str, models: list[str], *, default: str) -> None:
    unique_models = list(dict.fromkeys(model for model in models if model))
    if not unique_models:
        _prompt_env_value(name, label, default=default)
        return

    current = os.environ.get(name)
    selected_value = default if _is_placeholder(current) else current
    if selected_value not in unique_models:
        unique_models.insert(0, selected_value)

    _prompt_env_choice(
        name,
        label,
        [(model, "available model") for model in unique_models],
        default=selected_value,
    )


def _get_model_list(model_provider, api_key):
    available_models = []
    if model_provider == "openai":

        openai_base = os.environ.get("OPENAI_API_BASE")
        client = OpenAI(api_key=api_key, base_url=openai_base) if openai_base else OpenAI(api_key=api_key)
        # Fetch models
        models = client.models.list()
        # Print model IDs
        for model in models.data:
            model_id = model.id
            available_models.append(model_id if "/" in model_id else f"openai/{model_id}")

    if model_provider == "openrouter":
        # OpenRouter uses OpenAI-compatible API
        client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        models = client.models.list()
        for model in models.data:
            model_id = model.id
            # OpenRouter models are already prefixed (e.g., "openai/gpt-4", "anthropic/claude-3.5-sonnet")
            available_models.append(model_id)

    if model_provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        models = client.models.list()
        for m in models.data:
            model_id = m.id
            available_models.append(model_id if "/" in model_id else f"anthropic/{model_id}")
    
    if model_provider == "google":
        genai.configure(api_key=api_key)
        models = genai.list_models()
        for m in models:
            available_models.append(m.name.removeprefix("models/"))
    
    if model_provider == "ollama":
        ollama_base = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434").rstrip("/")
        response = requests.get(f"{ollama_base}/api/tags", timeout=10)
        response.raise_for_status()
        data = response.json()

        for model in data.get("models", []):
            available_models.append(f"ollama_chat/{model['name']}")

    return available_models


def _prompt_provider_models(provider: str, api_key: str | None, primary_default: str, thinking_default: str) -> None:
    try:
        models = _get_model_list(provider, api_key)
    except Exception as exc:
        _console.print(f"[yellow]Could not fetch {provider} models: {exc}[/yellow]")
        models = []

    _prompt_model_choice("MODEL_PRIMARY", "Primary model", models, default=primary_default)
    _prompt_model_choice(
        "MODEL_THINKING",
        "Thinking model",
        models,
        default=os.environ.get("MODEL_PRIMARY", thinking_default),
    )
            


def _configure_launch_env() -> None:
    """Collect launch-time environment values before agents import config.py."""
    if os.environ.get("FROSTY_CONFIG_ON_LAUNCH", "true").lower() in {"0", "false", "no"}:
        return
    if not sys.stdin.isatty():
        return

    required_names = [
        "SNOWFLAKE_USER_NAME",
        "SNOWFLAKE_ACCOUNT_IDENTIFIER",
        "APP_USER_NAME",
        "APP_USER_ID",
        "APP_NAME",
    ]
    has_missing_required = any(_is_placeholder(os.environ.get(name)) for name in required_names)
    configure = has_missing_required or Confirm.ask(
        "Configure Frosty environment for this launch?",
        default=False,
    )
    if not configure:
        return

    _console.print(Rule("[dim]Launch Configuration[/dim]", style="dim"))
    _console.print("[dim]Press Enter to keep an existing value. Values are saved to .env for future sessions.[/dim]")

    _prompt_env_value("APP_USER_NAME", "App display user name", default="Frosty User", required=True)
    _prompt_env_value("APP_USER_ID", "App user id", default=os.environ.get("APP_USER_NAME", "frosty-user"), required=True)
    _prompt_env_value("APP_NAME", "App name", default="frosty", required=True)

    _prompt_env_value("SNOWFLAKE_USER_NAME", "Snowflake user name", required=True)
    _prompt_env_value("SNOWFLAKE_USER_PASSWORD", "Snowflake password", secret=True, required=True)
    _prompt_env_value("SNOWFLAKE_ACCOUNT_IDENTIFIER", "Snowflake account identifier", required=True)
    _prompt_env_choice(
        "SNOWFLAKE_AUTHENTICATOR",
        "Snowflake authenticator",
        [
            ("", "standard username and password"),
            ("username_password_mfa", "Snowflake MFA with password"),
            ("externalbrowser", "browser-based SSO"),
        ],
        default="",
    )
    _prompt_env_value("SNOWFLAKE_ROLE", "Snowflake role (optional)", default="")
    _prompt_env_value("SNOWFLAKE_WAREHOUSE", "Snowflake warehouse (optional)", default="")
    _prompt_env_value("SNOWFLAKE_DATABASE", "Snowflake database (optional)", default="")

    current_provider = os.environ.get("MODEL_PROVIDER", "google").lower()
    if current_provider not in {"google", "openai", "anthropic", "ollama", "openrouter"}:
        current_provider = "google"
    provider = _prompt_env_choice(
        "MODEL_PROVIDER",
        "Model provider",
        [
            ("google", "Gemini models"),
            ("openai", "OpenAI or OpenAI-compatible endpoint"),
            ("openrouter", "OpenRouter (multi-provider)"),
            ("anthropic", "Claude models"),
            ("ollama", "local Ollama through LiteLLM"),
        ],
        default=current_provider,
    )
    os.environ["MODEL_PROVIDER"] = provider

    if provider == "google":
        _prompt_env_value("GOOGLE_API_KEY", "Google API key", secret=True)
        _prompt_provider_models(
            provider,
            os.environ.get("GOOGLE_API_KEY"),
            "gemini-2.5-flash",
            "gemini-2.5-pro-preview-03-25",
        )
    elif provider == "anthropic":
        _prompt_env_value("ANTHROPIC_API_KEY", "Anthropic API key", secret=True)
        _prompt_provider_models(
            provider,
            os.environ.get("ANTHROPIC_API_KEY"),
            "anthropic/claude-3-5-haiku-20241022",
            "anthropic/claude-3-5-sonnet-20241022",
        )
    elif provider == "ollama":
        _prompt_env_value("OLLAMA_API_BASE", "Ollama API base", default="http://localhost:11434")
        
        # Ask if user wants to use Gemma models through OpenAI Router
        use_gemma_openrouter = Confirm.ask(
            "\n[bold]Use Gemma models through OpenAI-compatible endpoint?[/bold]\n"
            "[dim]This routes Ollama's Gemma models through an OpenAI-compatible API.[/dim]",
            default=False,
        )
        
        if use_gemma_openrouter:
            # Hardcode the OpenAI Router configuration for Gemma
            os.environ["OPENAI_API_KEY"] = "sk-..."
            os.environ["OPENAI_API_BASE"] = "http://localhost:11434/v1"
            os.environ["MODEL_PRIMARY"] = "openai/gemma4:31b-cloud"
            _console.print("[dim]Configured for Gemma via OpenAI-compatible endpoint.[/dim]")
        else:
            _prompt_provider_models(
                provider,
                None,
                "ollama_chat/llama3.1",
                os.environ.get("MODEL_PRIMARY", "ollama_chat/llama3.1"),
            )
    elif provider == "openrouter":
        _prompt_env_value("OPENROUTER_API_KEY", "OpenRouter API key", secret=True)
        _prompt_provider_models(
            provider,
            os.environ.get("OPENROUTER_API_KEY"),
            "openrouter/google/gemma-2.5-flash",
            "openrouter/anthropic/claude-3.5-sonnet",
        )
    else:
        _prompt_env_value("OPENAI_API_KEY", "OpenAI API key", secret=True)
        _prompt_env_value("OPENAI_API_BASE", "OpenAI API base (optional)", default="")
        _prompt_provider_models(
            provider,
            os.environ.get("OPENAI_API_KEY"),
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
        )

    _persist_launch_env()


async def _get_boxed_input() -> str:
    """Display a cyan-framed input box and return the entered text."""
    result_holder: list[str] = [""]

    text_area = TextArea(
        height=1,
        multiline=False,
        wrap_lines=False,
        style="class:input-field",
    )

    frame = PTFrame(text_area, title="You", style="class:frame")
    layout = Layout(frame, focused_element=text_area)

    kb = KeyBindings()

    @kb.add("enter")
    def _submit(event):
        result_holder[0] = text_area.text
        event.app.exit()

    @kb.add("c-c")
    @kb.add("c-d")
    def _interrupt(event):
        raise KeyboardInterrupt()

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=PTStyle.from_dict({
            "frame.border": "ansicyan bold",
            "frame.label": "ansicyan bold",
            "input-field": "ansiwhite",
        }),
        full_screen=False,
        mouse_support=False,
    )

    await app.run_async()
    return result_holder[0].strip()

sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

_configure_launch_env()

from ._spinner import spinner as _spinner
_spinner.start("Starting Frosty AI...")
from .agent import ag_sf_manager
from google.adk.runners import Runner
from google.adk.memory import InMemoryMemoryService
from google.genai import types
from src.frosty_ai.adksession import SnowflakeADKSession as sfsession
from src.frosty_ai.adkstate import SnowflakeState as sfstate
from src.frosty_ai.adkrunner import ADKRunner
from src.frosty_ai.telemetry import tracer as _otel_tracer, shutdown as _otel_shutdown
_spinner.stop()

root_agent = ag_sf_manager
logger = logging.getLogger(__name__)

_ANSI_RESET     = "\033[0m"
_ANSI_BOLD      = "\033[1m"
_ANSI_BOLD_CYAN = "\033[1;36m"


def _format_inline(text: str) -> str:
    """Apply lightweight ANSI styling to text printed live during agent execution.

    Targets:
    - ✅ **Step N:** OBJECT_NAME — ...  → object name in bold cyan
    - **bold** spans anywhere          → ANSI bold (strips markdown asterisks)
    """
    # Step completion lines emitted by the manager agent
    text = re.sub(
        r'✅ \*\*Step (\d+):\*\* ([^\s—\n]+) —',
        lambda m: (
            f"✅ {_ANSI_BOLD}Step {m.group(1)}:{_ANSI_RESET} "
            f"{_ANSI_BOLD_CYAN}{m.group(2)}{_ANSI_RESET} —"
        ),
        text,
    )
    # General **bold** spans (strip markers, apply ANSI bold)
    text = re.sub(r'\*\*([^*\n]+)\*\*', rf'{_ANSI_BOLD}\1{_ANSI_RESET}', text)
    return text


def _summarize_debug_part(part) -> str:
    """Return a concise debug summary for non-text ADK event parts."""
    fields = []
    for attr in ("text", "thought", "code_execution_result", "executable_code", "inline_data", "file_data"):
        value = getattr(part, attr, None)
        if value:
            fields.append(f"{attr}={value!r}")
    if not fields:
        try:
            return repr(part)
        except Exception:
            return f"<{type(part).__name__}>"
    return ", ".join(fields)


def _extract_fenced_code_block(text: str, language: str = "python") -> str | None:
    """Extract the first fenced code block for the requested language."""
    match = re.search(rf"```{language}\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _update_query_display(total_count: int) -> None:
    """Update the terminal title bar and inline display with the current object count."""
    sys.stdout.write(f"\033]0;Frosty AI  |  Objects created: {total_count}\007")
    sys.stdout.flush()
    if total_count > 0:
        _spinner.println(f"\033[1;32m[● Objects created: {total_count}]\033[0m")


def _update_queries_from_state(state, queries_executed):
    logger.debug(" UPDATING QUERIES EXECUTED FROM STATE %s", state)
    if not state:
        return
    if isinstance(state, dict):
        value = state.get("app:QUERIES_EXECUTED")
        if value is None:
            value = state.get("user:QUERIES_EXECUTED")
        if isinstance(value, list):
            queries_executed[:] = value
        elif value:
            queries_executed.append(str(value))
    logger.debug(" UPDATED QUERIES EXECUTED LIST %s", queries_executed)


def _get_event_state(event):
    logger.debug("_get_event_state: extracting state from event %s", event)
    actions = getattr(event, "actions", None)
    if not actions:
        logger.debug("_get_event_state: no actions found on event")
        return None
    state = getattr(actions, "state", None)
    if state is not None:
        logger.debug("_get_event_state: found state %s", state)
        return state
    state_delta = getattr(actions, "state_delta", None)
    logger.debug("_get_event_state: found state_delta %s", state_delta)
    return state_delta


def _print_queries_panel(queries_executed: list[str]) -> None:
    """Render executed queries in a dedicated syntax-highlighted panel."""
    if not queries_executed:
        return
    combined = "\n\n".join(queries_executed)
    _console.print(
        Panel(
            Syntax(combined, "sql", theme="monokai", word_wrap=True),
            title="[bold green]Queries Executed[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )


def _extract_question(text: str) -> tuple[str, str]:
    """Split agent response into (main_text, question_text) on the ❓ marker."""
    marker = "❓"
    idx = text.find(marker)
    if idx == -1:
        return text, ""
    return text[:idx].rstrip(), text[idx:]


def _extract_options(main_text: str) -> tuple[str, str]:
    """Split main_text into (summary, options_section).

    The options section begins at 'Your infrastructure is ready',
    'Here are your next steps', or the first numbered-emoji option line.
    Returns (main_text, "") when no options section is detected.
    """
    patterns = [
        r"\n(?=Your infrastructure is ready)",
        r"\n(?=Here are your next steps)",
        # numbered emoji options: 1️⃣  2️⃣  etc. (digit + U+FE0F + U+20E3)
        "\n(?=[1-9]\uFE0F\u20E3)",
    ]
    earliest = len(main_text)
    for pattern in patterns:
        match = re.search(pattern, main_text)
        if match and match.start() < earliest:
            earliest = match.start()
    if earliest == len(main_text):
        return main_text, ""
    return main_text[:earliest].rstrip(), main_text[earliest:].lstrip()


def _format_elapsed_time(seconds: float) -> str:
    """Render a compact human-readable duration for one user interaction."""
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{seconds:.2f} s"
    minutes, remainder = divmod(seconds, 60)
    return f"{int(minutes)}m {remainder:.2f}s"


def _build_context_message(message: str, chat_history: list | None = None, max_chars: int = 800_000) -> str:
    """Prepend recent conversation history to the current user message.

    *chat_history* is a list of dicts, each with ``role`` and ``content`` keys.
    *max_chars* caps the total enriched message size (~4 chars per token, so
    800 000 chars ≈ 200 000 tokens, leaving headroom in a 262 144-token model).
    Oldest turns are dropped first when the budget is exceeded.
    """
    logger.debug("_build_context_message: building context with %d history entries", len(chat_history) if chat_history else 0)
    if not chat_history:
        logger.debug("_build_context_message: no chat history, returning message as-is")
        return message

    header = "Here is the recent conversation history for context:\n"
    footer = "\nNow, respond to the following new message:\n" + message
    # Budget available for history lines
    budget = max_chars - len(header) - len(footer)

    history_lines: list[str] = []
    # Walk history newest-first so we keep the most recent context
    for msg in reversed(chat_history):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        line = f"{role}: {content}"
        budget -= len(line) + 1  # +1 for newline
        if budget < 0:
            logger.warning(
                "_build_context_message: chat history truncated; dropped %d oldest entries",
                len(chat_history) - len(history_lines),
            )
            break
        history_lines.append(line)

    history_lines.reverse()
    enriched = header + "\n".join(history_lines) + footer
    logger.debug("_build_context_message: enriched message length=%d chars (history entries used=%d/%d)",
                 len(enriched), len(history_lines), len(chat_history))
    return enriched


async def call_agent_and_print(
    runner_instance: Runner,
    agent_instance,
    user_id,
    session_id: str,
    query_json: str,
    initial_state=None,
    query_offset: int = 0,
):
    """Sends a query to the specified agent/runner and prints results."""
    logger.debug(
        "call_agent_and_print: agent=%s user_id=%s session_id=%s query_len=%d initial_state=%s",
        agent_instance.name, user_id, session_id, len(query_json), initial_state,
    )
    user_content = types.Content(role='user', parts=[types.Part(text=query_json)])
    final_response_content = "No final response received."
    queries_executed = []
    _update_queries_from_state(initial_state, queries_executed)
    debug_enabled = os.environ.get("FROSTY_DEBUG", "").lower() == "true"
    last_author = None
    last_transfer_target = None
    last_generated_code = None

    _spinner.start(f"[{agent_instance.name}]")
    try:
        async for event in runner_instance.run_async(user_id=user_id, session_id=session_id, new_message=user_content):
            author = getattr(event, "author", "") or agent_instance.name
            if author == "user":
                author = agent_instance.name

            if event.actions.transfer_to_agent:
                transfer_target = event.actions.transfer_to_agent
                _spinner.set_label(f"[{transfer_target}]")
                if transfer_target != last_transfer_target:
                    _spinner.println(f"-> Running {transfer_target}")
                    last_transfer_target = transfer_target

            state = _get_event_state(event)
            if state:
                if debug_enabled:
                    _spinner.println(f"### [{author}] State\n{state}")
                prev_count = len(queries_executed)
                _update_queries_from_state(state, queries_executed)
                if len(queries_executed) > prev_count:
                    total = query_offset + len(queries_executed)
                    _update_query_display(total)

            if debug_enabled:
                if author != last_author:
                    _spinner.println(f"### [Agent] {author}")
                    last_author = author
                calls = event.get_function_calls()
                responses = event.get_function_responses()
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            _spinner.println(f"### [{author}] Payload\n{part.text}")
                            if author == "STREAMLIT_CODE_GENERATOR":
                                generated_code = _extract_fenced_code_block(part.text)
                                if generated_code and generated_code != last_generated_code:
                                    _spinner.println(f"### [{author}] Generated Code\n```python\n{generated_code}\n```")
                                    last_generated_code = generated_code
                        elif getattr(part, "thought", False):
                            _spinner.println(f"### [{author}] Thought\n{getattr(part, 'text', '')}")
                        else:
                            _spinner.println(f"### [{author}] Part\n{_summarize_debug_part(part)}")
                if calls:
                    _spinner.println(f"### [{author}] Tool Calls")
                    for call in calls:
                        _spinner.println(f"  Tool: {call.name}, Args: {call.args}")
                if responses:
                    _spinner.println(f"### [{author}] Tool Responses")
                    for response in responses:
                        _spinner.println(f"  {response.name} -> {response.response}")

            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if not part.thought and part.text:
                        final_response_content = part.text
                        break
            elif event.content and event.content.parts and author == agent_instance.name:
                for part in event.content.parts:
                    if not getattr(part, "thought", False) and part.text:
                        _spinner.println(_format_inline(part.text))
    finally:
        _spinner.stop()

    logger.debug(
        "call_agent_and_print: final response length=%d queries_executed=%d",
        len(final_response_content) if final_response_content else 0,
        len(queries_executed),
    )
    return final_response_content, queries_executed


async def main(message, runner, sf_session, memory_bank_service, service, chat_history: list | None = None, query_offset: int = 0):
    logger.debug("main: received message len=%d history_entries=%d", len(message), len(chat_history) if chat_history else 0)

    enriched_message = _build_context_message(message, chat_history)
    final_response, queries_executed = await call_agent_and_print(
        runner,
        root_agent,
        sf_session.user_id,
        sf_session.id,
        enriched_message,
        initial_state=sf_session.state,
        query_offset=query_offset,
    )
    try:
        logger.debug("main: fetching session for memory bank storage")
        session = await service.get_session(
            app_name=sf_session.app_name,
            user_id=sf_session.user_id,
            session_id=sf_session.id,
        )
        if session:
            logger.debug("main: adding session to memory bank")
            await memory_bank_service.add_session_to_memory(session)
        else:
            logger.debug("main: session not found, skipping memory bank")
    except Exception as exc:
        logger.warning("Failed to add session to memory bank: %s", exc)
    logger.debug("main: returning response len=%d queries=%d", len(final_response) if final_response else 0, len(queries_executed))
    return final_response, queries_executed


def _write_session_queries(all_queries: list[str]) -> None:
    """Write all queries from the session to a .sql file under queries/<session_timestamp>.sql."""
    logger.debug("_write_session_queries: %d queries to write", len(all_queries))
    if not all_queries:
        logger.debug("_write_session_queries: no queries, skipping file write")
        return
    root_dir = os.path.dirname(os.path.abspath(__file__))
    # Walk up to the project root (4 levels up from objagents/)
    for _ in range(4):
        root_dir = os.path.dirname(root_dir)
    queries_dir = os.path.join(root_dir, "queries")
    os.makedirs(queries_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(queries_dir, f"session_{timestamp}.sql")
    logger.debug("_write_session_queries: writing to %s", filepath)
    with open(filepath, "w") as f:
        f.write(f"-- Frosty AI session queries — {timestamp}\n\n")
        for i, query in enumerate(all_queries, 1):
            f.write(f"-- Query {i}\n{query};\n\n")
    logger.info("Session queries written to: %s", filepath)
    _console.print(f"\n[dim]Session queries written to: {filepath}[/dim]")


async def interactive():
    logger.debug("interactive: starting REPL session")
    chat_history = []
    session_queries: list[str] = []
    banner = Text(justify="center")
    banner.append("\n")
    banner.append("███████╗██████╗  ██████╗ ███████╗████████╗██╗   ██╗\n", style="bold cyan")
    banner.append("██╔════╝██╔══██╗██╔═══██╗██╔════╝╚══██╔══╝╚██╗ ██╔╝\n", style="bold cyan")
    banner.append("█████╗  ██████╔╝██║   ██║███████╗   ██║    ╚████╔╝ \n", style="bold cyan")
    banner.append("██╔══╝  ██╔══██╗██║   ██║╚════██║   ██║     ╚██╔╝  \n", style="bold cyan")
    banner.append("██║     ██║  ██║╚██████╔╝███████║   ██║      ██║   \n", style="bold cyan")
    banner.append("╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝      ╚═╝  \n", style="bold cyan")
    banner.append("V2026.04.23", style="bold yellow")
    banner.append("                     ╰─ by ", style="dim")
    banner.append("Gyrus Inc", style="bold yellow")
    banner.append(" ─╯\n", style="dim")
    banner.append("                            ", style="dim")
    banner.append("www.thegyrus.com", style="bold yellow link https://www.thegyrus.com")
    banner.append("\n")
    _console.print(Panel(banner, subtitle="[dim]Your Snowflake AI Assistant  ·  type [bold]exit[/bold] to quit[/dim]", border_style="cyan"))

    # Create the session and runner once — shared across all turns so that
    # app:TASKS_PERFORMED and other state persists throughout the conversation.
    _console.print(Rule("[dim]Initializing[/dim]", style="dim"))
    sf_state = sfstate(
        user_name=os.environ["APP_USER_NAME"],
        snowflake_user_name=os.environ["SNOWFLAKE_USER_NAME"],
        user_password=os.environ.get("SNOWFLAKE_USER_PASSWORD"),
        account_identifier=os.environ["SNOWFLAKE_ACCOUNT_IDENTIFIER"],
        authenticator=os.environ.get("SNOWFLAKE_AUTHENTICATOR"),
        role=os.environ.get("SNOWFLAKE_ROLE"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE"),
        database=os.environ.get("SNOWFLAKE_DATABASE"),
    )
    sf_state.init_snowflake_state()

    sf_session = sfsession(user_id=os.environ["APP_USER_ID"], app_name=os.environ["APP_NAME"], state=sf_state)
    logger.debug("interactive: session created id=%s", sf_session.id)
    _console.print(f"[dim]Session:[/dim] [bold]{sf_session.id}[/bold]")

    _adk_session, service = await sf_session.create_session()

    memory_bank_service = InMemoryMemoryService()
    runner = ADKRunner(
        agent=root_agent,
        app_name=sf_session.app_name,
        session_service=service,
        memory_service=memory_bank_service,
    )
    runner = runner.get_runner()

    # Pre-warm all lazy agent modules in the background using BFS with full
    # parallelism at every level — all nodes at each depth load concurrently
    # before moving to the next level, maximising thread utilisation.
    def _pre_warm():
        import time as _time
        from .lazy_agent_tool import LazyAgentTool
        from concurrent.futures import ThreadPoolExecutor

        def resolve_one(tool):
            try:
                tool.warm_up()
            except Exception:
                pass
            return tool.get_sub_tools()

        current_level = [
            t for t in (getattr(root_agent, "tools", None) or [])
            if isinstance(t, LazyAgentTool)
        ]
        while current_level:
            with ThreadPoolExecutor(max_workers=len(current_level)) as executor:
                child_lists = list(executor.map(resolve_one, current_level))
            current_level = [t for children in child_lists for t in children]

    _console.print("[bold cyan]⠋  Warming up agents in background...[/bold cyan]")
    threading.Thread(target=_pre_warm, daemon=True, name="agent-prewarmer").start()

    _console.print(Rule(style="dim"))
    
    # Star solicitation message - EXTRA PROMINENT WITH BOX
    _console.print()
    _console.print("[bold yellow]╔═══════════════════════════════════════════════════════════╗[/bold yellow]")
    _console.print("[bold yellow]║[/bold yellow]  [bold white]⭐  Support Frosty's Development!  ⭐[/bold white] [bold yellow]║[/bold yellow]")
    _console.print("[bold yellow]║[/bold yellow]  [dim]Maintaining an open-source project takes hard work.[/dim]  [bold yellow]║[/bold yellow]")
    _console.print("[bold yellow]║[/bold yellow]  [dim]Your stars keep us motivated and help others find us![/dim]  [bold yellow]║[/bold yellow]")
    _console.print("[bold yellow]║[/bold yellow]  [bold cyan]👉 https://github.com/Gyrus-Dev/frosty[/bold cyan] [bold yellow]║[/bold yellow]")
    _console.print("[bold yellow]╚═══════════════════════════════════════════════════════════╝[/bold yellow]")
    _console.print()

    _intro = (
        "👋  **Hi! I'm Frosty** — your Snowflake AI assistant.\n\n"
        "Here's what I can do for you:\n\n"
        "- 🏗  **Build from scratch** — describe what you need and I'll design and create "
        "the full Snowflake infrastructure: databases, schemas, tables, pipelines, roles, "
        "policies, and more.\n"
        "- 🔍  **Understand your existing setup** — I can inspect your live Snowflake "
        "environment, map your architecture, and answer questions about what's already there.\n\n"
        "**Getting started tip:**\n"
        "If you'd like me to inspect your existing infrastructure, I recommend starting with "
        "**one or two specific databases** rather than your entire account — for example:\n"
        "> *\"Inspect MY_DATABASE and give me an overview of its schemas and tables.\"*\n\n"
        "⚠️  **Full account-wide inspection** (all databases, schemas, roles, warehouses, "
        "pipelines) is a heavy operation that may be slow or hit memory limits on smaller "
        "machines. Only request a full inspection if you have sufficient resources available.\n\n"
        "What would you like to build or explore today?"
    )
    _console.print(Panel(
        Markdown(_intro),
        title="[bold cyan]Frosty AI[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    _update_query_display(0)
    while True:
        try:
            _console.print()
            user_input = await _get_boxed_input()
        except (EOFError, KeyboardInterrupt):
            logger.debug("interactive: session interrupted by user")
            _console.print("\n[bold cyan]Goodbye![/bold cyan]")
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            logger.debug("interactive: user requested exit")
            _console.print("[bold cyan]Goodbye![/bold cyan]")
            break
        logger.debug("interactive: dispatching message to main, history_len=%d", len(chat_history))
        interaction_started = time.perf_counter()
        with _otel_tracer.start_as_current_span("frosty.user_request") as _span:
            _span.set_attribute("query.length", len(user_input))
            response, queries = await main(user_input, runner, sf_session, memory_bank_service, service, chat_history, query_offset=len(session_queries))
            _span.set_attribute("response.queries_count", len(queries))
            _span.set_attribute("interaction.duration_ms", round((time.perf_counter() - interaction_started) * 1000, 2))
        interaction_elapsed = time.perf_counter() - interaction_started
        logger.debug("interactive: got response, new queries=%d total_queries=%d", len(queries), len(session_queries) + len(queries))
        _console.print()
        main_text, question = _extract_question(response)
        if queries:
            _print_queries_panel(queries)
        _console.print(Panel(Markdown(main_text), title="[bold blue]Frosty AI[/bold blue]", border_style="blue", padding=(1, 2)))
        if question:
            _console.print(Panel(Markdown(question), title="[bold yellow]❓ Question for you[/bold yellow]", border_style="yellow", padding=(1, 2)))
        _console.print(f"[dim]Interaction time: {_format_elapsed_time(interaction_elapsed)}[/dim]")
        chat_history.append({"role": "user", "content": user_input})
        chat_history.append({"role": "assistant", "content": response})
        session_queries.extend(queries)
        _update_query_display(len(session_queries))
    logger.debug("interactive: session ended, total queries=%d", len(session_queries))
    _write_session_queries(session_queries)
    _otel_shutdown()


# Entry point
if __name__ == '__main__':
    asyncio.run(interactive())
