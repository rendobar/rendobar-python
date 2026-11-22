"""Rendobar tools for LangChain and LangGraph agents.

    from rendobar.agents.langchain import rendobar_tools
    agent = create_agent(model, tools=rendobar_tools())

Needs ``pip install "rendobar[langchain]"``.
"""
# pyright: strict
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from .._client import Rendobar
from ._core import tool_definitions

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

try:
    from langchain_core.tools import StructuredTool
except ImportError as err:  # pragma: no cover - exercised without the extra
    raise ImportError('rendobar.agents.langchain needs langchain-core: pip install "rendobar[langchain]"') from err


def rendobar_tools(client: Optional[Rendobar] = None) -> List["BaseTool"]:
    """The four Rendobar tools as LangChain tools. With no client, reads RENDOBAR_API_KEY."""
    return [
        StructuredTool.from_function(func=d.run, name=d.name, description=d.description, args_schema=d.args_schema)
        for d in tool_definitions(client, app="langchain")
    ]
