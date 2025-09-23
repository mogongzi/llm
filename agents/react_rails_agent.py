"""
ReAct Rails Agent - Reasoning and Acting AI agent for Rails code analysis.

This agent uses the ReAct (Reasoning + Acting) pattern to dynamically analyze
Rails codebases by reasoning about queries and orchestrating tool usage.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from rich.console import Console

from agents.tools.base_tool import BaseTool
from agents.tools.ripgrep_tool import RipgrepTool
from agents.tools.model_analyzer import ModelAnalyzer
from agents.tools.controller_analyzer import ControllerAnalyzer
from agents.tools.route_analyzer import RouteAnalyzer
from agents.tools.migration_analyzer import MigrationAnalyzer
from agents.prompts.system_prompt import RAILS_REACT_SYSTEM_PROMPT
from util.sse_client import SSEClient
from providers import get_provider


@dataclass
class ReActStep:
    """Represents a single step in the ReAct loop."""
    step_type: str  # 'thought', 'action', 'observation', 'answer'
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None


class ReactRailsAgent:
    """
    ReAct Rails Agent for intelligent code analysis.

    Uses the ReAct pattern: Reasoning → Action → Observation → (repeat) → Answer
    """

    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize the ReAct Rails agent.

        Args:
            project_root: Root directory of the Rails project
        """
        self.project_root = project_root
        self.console = Console()
        self.tools: Dict[str, BaseTool] = {}
        self.conversation_history: List[Dict[str, Any]] = []
        self.react_steps: List[ReActStep] = []

        # Initialize tools
        self._init_tools()

        # LLM client for reasoning
        self.provider = get_provider("bedrock")  # Default to bedrock
        self.sse_client = SSEClient(self.provider)

    def _init_tools(self) -> None:
        """Initialize available tools for the agent."""
        try:
            self.tools['ripgrep'] = RipgrepTool(self.project_root)
            self.tools['model_analyzer'] = ModelAnalyzer(self.project_root)
            self.tools['controller_analyzer'] = ControllerAnalyzer(self.project_root)
            self.tools['route_analyzer'] = RouteAnalyzer(self.project_root)
            self.tools['migration_analyzer'] = MigrationAnalyzer(self.project_root)

            self.console.print(f"[dim]Initialized {len(self.tools)} tools for Rails analysis[/dim]")
        except Exception as e:
            self.console.print(f"[red]Error initializing tools: {e}[/red]")

    def set_project_root(self, project_root: str) -> None:
        """Update the project root and reinitialize tools."""
        self.project_root = project_root
        self._init_tools()

    async def process_message(self, user_query: str) -> str:
        """
        Main entry point for processing user queries using ReAct pattern.

        Args:
            user_query: User's natural language query about Rails code

        Returns:
            Agent's response with analysis results
        """
        try:
            self.console.print(f"[dim]🤖 Analyzing: {user_query}[/dim]")

            # Start ReAct loop
            self.react_steps = []
            self.conversation_history.append({"role": "user", "content": user_query})

            # Initial reasoning
            response = await self._react_loop(user_query)

            # Add agent response to history
            self.conversation_history.append({"role": "assistant", "content": response})

            return response

        except Exception as e:
            error_msg = f"Error processing query: {e}"
            self.console.print(f"[red]{error_msg}[/red]")
            return error_msg

    async def _react_loop(self, user_query: str, max_steps: int = 10) -> str:
        """
        Execute the ReAct reasoning and acting loop.

        Args:
            user_query: User's query to analyze
            max_steps: Maximum number of ReAct steps to prevent infinite loops

        Returns:
            Final agent response
        """
        # Build initial prompt with system instructions and query
        messages = [
            {"role": "system", "content": RAILS_REACT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Please analyze this Rails query: {user_query}"}
        ]

        for step in range(max_steps):
            try:
                # Get LLM reasoning/action
                response = await self._call_llm(messages)

                # Parse the response to determine next action
                action = self._parse_llm_response(response)

                if action['type'] == 'thought':
                    # Agent is reasoning
                    self.react_steps.append(ReActStep(
                        step_type='thought',
                        content=action['content']
                    ))
                    self.console.print(f"[yellow]💭 Thought:[/yellow] {action['content']}")

                elif action['type'] == 'action':
                    # Agent wants to use a tool
                    tool_name = action['tool']
                    tool_input = action['input']

                    self.react_steps.append(ReActStep(
                        step_type='action',
                        content=f"Using {tool_name}",
                        tool_name=tool_name,
                        tool_input=tool_input
                    ))

                    self.console.print(f"[blue]🔧 Action:[/blue] {tool_name}({tool_input})")

                    # Execute tool
                    tool_output = await self._execute_tool(tool_name, tool_input)

                    # Add observation
                    self.react_steps.append(ReActStep(
                        step_type='observation',
                        content=str(tool_output),
                        tool_output=tool_output
                    ))

                    self.console.print(f"[green]👁 Observation:[/green] {str(tool_output)[:200]}...")

                    # Add tool result to conversation
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": f"Tool result: {tool_output}"})

                elif action['type'] == 'answer':
                    # Agent has final answer
                    self.react_steps.append(ReActStep(
                        step_type='answer',
                        content=action['content']
                    ))

                    self.console.print(f"[cyan]✅ Answer:[/cyan] {action['content']}")
                    return action['content']

                else:
                    # Add the response and continue
                    messages.append({"role": "assistant", "content": response})

            except Exception as e:
                self.console.print(f"[red]Error in ReAct step {step}: {e}[/red]")
                break

        # If we reach max steps, return summary
        return self._generate_summary()

    async def _call_llm(self, messages: List[Dict[str, Any]]) -> str:
        """
        Call the LLM with conversation messages.

        Args:
            messages: Conversation messages

        Returns:
            LLM response text
        """
        try:
            # For now, use a simple prompt-based approach
            # In full implementation, this would use the streaming client

            # Convert messages to simple prompt format
            prompt_parts = []
            for msg in messages:
                if msg['role'] == 'system':
                    prompt_parts.append(f"System: {msg['content']}")
                elif msg['role'] == 'user':
                    prompt_parts.append(f"Human: {msg['content']}")
                elif msg['role'] == 'assistant':
                    prompt_parts.append(f"Assistant: {msg['content']}")

            prompt = "\n\n".join(prompt_parts) + "\n\nAssistant:"

            # Placeholder for actual LLM call
            # In full implementation, this would use the SSE client
            return self._mock_llm_response(messages[-1]['content'])

        except Exception as e:
            return f"Error calling LLM: {e}"

    def _mock_llm_response(self, user_query: str) -> str:
        """
        Mock LLM response for development/testing.
        In production, this would be replaced with actual LLM calls.
        """
        # Simple keyword-based mock responses
        query_lower = user_query.lower()

        if 'validation' in query_lower or 'validates' in query_lower:
            if 'product' in query_lower:
                return """
Thought: I need to analyze validations for the Product model. Let me examine the Product model file to find validation rules.

Action: model_analyzer
Input: {"model_name": "Product", "focus": "validations"}
"""
            else:
                return """
Thought: I need to find validation-related code. Let me search for validation patterns in the codebase.

Action: ripgrep
Input: {"pattern": "validates", "file_types": ["rb"]}
"""

        elif 'callback' in query_lower or 'before' in query_lower or 'after' in query_lower:
            return """
Thought: This query is about Rails callbacks. I should examine model files for callback definitions.

Action: ripgrep
Input: {"pattern": "before_|after_|around_", "file_types": ["rb"]}
"""

        elif 'controller' in query_lower:
            return """
Thought: This is a controller-related query. Let me analyze the relevant controller.

Action: controller_analyzer
Input: {"controller_name": "Application", "action": "all"}
"""

        elif 'route' in query_lower or 'routing' in query_lower:
            return """
Thought: This query is about Rails routing. Let me examine the routes configuration.

Action: route_analyzer
Input: {"focus": "all"}
"""

        elif 'migration' in query_lower or 'database' in query_lower or 'schema' in query_lower:
            return """
Thought: This query involves database structure or migrations. Let me analyze recent migrations.

Action: migration_analyzer
Input: {"migration_type": "all", "limit": 5}
"""

        else:
            return """
Thought: I need to understand this Rails codebase better. Let me start with a general search.

Action: ripgrep
Input: {"pattern": "class.*ApplicationRecord", "file_types": ["rb"]}
"""

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response to extract thought/action/answer.

        Args:
            response: Raw LLM response

        Returns:
            Parsed action dictionary
        """
        response = response.strip()

        # Look for structured patterns
        if "Thought:" in response:
            thought_content = response.split("Thought:")[-1].split("Action:")[0].strip()
            return {"type": "thought", "content": thought_content}

        elif "Action:" in response:
            action_part = response.split("Action:")[-1].strip()
            lines = action_part.split('\n')
            tool_name = lines[0].strip()

            # Look for input
            tool_input = {}
            if "Input:" in response:
                input_part = response.split("Input:")[-1].strip()
                try:
                    tool_input = json.loads(input_part)
                except:
                    # Fallback to simple parsing
                    tool_input = {"query": input_part}

            return {"type": "action", "tool": tool_name, "input": tool_input}

        elif "Answer:" in response:
            answer_content = response.split("Answer:")[-1].strip()
            return {"type": "answer", "content": answer_content}

        else:
            # Default: treat as thought
            return {"type": "thought", "content": response}

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Execute a tool with given input.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            Tool execution result
        """
        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' not available"

        try:
            tool = self.tools[tool_name]
            result = await tool.execute(tool_input)
            return result
        except Exception as e:
            return f"Error executing {tool_name}: {e}"

    def _generate_summary(self) -> str:
        """Generate a summary of the ReAct session."""
        if not self.react_steps:
            return "No analysis steps completed."

        summary_parts = ["## Rails Code Analysis Summary\n"]

        for step in self.react_steps:
            if step.step_type == 'thought':
                summary_parts.append(f"**Reasoning:** {step.content}")
            elif step.step_type == 'action':
                summary_parts.append(f"**Tool Used:** {step.tool_name}")
            elif step.step_type == 'observation':
                summary_parts.append(f"**Result:** {step.content[:200]}...")
            elif step.step_type == 'answer':
                summary_parts.append(f"**Answer:** {step.content}")

        return "\n\n".join(summary_parts)

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            "project_root": self.project_root,
            "tools_available": list(self.tools.keys()),
            "conversation_length": len(self.conversation_history),
            "react_steps": len(self.react_steps)
        }