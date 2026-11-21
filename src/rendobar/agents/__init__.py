"""Rendobar tools for AI agent frameworks.

    from rendobar.agents.langchain import rendobar_tools   # pip install "rendobar[langchain]"
    from rendobar.agents.crewai import rendobar_tools      # pip install "rendobar[crewai]"

Both give the agent the same four tools as Rendobar's MCP server. For a framework
that speaks MCP (the OpenAI Agents SDK, the Claude Agent SDK), connect it to
https://api.rendobar.com/mcp instead.
"""
# pyright: strict
from ._core import ToolDefinition, summarize, tool_definitions

__all__ = ["ToolDefinition", "summarize", "tool_definitions"]
