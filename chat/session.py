"""Chat session orchestration and API interactions."""

from typing import List, Optional, Tuple
from rich.console import Console

# We'll need to import these when used in main file
# from tools.definitions import AVAILABLE_TOOLS
# from main streaming function will be imported

console = Console(soft_wrap=True)


class ChatSession:
    """Orchestrates API interactions and tool execution flows."""
    
    def __init__(self, url: str, provider, model: Optional[str], max_tokens: int, 
                 live_window: int, use_mock: bool, timeout: float, mock_file: Optional[str],
                 show_rule: bool, tool_executor):
        self.url = url
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.live_window = live_window
        self.use_mock = use_mock
        self.timeout = timeout
        self.mock_file = mock_file
        self.show_rule = show_rule
        self.tool_executor = tool_executor
    
    def send_message(self, history: List[dict], use_thinking: bool, tools_enabled: bool, 
                    available_tools, stream_and_render_func) -> Tuple[str, int, float, List[dict]]:
        """Send a message and handle the complete request/response cycle including tools."""
        # Build request payload with conditional tool support
        tools_param = available_tools if tools_enabled else None
        payload = self.provider.build_payload(history, model=self.model, max_tokens=self.max_tokens, 
                                             thinking=use_thinking, tools=tools_param)
        
        # Stream initial response and capture any tool calls
        reply_text, tokens_used, cost_used, tool_calls_made = stream_and_render_func(
            self.url,
            payload,
            mapper=self.provider.map_events,
            live_window=self.live_window,
            use_mock=self.use_mock,
            timeout=self.timeout,
            mock_file=self.mock_file,
            show_rule=self.show_rule,
            tool_executor=self.tool_executor,
        )
        
        return reply_text, tokens_used, cost_used, tool_calls_made
    
    def handle_tool_followup(self, history: List[dict], use_thinking: bool, tools_enabled: bool, 
                           available_tools, stream_and_render_func) -> Tuple[str, int, float]:
        """Handle follow-up request after tool execution."""
        console.print("[dim]Getting Claude's response to tool results...[/dim]")
        
        # Follow-up request includes tool results in context
        tools_param = available_tools if tools_enabled else None
        followup_payload = self.provider.build_payload(history, model=self.model, max_tokens=self.max_tokens, 
                                                      thinking=use_thinking, tools=tools_param)
        
        followup_reply, followup_tokens, followup_cost, _ = stream_and_render_func(
            self.url,
            followup_payload, 
            mapper=self.provider.map_events,
            live_window=self.live_window,
            use_mock=self.use_mock,
            timeout=self.timeout,
            mock_file=self.mock_file,
            show_rule=False,  # Skip model header for follow-up
            tool_executor=self.tool_executor,
        )
        
        return followup_reply, followup_tokens, followup_cost