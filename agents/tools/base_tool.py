"""
Base tool class for ReAct Rails agent tools.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseTool(ABC):
    """Abstract base class for all ReAct agent tools."""

    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize the tool.

        Args:
            project_root: Root directory of the Rails project
        """
        self.project_root = project_root

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for identification."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        pass

    @property
    def parameters(self) -> Dict[str, Any]:
        """
        Tool parameter schema for LLM function calling.

        Returns:
            JSON schema describing the tool's input parameters
        """
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    @abstractmethod
    async def execute(self, input_params: Dict[str, Any]) -> Any:
        """
        Execute the tool with given parameters.

        Args:
            input_params: Input parameters for tool execution

        Returns:
            Tool execution result
        """
        pass

    def validate_input(self, input_params: Dict[str, Any]) -> bool:
        """
        Validate input parameters.

        Args:
            input_params: Parameters to validate

        Returns:
            True if valid, False otherwise
        """
        # Default implementation - override in subclasses for specific validation
        return isinstance(input_params, dict)

    def format_result(self, result: Any) -> str:
        """
        Format tool result for LLM consumption.

        Args:
            result: Raw tool result

        Returns:
            Formatted string result
        """
        if isinstance(result, str):
            return result
        elif isinstance(result, (list, dict)):
            import json
            return json.dumps(result, indent=2)
        else:
            return str(result)