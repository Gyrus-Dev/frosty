import sys
import os
import re
import asyncio
import logging
import threading
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from ._spinner import spinner as _spinner
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text
from prompt_toolkit.application import Application
from prompt_toolkit.widgets import TextArea, Frame as PTFrame
from prompt_toolkit.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PTStyle

_console = Console()


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
            title="[bold green]Objects Created[/bold green]",
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


def _build_context_message(message: str, chat_history: list | None = None) -> str:
    """Prepend recent conversation history to the current user message.

    *chat_history* is a list of dicts, each with ``role`` and ``content`` keys.
    """
    logger.debug("_build_context_message: building context with %d history entries", len(chat_history) if chat_history else 0)
    if not chat_history:
        logger.debug("_build_context_message: no chat history, returning message as-is")
        return message
    lines = ["Here is the recent conversation history for context:"]
    for msg in chat_history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    lines.append("")
    lines.append("Now, respond to the following new message:")
    lines.append(message)
    enriched = "\n".join(lines)
    logger.debug("_build_context_message: enriched message length=%d chars", len(enriched))
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

    _spinner.start(f"[{agent_instance.name}]")
    try:
        async for event in runner_instance.run_async(user_id=user_id, session_id=session_id, new_message=user_content):
            author = getattr(event, "author", "") or agent_instance.name
            if author == "user":
                author = agent_instance.name

            if event.actions.transfer_to_agent:
                _spinner.set_label(f"[{event.actions.transfer_to_agent}]")

            state = _get_event_state(event)
            if state:
                if os.environ.get("FROSTY_DEBUG", "").lower() == "true":
                    _spinner.println(f"### [{author}] State\n{state}")
                prev_count = len(queries_executed)
                _update_queries_from_state(state, queries_executed)
                if len(queries_executed) > prev_count:
                    total = query_offset + len(queries_executed)
                    _update_query_display(total)

            if os.environ.get("FROSTY_DEBUG", "").lower() == "true":
                calls = event.get_function_calls()
                responses = event.get_function_responses()
                if event.content and event.content.parts:
                    if event.content.parts[0].text:
                        _spinner.println(f"### [{author}] Payload\n{event.content.parts[0].text}")
                    if event.content.parts[0].thought:
                        _spinner.println(f"### [{author}] Thinking\n{event.content.parts[0].text}")
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
    banner.append("                              ╰─ by Gyrus Inc ─╯\n", style="dim")
    banner.append("                            www.thegyrus.com\n", style="dim link https://www.thegyrus.com")
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
        with _otel_tracer.start_as_current_span("frosty.user_request") as _span:
            _span.set_attribute("query.length", len(user_input))
            response, queries = await main(user_input, runner, sf_session, memory_bank_service, service, chat_history, query_offset=len(session_queries))
            _span.set_attribute("response.queries_count", len(queries))
        logger.debug("interactive: got response, new queries=%d total_queries=%d", len(queries), len(session_queries) + len(queries))
        _console.print()
        main_text, question = _extract_question(response)
        full_response = "\n\n".join(part for part in (main_text, question) if part)
        _console.print(Panel(Markdown(full_response), title="[bold blue]Frosty AI[/bold blue]", border_style="blue", padding=(1, 2)))
        if queries:
            _print_queries_panel(queries)
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
