"""
Ripgrep tool for fast text search in Rails projects.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool


class RipgrepTool(BaseTool):
    """Tool for fast text search using ripgrep."""

    @property
    def name(self) -> str:
        return "ripgrep"

    @property
    def description(self) -> str:
        return "Fast text search in Rails codebase using ripgrep. Excellent for finding exact code patterns, method calls, and string matches."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for"
                },
                "file_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File extensions to search (e.g., ['rb', 'erb'])",
                    "default": ["rb"]
                },
                "context": {
                    "type": "integer",
                    "description": "Number of context lines to show around matches",
                    "default": 2
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 20
                }
            },
            "required": ["pattern"]
        }

    async def execute(self, input_params: Dict[str, Any]) -> Any:
        """
        Execute ripgrep search.

        Args:
            input_params: Search parameters

        Returns:
            Search results with file paths, line numbers, and content
        """
        if not self.validate_input(input_params):
            return "Error: Invalid input parameters"

        if not self.project_root or not Path(self.project_root).exists():
            return "Error: Project root not found"

        pattern = input_params.get("pattern", "")
        file_types = input_params.get("file_types", ["rb"])
        context = input_params.get("context", 2)
        max_results = input_params.get("max_results", 20)

        if not pattern:
            return "Error: Pattern is required"

        try:
            # Build ripgrep command
            cmd = ["rg", "--line-number", "--with-filename"]

            # Add context if specified
            if context > 0:
                cmd.extend(["-C", str(context)])

            # Add file type filters
            for file_type in file_types:
                cmd.extend(["--type-add", f"target:{file_type}", "--type", "target"])

            # Add pattern and search path
            cmd.extend([pattern, self.project_root])

            # Execute ripgrep
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                if result.returncode == 1:  # No matches found
                    return {"matches": [], "total": 0, "message": "No matches found"}
                else:
                    return f"Ripgrep error: {result.stderr}"

            # Parse results
            matches = self._parse_ripgrep_output(result.stdout, max_results)

            return {
                "matches": matches,
                "total": len(matches),
                "pattern": pattern,
                "file_types": file_types
            }

        except subprocess.TimeoutExpired:
            return "Error: Search timed out"
        except Exception as e:
            return f"Error executing ripgrep: {e}"

    def _parse_ripgrep_output(self, output: str, max_results: int) -> List[Dict[str, Any]]:
        """
        Parse ripgrep output into structured results.

        Args:
            output: Raw ripgrep output
            max_results: Maximum number of results to return

        Returns:
            List of match dictionaries
        """
        matches = []
        lines = output.strip().split('\n')

        for line in lines[:max_results]:
            if not line.strip():
                continue

            # Parse ripgrep output format: file:line:content
            if ':' in line:
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    file_path = parts[0]
                    try:
                        line_number = int(parts[1])
                        content = parts[2]

                        # Make path relative to project root
                        try:
                            rel_path = Path(file_path).relative_to(self.project_root)
                        except ValueError:
                            rel_path = Path(file_path)

                        matches.append({
                            "file": str(rel_path),
                            "line": line_number,
                            "content": content.strip(),
                            "context": "match"
                        })
                    except ValueError:
                        # Line number parsing failed, might be context line
                        continue

        return matches

    def validate_input(self, input_params: Dict[str, Any]) -> bool:
        """Validate ripgrep input parameters."""
        if not super().validate_input(input_params):
            return False

        pattern = input_params.get("pattern")
        if not pattern or not isinstance(pattern, str):
            return False

        file_types = input_params.get("file_types", ["rb"])
        if not isinstance(file_types, list):
            return False

        return True