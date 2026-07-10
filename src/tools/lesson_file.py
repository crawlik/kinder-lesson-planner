"""Tool + helper for saving a finished lesson plan to a Markdown file."""
import json
import os
import re
from typing import Optional, Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

DEFAULT_DIR = os.environ.get("LESSON_PLANS_DIR", "lesson_plans")


def _slugify(text: str) -> str:
    """Turn a title into a safe, readable filename stem."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60].strip("-") or "lesson-plan"


def save_lesson_plan_to_file(
    title: str, content: str, directory: Optional[str] = None
) -> str:
    """Write a lesson plan to a Markdown file and return its absolute path.

    Never overwrites: if the slug already exists, a numeric suffix is added.
    """
    directory = directory or DEFAULT_DIR
    os.makedirs(directory, exist_ok=True)

    stem = _slugify(title)
    path = os.path.join(directory, f"{stem}.md")
    counter = 2
    while os.path.exists(path):
        path = os.path.join(directory, f"{stem}-{counter}.md")
        counter += 1

    body = content.strip()
    if not body.lstrip().startswith("#"):
        body = f"# {title}\n\n{body}"

    with open(path, "w", encoding="utf-8") as f:
        f.write(body + "\n")

    return os.path.abspath(path)


class SaveLessonPlanInput(BaseModel):
    """Input for saving a lesson plan."""

    title: str = Field(
        description="A short, descriptive title for the lesson, e.g. 'Counting with Autumn Leaves'."
    )
    content: str = Field(
        description="The complete lesson plan, formatted as Markdown."
    )


class SaveLessonPlanTool(BaseTool):
    """Persist a finished lesson plan to disk as a Markdown file."""

    name: str = "save_lesson_plan"
    description: str = (
        "Save a finished lesson plan to a Markdown file so the teacher can keep it. "
        "Only call this after you have produced a complete plan and the teacher wants "
        "to save it. Pass a clear title and the full Markdown content."
    )
    args_schema: Type[BaseModel] = SaveLessonPlanInput

    def _run(self, title: str, content: str) -> str:
        try:
            path = save_lesson_plan_to_file(title, content)
            return json.dumps({"success": True, "path": path})
        except Exception as e:  # noqa: BLE001
            return json.dumps({"success": False, "error": str(e)})

    async def _arun(self, title: str, content: str) -> str:
        return self._run(title, content)


def create_lesson_file_tool() -> SaveLessonPlanTool:
    """Create the save-lesson-plan tool."""
    return SaveLessonPlanTool()
