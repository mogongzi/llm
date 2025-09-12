**Overview**

- **Purpose:** Stream LLM responses over SSE and render Markdown cleanly in the terminal.
- **Clients:** `llm-cli.py` (polished live Markdown), `debug/try.py` (block-buffered), `debug/debug_cli.py` (raw/http debug).
- **Proxy:** `ai-server/ai-core-proxy.js` forwards to your provider with OAuth client credentials and exposes `/invoke`, `/mock`, and `/healthz`.

**Quick Start**

- **Prerequisites:** Node 18+, Python 3.9+, `pip install rich requests`.
- **Install proxy deps:** `cd ai-server && npm ci`
- **Start proxy:** `npm start` (run from `ai-server`)
- **Run client (mock):** `python3 llm-cli.py --mock` (streams `ai-server/mock.dat`)
- **Run client (provider):** `python3 llm-cli.py --url http://127.0.0.1:8000/invoke`
- **Useful flags:** `--mock-file path/to/file.dat`, `--timeout 90`, `--live-window 6`, `--no-rule`

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
- **Stream mock data:** `python3 llm-cli.py --mock`
- **Notes:**
  - Hits `http://127.0.0.1:8000/mock` and streams frames from `ai-server/mock.dat`.
  - Override file: `GET /mock?file=path/to/file.dat`.

**Provider Mode**

- **Configure env:** Create `ai-server/.env` with:
  - `OAUTH_TOKEN_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `LLM_API_ENDPOINT`
  - Optional: `HOST` (default `127.0.0.1`), `PORT` (default `8000`).
- **Start proxy:** `cd ai-server && npm start`
- **Use client:** `python3 llm-cli.py --url http://127.0.0.1:8000/invoke`

**CLIs**

- `llm-cli.py`: live Markdown with stable scroll back, headings, and code blocks. Supports `--provider` (`bedrock` [Bedrock Anthropic] or `azure` [Azure OpenAI]).
- `debug/try.py`: prints only completed blocks (paragraphs/fenced code); abort with `q`. Supports `--provider`.
- `debug/debug_cli.py`: `--http` prints raw SSE lines; default prints plain text chunks. Supports `--provider`.

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
- **Abort:** `Ctrl+C` anywhere; `q` during `try.py` streaming.

**Project Structure**

- `llm-cli.py`: Main Python CLI; streams SSE, renders live Markdown, supports tool calls.
- `ai-server/`: Node 18+ proxy exposing `/invoke`, `/mock`, `/healthz`; configure via `.env`.
- `providers/`: Provider adapters mapping raw SSE to events (`bedrock`, `azure`).
- `render/`: Live vs block‑buffered rendering utilities.
- `tools/`: Built‑in tools and executor.
- `context/`: Context manager for attaching local files to prompts.
- `rag/`: Naive TF‑IDF chunked indexer and manager (persistence, retrieval, context formatting).
- `debug/`: Local CLI/renderer tools (`try.py`, `debug_cli.py`).
- `tests/`: Python tests (pytest) for parsing, rendering, and RAG.

**Flags and Env**

- CLI flags: `--model`, `--max-tokens 4096`, `--mock-file`, `--mock-delay`, `--timeout 90`, `--live-window 6`, `--no-rule`.
- Env overrides: `LLM_URL`, `LLM_PROVIDER` (`bedrock`|`azure`), `LLM_MOCK_DELAY_MS`.

**Testing**

- Install: `pip install pytest`
- Run all tests: `pytest -q`
- Recommended flows:
  - Start proxy, then `python3 llm-cli.py --mock` to validate SSE rendering.
  - Use `/rag index naive <path>` and `/rag search "query"` to validate retrieval output.

**Security & Configuration**

- Do not commit secrets. Use `ai-server/.env` with `OAUTH_TOKEN_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `LLM_API_ENDPOINT`.
- Avoid logging credentials; remove OAuth debug prints.
- Default proxy binds to `127.0.0.1:8000`; keep localhost during development.

**RAG Limitations & Roadmap**

- Current limitations: character‑based chunking, TF‑IDF only, no incremental indexing, fixed `char_cap`.
- Potential enhancements: markdown/code‑aware chunking, stopwords/BM25, hybrid retrieval with embeddings, incremental reindex, `/rag config` to tune `k/chunk/overlap/char_cap`.
