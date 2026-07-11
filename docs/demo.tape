# VHS tape — LIVE capture of the real app (real LLM calls, real web search).
# Needs .env with OPENAI_API_KEY + TAVILY_API_KEY. Regenerate: task demo
# The raw capture runs in real time (~35s of actual work); trim trailing static
# afterwards, e.g.:  ffmpeg -y -t 36 -i docs/demo.gif -vf fps=12 docs/demo.gif
Output docs/demo.gif

Set Shell "bash"
Set FontSize 15
Set Width 1100
Set Height 900
Set Padding 18
Set Theme "Dracula"
Set Framerate 12

Hide
Type "clear && TRACING_ENABLED=false .venv/bin/python main.py"
Enter
Sleep 5s
Show
Type "A 15-minute lesson on the days of the week, and find a real picture book"
Sleep 800ms
Enter
Sleep 80s
