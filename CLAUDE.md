# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Prerequisites:**

- Node 18+
- Python 3.9+ (3.13+ recommended)
- Virtual environment: `python3 -m venv .venv && source .venv/bin/activate`
- Dependencies: `pip install rich requests prompt-toolkit pytest`

**Setup and Start:**

- Install proxy dependencies: `cd ai-server && npm ci`
- Start proxy server: `npm start` (from `ai-server` directory)
- Start in development mode: `npm run dev` (from `ai-server` directory)

**Running Main CLI:**

- Default mode: `python3 llm-cli.py`
- Azure provider: `python3 llm-cli.py --provider azure`
- Custom endpoint: `python3 llm-cli.py --url http://other-host:8000/invoke`

**Main CLI Flags:**

- `--url <endpoint>` - Endpoint URL (default: http://127.0.0.1:8000/invoke)
- `--provider bedrock|azure` - Provider type (default: bedrock)

**Debug/Testing:**

- Raw HTTP/SSE inspection: `python3 debug/debug.py --http "your prompt"`
- Plain text output: `python3 debug/debug.py --raw "your prompt"`
- Block-buffered Markdown: `python3 debug/debug.py --block "your prompt"`
- Interactive debug mode: `python3 debug/debug.py --interactive`
- Mock mode: `python3 debug/debug.py --mock "test prompt"`

**Debug Script Flags:**

- `--mock` - Use mock endpoint instead of real provider
- `--mock-file path/to/file.dat` - Custom mock data file
- `--mock-delay 1000` - Mock delay in milliseconds
- `--model <name>` - Specify model for testing
- `--max-tokens <num>` - Token limit for testing
- `--timeout <seconds>` - Request timeout
- `--live-window <num>` - Live rendering window size

**Multi-line Input:**
- **Enter** = Submit message
- **Ctrl+J** = New line
- **`/paste`** = Special mode for large content (type `/end` to finish)
- **`▌` cursor** appears on every line for visual consistency

## Architecture Overview

This is a streaming LLM client system with live Markdown rendering, RAG capabilities, tool calling, and conversation management:

**Core Components:**

- `llm-cli.py` - Main CLI with live Markdown rendering, context management, and tool support
- `util/sse_client.py` - SSE (Server-Sent Events) client library
- `ai-server/ai-core-proxy.js` - Node.js proxy server with OAuth handling
- `render/markdown_live.py` - Live Markdown renderer using Rich library
- `chat/` - Session and conversation management with usage tracking
- `context/` - Context file management system
- `rag/` - Retrieval-Augmented Generation with TF-IDF indexing
- `tools/` - Built-in tool execution system
- `providers/` - Provider adapters for Bedrock and Azure OpenAI
- `debug/` - Debug clients for testing and development

**Data Flow:**

1. Client sends request to proxy server (`/invoke` or `/mock`)
2. Proxy handles OAuth authentication and forwards to LLM provider
3. Response streams back as SSE with JSON events containing `content_block_delta` and `text_delta`
4. Client renders streaming Markdown with syntax highlighting in real-time
5. Tool calls are automatically executed and results streamed back
6. Conversation history and usage metrics are tracked

**Configuration:**

- Proxy config via `ai-server/.env`: `OAUTH_TOKEN_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `LLM_API_ENDPOINT`
- Default proxy runs on `127.0.0.1:8000`
- No environment variables needed (all settings via CLI flags)

## Key Features

**RAG (Retrieval-Augmented Generation):**
- `/rag index naive <path>` - Index files/directories with TF-IDF chunking
- `/rag on|off` - Enable/disable RAG for next prompt
- `/rag search "query" k` - Preview search results
- `/rag status|clear` - Inspect or clear index
- Persistent storage in `context/.rag_index.json`

**Context Management:**
- `/context <file>` - Add files to prompt context
- `/context list|clear` - Manage context files
- `@` path browser - Interactive file selection dropdown

**Tool System:**
- Built-in tools: calculator, weather, time
- Automatic tool execution during streaming
- Toggle tools via input indicator

**Conversation Management:**
- Session persistence and history
- Usage tracking and metrics
- Multi-provider support (Bedrock, Azure OpenAI)

## Key Files

- `llm-cli.py` - Main CLI with live Markdown rendering and comprehensive features
- `util/simple_pt_input.py` - Multi-line input handler with `▌` cursor support
- `util/sse_client.py` - SSE client with provider adapter support
- `ai-server/ai-core-proxy.js` - Express server handling `/invoke`, `/mock`, `/healthz` endpoints
- `render/markdown_live.py` - Custom Rich-based Markdown renderer with code block handling
- `chat/session.py` - Session management and persistence
- `chat/conversation.py` - Conversation history and context
- `chat/usage_tracker.py` - Token and usage metrics tracking
- `context/context_manager.py` - File context management system
- `rag/manager.py` - RAG system with TF-IDF indexing and retrieval
- `tools/executor.py` - Tool execution engine with built-in tools
- `providers/bedrock.py` - AWS Bedrock provider adapter
- `providers/azure_openai.py` - Azure OpenAI provider adapter
- `debug/debug.py` - Unified debug client with multiple output modes (HTTP/SSE inspection, block-buffered Markdown, interactive mode)
- `ai-server/mock.dat` - Demo SSE stream data for testing

## Testing and Validation

**Test Suite:**
- Run all tests: `pytest -q` (requires `pip install pytest`)
- Test coverage includes: RAG indexing/search, provider adapters, tool execution, conversation management, SSE parsing, input handling

**Manual Validation:**
- Basic flow: Start proxy with `npm start`, run `python3 llm-cli.py`
- Provider testing: `python3 llm-cli.py --provider azure`
- Mock testing: `python3 debug/debug.py --mock "test prompt"`
- RAG testing: Use `/rag index naive <path>` and `/rag search "query"` to validate retrieval
- Tool testing: Enable tools and test calculator, weather, time functions
- Context testing: Use `/context <file>` and `@` path browser
- SSE structure inspection: Use `python3 debug/debug.py --http "test"` to examine raw stream format

**Expected SSE Event Types:**
- `message_start`, `content_block_delta` (with `text_delta`), `message_stop`, `tool_use`, `tool_result`
