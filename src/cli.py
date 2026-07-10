"""Colorful terminal app for the kindergarten lesson planner.

A friendly REPL: the teacher chats with the agent, watches it search the web
live, sees plans rendered as pretty Markdown, and can save them to disk.
"""
import logging
import os
import sys

from dotenv import load_dotenv
from rich.align import Align
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.text import Text

from src.agent import create_agent, resolve_model
from src.tools.lesson_file import save_lesson_plan_to_file

# Keep library logging out of the pretty UI unless the user opts in.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

console = Console()

REQUIRED_VARS = ["OPENAI_API_KEY", "TAVILY_API_KEY"]

BANNER = r"""
  _  ___         _              _
 | |/ (_)_ _  __| |___ _ _  ___| |
 | ' <| | ' \/ _` / -_) '_|/ -_)_|
 |_|\_\_|_||_\__,_\___|_|(_)___(_)
   Lesson Planner  •  agentic + web-powered
"""

HELP_TEXT = """[bold]Commands[/bold]
  [cyan]/help[/cyan]            Show this help
  [cyan]/save[/cyan] [dim][title][/dim]   Save the last plan to a Markdown file
  [cyan]/new[/cyan]             Start a fresh conversation (clears memory)
  [cyan]/quit[/cyan], [cyan]/exit[/cyan]  Leave the app

[bold]Try asking[/bold]
  • "A 30-minute lesson on the life cycle of a butterfly"
  • "Something for teaching sharing and kindness, with a picture book"
  • "A counting activity using autumn leaves"
  • Then refine: "make it shorter" or "add a movement break"
"""

TOOL_LABELS = {
    "web_search": ("🔍", "cyan", "Searching the web"),
    "save_lesson_plan": ("💾", "green", "Saving lesson plan"),
}


def _fatal(message: str) -> None:
    console.print(Panel(message, title="[bold red]Error[/bold red]", border_style="red"))
    sys.exit(1)


def _print_banner(model: str) -> None:
    console.print(Align.center(Text(BANNER, style="bold magenta")))
    console.print(
        Align.center(
            Text(f"model: {model}   •   type /help for commands", style="dim")
        )
    )
    console.print()


def _render_plan(markdown_text: str) -> None:
    console.print(
        Panel(
            Markdown(markdown_text or "_(no content)_"),
            title="[bold green]👩‍🏫 Lesson Plan[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )


def _run_turn(agent, message: str, thread_id: str) -> str:
    """Drive one agent turn with a live status, return the final text."""
    final = ""
    with console.status("[bold yellow]Thinking…[/bold yellow]", spinner="dots") as status:
        for event in agent.stream(message, thread_id):
            etype = event["type"]
            if etype == "tool_call":
                icon, color, label = TOOL_LABELS.get(
                    event["name"], ("🛠️", "yellow", event["name"])
                )
                detail = event["args"].get("query") or event["args"].get("title") or ""
                status.update(f"[bold {color}]{icon} {label}…[/bold {color}] [dim]{detail}[/dim]")
                line = f"[{color}]{icon} {label}[/{color}]"
                if detail:
                    line += f" [dim]· {detail}[/dim]"
                console.print(line)
            elif etype == "final":
                final = event["content"]
            elif etype == "error":
                console.print(
                    Panel(
                        str(event["error"]),
                        title="[bold red]Agent error[/bold red]",
                        border_style="red",
                    )
                )
                return ""
    return final


def _handle_save(arg: str, last_plan: str) -> None:
    if not last_plan:
        console.print("[yellow]Nothing to save yet — ask for a lesson plan first.[/yellow]")
        return
    title = arg.strip() or last_plan.strip().lstrip("#").strip().splitlines()[0][:60] or "lesson-plan"
    try:
        path = save_lesson_plan_to_file(title, last_plan)
        console.print(f"[green]💾 Saved to[/green] [bold]{path}[/bold]")
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Could not save: {e}[/red]")


def main() -> None:
    load_dotenv()

    # Optional LangSmith tracing, mirroring the reference project.
    if os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true":
        console.print("[dim]LangSmith tracing enabled[/dim]")

    missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
    if missing:
        _fatal(
            "Missing required environment variables: "
            + ", ".join(missing)
            + "\n\nCopy .env.example to .env and fill in your keys."
        )

    try:
        agent = create_agent(
            openai_api_key=os.environ["OPENAI_API_KEY"],
            tavily_api_key=os.environ["TAVILY_API_KEY"],
        )
    except Exception as e:  # noqa: BLE001
        _fatal(f"Failed to initialize the agent:\n{e}")

    _print_banner(resolve_model())
    console.print(
        Panel(
            "Hi! I'm your kindergarten lesson-planning assistant. "
            "Tell me what you'd like to teach and I'll build a plan — "
            "I can search the web for fresh ideas and save plans for you.",
            border_style="magenta",
        )
    )

    thread_id = "session-1"
    turn = 0
    last_plan = ""

    while True:
        console.print()
        try:
            user_input = Prompt.ask("[bold cyan]teacher[/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[magenta]Goodbye! Happy teaching. 👋[/magenta]")
            break

        if not user_input:
            continue

        # --- Commands ---
        if user_input.lower() in ("/quit", "/exit", "/q"):
            console.print("[magenta]Goodbye! Happy teaching. 👋[/magenta]")
            break
        if user_input.lower() == "/help":
            console.print(Panel(HELP_TEXT, border_style="blue", title="Help"))
            continue
        if user_input.lower() == "/new":
            turn += 1
            thread_id = f"session-{turn + 1}"
            last_plan = ""
            console.print("[dim]Started a fresh conversation.[/dim]")
            continue
        if user_input.lower().startswith("/save"):
            _handle_save(user_input[len("/save"):], last_plan)
            continue
        if user_input.startswith("/"):
            console.print(f"[yellow]Unknown command: {user_input}. Try /help.[/yellow]")
            continue

        # --- Normal turn ---
        console.print(Rule(style="dim"))
        response = _run_turn(agent, user_input, thread_id)
        if response:
            last_plan = response
            _render_plan(response)


if __name__ == "__main__":
    main()
