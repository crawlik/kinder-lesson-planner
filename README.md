# 🍎 Kinder Lesson Planner

An **agentic LLM assistant** that generates kindergarten lesson plans from a
teacher's plain-English request. It runs as a **simple, colorful terminal app**,
uses **web search** to ground its ideas in real books/songs/activities, and can
**save plans to Markdown** files.

Built with a LangGraph ReAct agent + OpenAI and a terminal-first UX.

## ✨ Features

- **🧑‍🏫 LLM-as-a-judge review loop** — after drafting, a second LLM acts as a
  judge playing the role of a senior master teacher: it scores every plan on a
  rubric (age-fit, **safety**, engagement, clarity), flags concrete issues, and
  auto-refines the plan before you see it. A small *generate → critique → refine*
  agentic loop that reliably catches things like choking hazards. Toggle with
  `/review on|off`.
- **Conversational** — multi-turn memory, so you can refine a plan ("make it
  shorter", "add a movement break") without repeating yourself.
- **Web-powered** — a `web_search` tool (Tavily) pulls in real picture books,
  songs, and craft ideas instead of inventing them.
- **Saves your work** — a `save_lesson_plan` tool (and a `/save` command) write
  plans to `lesson_plans/*.md`.
- **Colorful TUI** — [Rich](https://github.com/Textualize/rich)-rendered
  Markdown, live tool activity, and spinners.
- **Robust** — env validation, graceful error panels, and safe model/temperature
  handling (auto-adapts for `gpt-5*`/`o*` models).

## 🧱 Project structure

```
kinder-lesson-planner/
├── main.py                  # entry point
├── src/
│   ├── agent.py             # LangGraph ReAct agent (OpenAI + tools + memory)
│   ├── cli.py               # colorful Rich terminal app (REPL)
│   └── tools/
│       ├── websearch.py     # Tavily web search tool
│       └── lesson_file.py   # save-lesson-plan tool + helper
├── pyproject.toml
├── .env.example
└── README.md
```

## 🚀 Setup

Requires Python 3.10+ and [uv](https://github.com/astral-sh/uv) (or plain pip).

```bash
# 1. Install dependencies
uv sync                         # or: pip install -e .

# 2. Configure keys
cp .env.example .env            # then edit .env
```

Fill in `.env`:

```env
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
OPENAI_MODEL=gpt-4.1            # optional; a frontier model is recommended
```

Get keys: [OpenAI](https://platform.openai.com/api-keys) ·
[Tavily](https://tavily.com/) (free tier is plenty for a demo).

## 🕹️ Usage

```bash
uv run python main.py           # or: uv run kinder-lesson-planner
```

Then just talk to it:

```
teacher › A 30-minute lesson on the life cycle of a butterfly
teacher › make it shorter and add a song
teacher › /save Butterfly Life Cycle
```

### Commands

| Command | What it does |
|---|---|
| `/help` | Show help and example prompts |
| `/save [title]` | Save the last plan to `lesson_plans/` |
| `/review [on\|off]` | Toggle the master-teacher review loop |
| `/new` | Start a fresh conversation (clears memory) |
| `/quit` | Exit |

## 🧠 How it works

1. **ReAct agent (LangGraph):** a cyclic `agent → tools → agent` graph. The model
   reasons, decides whether to call a tool, tools run, results feed back, and it
   loops until it returns a final answer.
2. **Tools:**
   - `web_search` — Tavily search for real, current classroom resources.
   - `save_lesson_plan` — writes a Markdown file (never overwrites).
3. **Master-teacher review loop:** once a plan is drafted, a separate
   `LessonReviewer` LLM (structured output) scores it on a rubric, lists issues,
   and returns an improved version — a reflection loop that raises quality and
   catches safety problems. See `src/reviewer.py`.
4. **Memory:** a `MemorySaver` checkpointer keyed by `thread_id` makes it a true
   chatbot — refinements build on the previous turn.
5. **Prompt engineering:** a detailed system prompt encodes developmental
   appropriateness (ages 4–6), a consistent 10-section plan structure, safety
   awareness, and a bias toward searching for real resources over inventing them.

```
        ┌──────────────┐
        │  Teacher     │  (colorful terminal REPL)
        └──────┬───────┘
               │
        ┌──────▼───────┐
        │ ReAct Agent  │  LangGraph + OpenAI
        │  (+ memory)  │
        └──────┬───────┘
        ┌──────┴───────┐
   ┌────▼────┐   ┌─────▼──────┐
   │ web_    │   │ save_      │
   │ search  │   │ lesson_plan│
   └─────────┘   └────────────┘
               │ draft
        ┌──────▼───────────┐
        │ 🧑‍🏫 Master-Teacher │  rubric scores + auto-refine
        │  Reviewer         │  (src/reviewer.py)
        └──────┬───────────┘
               ▼ polished plan
```

## 🔧 Design notes & trade-offs

- **Model choice:** defaults to a frontier model (`gpt-4.1`) for reliable tool
  use. The agent auto-omits `temperature` for `gpt-5*`/`o*` models, which only
  accept the default — so switching models won't crash the demo.
- **Terminal over web:** a TUI keeps the demo dependency-light and fast to run,
  and puts the agent's reasoning/tool activity front and center.
- **In-memory conversation:** memory is per-process (not persisted across runs) —
  intentional simplicity for a prototype.

- **Review loop trade-off:** the reviewer adds a second LLM call per plan
  (~2× latency/cost on planning turns). It's best-effort — if it fails, the
  draft is kept — and can be switched off with `/review off` or
  `REVIEW_ENABLED=false`. Note the *draft* (not the revised plan) is what's kept
  in conversation memory, so follow-up edits build on the pre-review version.

### If I had one more day
- Feed the revised plan back into conversation memory so edits build on it.
- Persist conversations and a lesson-plan library across sessions.
- Add a curriculum-standards lookup tool (e.g. state early-learning standards).
- Printable/PDF export and read-aloud (TTS) of songs and stories.
- Add evals over a set of teacher prompts (incl. the reviewer's rubric scores).

## 📄 License

MIT — see [LICENSE](LICENSE).
