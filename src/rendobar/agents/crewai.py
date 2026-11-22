"""Rendobar tools for CrewAI agents.

    from rendobar.agents.crewai import rendobar_tools
    editor = Agent(role="Video editor", goal="...", backstory="...", tools=rendobar_tools())

Needs ``pip install "rendobar[crewai]"``.
"""
# pyright: strict
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .._client import Rendobar
from ._core import ToolDefinition, tool_definitions

try:
    from crewai.tools import BaseTool
except ImportError as err:  # pragma: no cover - exercised without the extra
    raise ImportError('rendobar.agents.crewai needs crewai: pip install "rendobar[crewai]"') from err


def _tool(definition: ToolDefinition) -> BaseTool:
    run: Callable[..., Dict[str, Any]] = definition.run

    class RendobarTool(BaseTool):
        def _run(self, **kwargs: Any) -> Dict[str, Any]:
            return run(**kwargs)

    RendobarTool.__name__ = f"Rendobar_{definition.name}"
    return RendobarTool(name=definition.name, description=definition.description, args_schema=definition.args_schema)


def rendobar_tools(client: Optional[Rendobar] = None) -> List[BaseTool]:
    """The four Rendobar tools as CrewAI tools. With no client, reads RENDOBAR_API_KEY."""
    return [_tool(d) for d in tool_definitions(client, app="crewai")]
