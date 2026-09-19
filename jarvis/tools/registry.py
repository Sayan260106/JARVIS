"""Central Tool Registry for JARVIS.

Manages tool discovery, schema generation, and tool retrieval.
"""

from __future__ import annotations
import json
from typing import Dict, List, Optional
from jarvis.tools.base import BaseTool


class ToolRegistry:
    """Registry maintaining active system tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> BaseTool:
        """Register a new tool instance."""
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieve tool by name."""
        return self._tools.get(name)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieve tool by name (alias for get)."""
        return self.get(name)

    def list_tools(self) -> List[BaseTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, str]]:
        """Return list of tool schemas for Ollama."""
        return [tool.to_schema() for tool in self._tools.values()]

    def get_prompt_description(self) -> str:
        """Format tools into a clean prompt block for Ollama tool calling."""
        lines = [
            "You have access to the following local tools:",
            "To use a tool, output ONLY a JSON object in this format:",
            '{"tool": "<tool_name>", "arguments": {<key>: <value>}}',
            "",
            "Available Tools:",
        ]
        for tool in self._tools.values():
            params_desc = ", ".join(
                f"{p.name} ({p.type}{', required' if p.required else ', optional'}): {p.description}"
                for p in tool.parameters.values()
            )
            lines.append(f"- {tool.name} [{tool.risk_level.value}]: {tool.description}")
            if params_desc:
                lines.append(f"  Arguments: {params_desc}")
            lines.append("")
        return "\n".join(lines)
