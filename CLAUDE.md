# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Prerequisites:**

- Node 18+
- Python 3.9+
- `pip install rich requests`
- **Optional for enhanced input**: `pip install prompt-toolkit` (enables Shift+Enter for new lines)

**Setup and Start:**

- Install proxy dependencies: `cd ai-server && npm ci`
- Start proxy server: `npm start` (from `ai-server` directory)
- Start in development mode: `npm run dev` (from `ai-server` directory)

**Running Clients:**

- Mock mode (streams demo data): `python3 llm-cli.py --mock`
- Provider mode: `python3 llm-cli.py --url http://127.0.0.1:8000/invoke`
- Debug clients:
  - Raw SSE inspection: `python3 debug/debug_cli.py --http "your prompt"`
  - Block-buffered output: `python3 debug/try.py` (press `q` to abort)

**Common Flags:**

- `--mock-file path/to/file.dat` - Use custom mock data file
- `--timeout 90` - Set request timeout
- `--live-window 6` - Adjust live rendering window size
- `--no-rule` - Disable model name header
- `--provider bedrock|azure` - Select provider type

**Multi-line Input:**
- **With prompt-toolkit installed**: Shift+Enter for new lines, Enter to submit
- **Without prompt-toolkit**: Empty line to submit when you have content
- **All versions**: `/paste` mode for large content blocks

## Architecture Overview

This is a streaming LLM client system with live Markdown rendering:

**Core Components:**

- `llm-cli.py` - Main CLI with live Markdown rendering and stable scrollback
- `sse_client.py` - SSE (Server-Sent Events) client library
- `ai-server/ai-core-proxy.js` - Node.js proxy server with OAuth handling
- `render/markdown_live.py` - Live Markdown renderer using Rich library
- `debug/` - Debug clients for testing and development

**Data Flow:**

1. Client sends request to proxy server (`/invoke` or `/mock`)
2. Proxy handles OAuth authentication and forwards to LLM provider
3. Response streams back as SSE with JSON events containing `content_block_delta` and `text_delta`
4. Client renders streaming Markdown with syntax highlighting in real-time

**Configuration:**

- Proxy config via `ai-server/.env`: `OAUTH_TOKEN_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `LLM_API_ENDPOINT`
- Default proxy runs on `127.0.0.1:8000`
- Default client URL can be set via `LLM_URL` environment variable

## Key Files

- `llm-cli.py` - Main polished CLI with live Markdown rendering
- `ai-server/ai-core-proxy.js` - Express server handling `/invoke`, `/mock`, `/healthz` endpoints
- `render/markdown_live.py` - Custom Rich-based Markdown renderer with code block handling
- `debug/try.py` - Block-buffered Markdown renderer for testing
- `debug/debug_cli.py` - Raw SSE debugging client
- `ai-server/mock.dat` - Demo SSE stream data for testing

## Testing and Validation

No formal test suite exists. Validate functionality via:

- Mock flow: Start proxy with `npm start`, run `python3 llm-cli.py --mock`
- Provider flow: Configure `.env` and run with `--url http://127.0.0.1:8000/invoke`
- SSE structure inspection: Use `debug/debug_cli.py --http` to examine raw stream format

Expected SSE event types: `message_start`, `content_block_delta` (with `text_delta`), `message_stop`.
