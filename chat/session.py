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
                 show_rule: bool, tool_executor, context_manager=None, rag_manager=None, provider_name: str = "bedrock"):
        self.url = url
        self.provider = provider
        self.provider_name = provider_name
        self.model = model
        self.max_tokens = max_tokens
        self.live_window = live_window
        self.use_mock = use_mock
        self.timeout = timeout
        self.mock_file = mock_file
        self.show_rule = show_rule
        self.tool_executor = tool_executor
        self.context_manager = context_manager
        self.rag_manager = rag_manager
    
    def send_message(self, history: List[dict], use_thinking: bool, tools_enabled: bool, 
                    available_tools, stream_and_render_func) -> Tuple[str, int, float, List[dict]]:
        """Send a message and handle the complete request/response cycle including tools."""
        # Build request payload with conditional tool support and context injection
        tools_param = available_tools if tools_enabled else None
        base_context = self.context_manager.format_context_for_llm() if self.context_manager else None

        # Compose RAG context if enabled
        rag_block = None
        if self.rag_manager and getattr(self.rag_manager, "enabled", False):
            # Use last user message content as query
            query = ""
            for msg in reversed(history):
                if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                    query = msg["content"]
                    break
            if query.strip():
                try:
                    rag_block = self.rag_manager.search_and_format(query, k=self.rag_manager.default_k)
                except Exception:
                    rag_block = None
        # Merge context blocks
        context_parts = []
        if base_context:
            context_parts.append(base_context)
        if rag_block:
            context_parts.append(rag_block)
        context_content = "\n\n".join(context_parts) if context_parts else None
        payload = self.provider.build_payload(history, model=self.model, max_tokens=self.max_tokens, 
                                             thinking=use_thinking, tools=tools_param, context_content=context_content)
        
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
            use_thinking=use_thinking,
            provider_name=self.provider_name,
        )
        
        return reply_text, tokens_used, cost_used, tool_calls_made
    
    def handle_tool_followup(self, history: List[dict], use_thinking: bool, tools_enabled: bool, 
                           available_tools, stream_and_render_func) -> Tuple[str, int, float]:
        """Handle follow-up request after tool execution."""
        console.print("[dim]Getting Claude's response to tool results...[/dim]")
        
        # Follow-up request includes tool results in context
        tools_param = available_tools if tools_enabled else None
        context_content = self.context_manager.format_context_for_llm() if self.context_manager else None
        followup_payload = self.provider.build_payload(history, model=self.model, max_tokens=self.max_tokens, 
                                                      thinking=use_thinking, tools=tools_param, context_content=context_content)
        
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
            use_thinking=use_thinking,
            provider_name=self.provider_name,
        )
        
        return followup_reply, followup_tokens, followup_cost
