#!/usr/bin/env python3
"""Replay a recorded run through the Rich UI — for the README demo GIF.

Self-contained (only needs `rich`): no API keys, no network, no LLM latency, so
it renders instantly and deterministically. Visually mirrors the real terminal
app. Usage: python scripts/demo.py [fixture-id]
"""
import json
import pathlib
import sys
import time

from rich.align import Align
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "tests" / "fixtures" / "runs"
DEFAULT_ID = "a-short-circle-time-lesson-teaching-the-days-of"

BANNER = r"""
  _  ___         _              _
 | |/ (_)_ _  __| |___ _ _  ___| |
 | ' <| | ' \/ _` / -_) '_|/ -_)_|
 |_|\_\_|_||_\__,_\___|_|(_)___(_)
   Lesson Planner  •  agentic + web-powered
"""

CANNED_SUMMARY = "Tightened the pacing and kept it playful, hands-on, and age-appropriate."

console = Console()


def type_prompt(text: str, delay: float = 0.04) -> None:
    sys.stdout.write("\033[1;36mteacher ›\033[0m ")
    sys.stdout.flush()
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


def plan_preview(plan: str, max_lines: int = 12) -> str:
    lines = plan.strip().splitlines()
    if len(lines) <= max_lines:
        return plan
    return "\n".join(lines[:max_lines]) + "\n\n_…full plan continues…_"


def render_review(scores: dict) -> None:
    labels = [
        ("age_appropriateness", "Age fit"),
        ("safety", "Safety"),
        ("engagement", "Engagement"),
        ("clarity", "Clarity"),
    ]
    rows = []
    for key, label in labels:
        s = int(scores.get(key, 0))
        color = "green" if s >= 4 else "yellow" if s == 3 else "red"
        rows.append(f"[{color}]{'★' * s}{'☆' * (5 - s)}[/{color}]  {label}")
    body = "\n".join(rows) + f"\n\n[dim]✎ {CANNED_SUMMARY}[/dim]"
    console.print(
        Panel(
            body,
            title="[bold magenta]👩‍🏫 Master-Teacher Review[/bold magenta]",
            border_style="magenta",
            padding=(1, 2),
        )
    )


def main() -> None:
    fid = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ID
    run = json.loads((RUNS / f"{fid}.json").read_text())

    sys.stdout.write("\033[2J\033[H")  # clear screen so the GIF opens on the banner
    sys.stdout.flush()
    time.sleep(0.4)
    console.print(Align.center(Text(BANNER, style="bold magenta")))
    console.print(Align.center(Text("model: gpt-5.4   •   type /help for commands", style="dim")))
    console.print()
    console.print(
        Panel(
            "Hi! I'm your kindergarten lesson-planning assistant. "
            "Tell me what you'd like to teach and I'll build a plan.",
            border_style="magenta",
        )
    )
    console.print()
    time.sleep(0.6)

    type_prompt(run["input"])
    console.print(Rule(style="dim"))
    time.sleep(0.3)

    for name in run.get("tools_used", []):
        if name == "web_search":
            console.print("[cyan]🔍 web search[/cyan] [dim]· age-appropriate books & songs[/dim]")
            time.sleep(0.6)
            break

    console.print(
        Panel(
            Markdown(plan_preview(run["plan"])),
            title="[bold green]👩‍🏫 Lesson Plan[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )
    time.sleep(0.5)
    console.print("[magenta]👩‍🏫 master-teacher review[/magenta]")
    time.sleep(0.4)
    render_review(run.get("review_scores", {}))
    time.sleep(0.8)


if __name__ == "__main__":
    main()
