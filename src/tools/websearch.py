"""Web search tool using the Tavily API.

Gives the agent fresh, real-world ideas: current seasonal themes, popular
picture books, songs, craft ideas, and age-appropriate activities that a
static model may not know about.
"""
import json
from typing import Type

import requests
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class WebSearchInput(BaseModel):
    """Input for a web search."""

    query: str = Field(
        description=(
            "A focused search query, e.g. 'best picture books about kindness for "
            "preschoolers' or 'simple spring craft ideas for kindergarten'."
        )
    )


class WebSearchTool(BaseTool):
    """Search the web for classroom-ready ideas, books, songs, and activities."""

    name: str = "web_search"
    description: str = (
        "Search the web for current, real-world teaching resources: picture books, "
        "songs, rhymes, craft ideas, seasonal themes, and developmentally appropriate "
        "activities for young children. Use this to ground lesson plans in concrete, "
        "up-to-date, verifiable ideas instead of inventing them."
    )
    args_schema: Type[BaseModel] = WebSearchInput
    api_key: str
    max_results: int = 5

    def _run(self, query: str) -> str:
        """Execute the search."""
        try:
            response = requests.post(
                TAVILY_SEARCH_URL,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": self.max_results,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            results = [
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0),
                }
                for result in data.get("results", [])
            ]

            return json.dumps(
                {"success": True, "query": query, "results": results}, indent=2
            )
        except Exception as e:  # noqa: BLE001 - surface a clean message to the agent
            return json.dumps({"success": False, "error": str(e)})

    async def _arun(self, query: str) -> str:
        """Async version (delegates to sync — requests is blocking)."""
        return self._run(query)


def create_web_search_tool(api_key: str) -> WebSearchTool:
    """Create a web search tool bound to the given API key."""
    return WebSearchTool(api_key=api_key)
