**Overview**

- **Purpose:** Stream LLM responses over SSE and render Markdown cleanly in the terminal.
- **Clients:** `llm-cli.py` (polished live Markdown) and `debug/debug.py` (unified debug client: raw/http, block-buffered, live, interactive).
- **Proxy:** `ai-server/ai-core-proxy.js` forwards to your provider with OAuth client credentials and exposes `/invoke`, `/mock`, and `/healthz`.

**Quick Start**

- **Prerequisites:** Node 18+, Python 3.9+, `pip install rich requests prompt-toolkit`.
- **Install proxy deps:** `cd ai-server && npm ci`
- **Start proxy:** `npm start` (run from `ai-server`)
- **Run client (provider):** `python3 llm-cli.py --provider bedrock --url http://127.0.0.1:8000/invoke`
- **Run client (mock):** `python3 llm-cli.py --url http://127.0.0.1:8000/mock` (main CLI uses `/mock` URL; advanced mock flags are in the debug client)

**RAG (Retrieval‑Augmented Generation)**

- **What’s included:** A simple, chunked TF‑IDF retriever with persistence.
- **Indexing:** `/rag index naive <path>` (accepts a file or directory; recurses; saves to `context/.rag_index.json`).
- **Enable retrieval:** `/rag on` (your next prompt auto‑injects a `<context>…</context>` block).
- **Preview results:** `/rag search "your query" 5` (prints top‑k matches with file/offset).
- **Inspect/clear:** `/rag status`, `/rag clear`.
- **Defaults:** `chunk_size=1000`, `overlap=200`, `k=3`, `char_cap=6000` (see `rag/manager.py`).

Behavior when RAG is on
- The client injects a strict system prompt that enforces grounded answers from the `<context>…</context>` block only.
- If the answer is not supported by that context, the model responds exactly with: `I don’t know based on the provided documents.`
- When no matches are retrieved, the client still sends an empty `<context></context>` to trigger the no‑match behavior reliably.

Notes
- Retrieval currently uses character‑based overlapping chunks and TF‑IDF cosine similarity.
- Ignored files: large non‑text files are skipped; common text/code/doc extensions are indexed.
- Context format injected to the model: `<context><chunk src="path#start-end">…</chunk>…</context>`.

**Mock Mode**

- **Start proxy:** `cd ai-server && npm start`
- **Main CLI:** `python3 llm-cli.py --url http://127.0.0.1:8000/mock`
- **Debug client:** `python3 -m debug.debug --mock "your prompt"`
- **Notes:**
  - Mock endpoint streams frames from `ai-server/mock.dat` by default.
  - Override file: `--mock-file ai-server/mock.dat` (debug client) or `GET /mock?file=path/to/file.dat`.
  - Add delay: `--mock-delay 250` or `LLM_MOCK_DELAY_MS=250`.

**Provider Mode**

- **Configure env:** Create `ai-server/.env` with:
  - `OAUTH_TOKEN_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `LLM_API_ENDPOINT`
  - Optional: `HOST` (default `127.0.0.1`), `PORT` (default `8000`).
- **Start proxy:** `cd ai-server && npm start`
- **Use client:** `python3 llm-cli.py --url http://127.0.0.1:8000/invoke`

**CLIs**

- `llm-cli.py` (main): Live Markdown with stable scrollback, thinking/tool toggles, file context, and RAG. Flags: `--url`, `--provider {bedrock,azure}`.
- `debug/debug.py` (unified):
  - `--http` raw SSE lines
  - `--raw` plain text
  - `--block` block-buffered Markdown
  - `--live` live rendering via StreamingClient
  - `--interactive` interactive block-buffered mode
  - Extras: `--mock`, `--mock-file`, `--mock-delay`, `--timeout`, `--live-window`, `--model`, `--max-tokens`.

**Context Files**

- **Add/remove/list:** `/context <file>`, `/context clear`, `/context list`.
- **Path browser:** type `@` in the prompt to open a dropdown of files/folders; select to add to context.
- The CLI automatically formats file snippets into a context block the model can use.

**Tools**

- Built‑in tool calling is supported (calculator, weather, time). Toggle tools via the input indicator.
- When tools are called by the model, the CLI streams tool inputs, executes, and sends results back automatically.

**Troubleshooting**

- **Auth errors:** Check `.env` values and that OAuth client can request `client_credentials` tokens.
- **CORS/headers:** Proxy mirrors upstream `content-*` headers and streams body as-is.
- **Network timeouts:** Clients use a 60s timeout; adjust if your provider is slow.
- **Abort:** Press `Esc` during streaming (main CLI and debug live/block). `Ctrl+C` exits program.

**Project Structure**

- `llm-cli.py`: Main Python CLI; streams SSE, renders live Markdown, supports tools, context, and RAG.
- `streaming_client.py`: SSE client + live renderer integration and tool execution wiring.
- `chat/`: Conversation/session orchestration, usage tracking, tool workflow glue.
- `context/`: Context manager for attaching local files to prompts.
- `rag/`: Naive TF‑IDF chunked indexer and manager (persistence, retrieval, context formatting).
- `providers/`: Provider adapters mapping raw SSE to events (`bedrock`, `azure`).
- `render/`: Live and block‑buffered rendering utilities.
- `tools/`: Built‑in tools and executor.
- `debug/`: Unified debug client (`debug.py`).
- `ai-server/`: Node 18+ proxy exposing `/invoke`, `/mock`, `/healthz`; configure via `.env`.
- `tests/`: Python tests (pytest) for parsing, rendering, providers, and RAG.

**Flags and Env**

- Main CLI: `--url`, `--provider {bedrock,azure}` (toggle thinking, tools, context, and RAG inside the REPL).
- Debug client: `--http|--raw|--block|--live|--interactive`, plus `--mock`, `--mock-file`, `--mock-delay`, `--timeout`, `--live-window`, `--model`, `--max-tokens`.
- Env overrides: `LLM_MOCK_DELAY_MS` (mock delay for proxy/debug), provider creds via `ai-server/.env`.

**Testing**

- Install: `pip install pytest`
- Run all tests: `pytest -q`
- Recommended flows:
  - Start proxy, then validate rendering via main CLI with `--url http://127.0.0.1:8000/mock` or via debug client `--http/--block/--live`.
  - Use `/rag index naive <path>` and `/rag search "query"` to validate retrieval output.

**Security & Configuration**

- Do not commit secrets. Use `ai-server/.env` with `OAUTH_TOKEN_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `LLM_API_ENDPOINT`.
- Avoid logging credentials; remove OAuth debug prints.
- Default proxy binds to `127.0.0.1:8000`; keep localhost during development.

**RAG Limitations & Roadmap**

- Current limitations: character‑based chunking, TF‑IDF only, no incremental indexing, fixed `char_cap`.
- Potential enhancements: markdown/code‑aware chunking, stopwords/BM25, hybrid retrieval with embeddings, incremental reindex, `/rag config` to tune `k/chunk/overlap/char_cap`.
