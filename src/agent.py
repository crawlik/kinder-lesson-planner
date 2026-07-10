"""Kindergarten lesson-plan agent built on LangGraph + OpenAI.

A ReAct-style agent: the model reasons, optionally calls tools (web search,
save-to-file), and loops until it produces a final answer. A checkpointer gives
it multi-turn memory so a teacher can refine a plan conversationally.
"""
import logging
import os
import traceback
from typing import Annotated, Any, Dict, Iterator, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.tools.lesson_file import create_lesson_file_tool
from src.tools.websearch import create_web_search_tool

logger = logging.getLogger(__name__)

# Frontier model by default. gpt-5* models only accept the default temperature,
# so we omit the temperature argument for those to avoid an API error.
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1")

SYSTEM_PROMPT = """You are an expert early-childhood educator who designs \
warm, playful, and developmentally appropriate lesson plans for KINDERGARTEN \
children (roughly ages 4-6).

Your job is to turn a teacher's request into a concrete, classroom-ready lesson \
plan. Ground your ideas in reality: when the teacher asks for a topic, current \
themes, specific books, songs, or craft ideas, use the `web_search` tool to find \
real, verifiable resources rather than inventing them. Prefer well-known picture \
books and songs, and cite the source when a specific resource comes from search.

Every lesson plan you produce should include, formatted as clean Markdown:
1. **Title & Theme** — a fun, clear title.
2. **Age Group & Duration** — assume kindergarten unless told otherwise.
3. **Learning Objectives** — 2-4 concrete, observable goals.
4. **Materials** — a simple, low-cost, easy-to-source list.
5. **Warm-Up / Circle Time** — a short hook (song, story, question).
6. **Main Activity** — step-by-step, with clear teacher instructions.
7. **Wrap-Up** — reflection or sharing.
8. **Assessment** — how the teacher can tell children met the objectives (observation-based).
9. **Differentiation** — one adaptation to make it easier and one to extend it.
10. **Safety / Notes** — allergy, choking, or mobility considerations when relevant.

Guiding principles:
- Keep language and activities age-appropriate: short attention spans, hands-on, \
play-based, lots of movement and repetition.
- Be specific and actionable — a substitute teacher should be able to run it.
- Be safety-conscious (small parts, scissors, food allergies).
- Be inclusive and culturally sensitive.
- Ask a brief clarifying question ONLY if the request is too vague to plan well; \
otherwise make sensible assumptions and state them.

When the teacher is happy with a plan and wants to keep it, use the \
`save_lesson_plan` tool to save it. Be friendly, encouraging, and concise in your \
conversational replies."""


class AgentState(TypedDict):
    """Graph state — a running list of messages."""

    messages: Annotated[Sequence[BaseMessage], add_messages]


class LessonPlannerAgent:
    """A conversational, tool-using kindergarten lesson-plan agent."""

    def __init__(
        self,
        openai_api_key: str,
        tavily_api_key: str,
        model_name: str = DEFAULT_MODEL,
        temperature: float = 0.7,
    ):
        logger.info("Initializing LessonPlannerAgent with model=%s", model_name)

        self.tools = [
            create_web_search_tool(tavily_api_key),
            create_lesson_file_tool(),
        ]

        # gpt-5* models reject a custom temperature — only pass it when supported.
        llm_kwargs: Dict[str, Any] = {
            "model": model_name,
            "openai_api_key": openai_api_key,
        }
        if not model_name.startswith("gpt-5") and not model_name.startswith("o"):
            llm_kwargs["temperature"] = temperature

        self.llm = ChatOpenAI(**llm_kwargs).bind_tools(self.tools)
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ToolNode(self.tools))
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent", self._should_continue, {"continue": "tools", "end": END}
        )
        workflow.add_edge("tools", "agent")
        # MemorySaver gives multi-turn memory keyed by thread_id.
        return workflow.compile(checkpointer=MemorySaver())

    def _call_model(self, state: AgentState) -> Dict[str, Any]:
        # The system prompt is prepended on every call (not persisted to state),
        # so it survives across turns even with a checkpointer.
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
        try:
            response = self.llm.invoke(messages)
            return {"messages": [response]}
        except Exception as e:  # noqa: BLE001
            logger.error("Error calling model: %s", e)
            logger.error(traceback.format_exc())
            raise

    @staticmethod
    def _should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "continue"
        return "end"

    def stream(self, message: str, thread_id: str = "default") -> Iterator[Dict[str, Any]]:
        """Stream a turn as a series of events.

        Yields dicts of:
          {"type": "tool_call", "name": str, "args": dict}
          {"type": "final", "content": str}
          {"type": "error", "error": str}
        """
        config = {"configurable": {"thread_id": thread_id}}
        final_content = ""
        try:
            for update in self.graph.stream(
                {"messages": [HumanMessage(content=message)]},
                config,
                stream_mode="updates",
            ):
                for node, data in update.items():
                    for msg in data.get("messages", []) or []:
                        if node == "agent" and getattr(msg, "tool_calls", None):
                            for call in msg.tool_calls:
                                yield {
                                    "type": "tool_call",
                                    "name": call.get("name", "tool"),
                                    "args": call.get("args", {}) or {},
                                }
                        elif node == "agent" and isinstance(msg, AIMessage) and msg.content:
                            final_content = msg.content
            yield {"type": "final", "content": final_content}
        except Exception as e:  # noqa: BLE001
            logger.error("Error during stream: %s", e)
            logger.error(traceback.format_exc())
            yield {"type": "error", "error": str(e)}

    def chat(self, message: str, thread_id: str = "default") -> Dict[str, Any]:
        """Non-streaming convenience wrapper. Returns {success, response|error}."""
        final = ""
        for event in self.stream(message, thread_id):
            if event["type"] == "final":
                final = event["content"]
            elif event["type"] == "error":
                return {"success": False, "error": event["error"]}
        return {"success": True, "response": final}


def create_agent(
    openai_api_key: str, tavily_api_key: str, model_name: str = DEFAULT_MODEL
) -> LessonPlannerAgent:
    """Create and return a lesson-planner agent."""
    return LessonPlannerAgent(
        openai_api_key=openai_api_key,
        tavily_api_key=tavily_api_key,
        model_name=model_name,
    )
