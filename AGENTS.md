# Repository Guidelines

## Project Structure & Module Organization
- `llm-cli.py`: Main Python CLI; streams SSE and renders live Markdown. Supports multiline input, tool calls, context, and RAG.
- `streaming_client.py`: SSE client + live renderer integration and tool execution wiring.
- `chat/`: Conversation/session orchestration (`conversation.py`, `session.py`), usage tracking, tool workflow glue.
- `context/`: Context manager for adding files/paths and formatting context blocks.
- `rag/`: Local RAG indexer/manager and context block formatting for grounded answers.
- `providers/`: Adapters mapping raw SSE to unified events (`bedrock`, `azure`).
- `tools/`: Built‑in tools and executor.
- `render/`: Rendering utilities (live and block‑buffered Markdown).
- `debug/`: Unified debug client (`debug.py`) replacing older `try.py`/`debug_cli.py`.
- `util/`: Prompt/input helpers, `@` file browser, command handlers.
- `ai-server/`: Node 18+ proxy exposing `/invoke`, `/mock`, `/healthz`; config via `.env`.
- `logs/`: Optional local logs/output.
- `tests/`: Python tests; run with `pytest`.

## Build, Test, and Development Commands
- Install Python deps: `pip install rich requests prompt-toolkit`
- Install dev deps (tests): `pip install pytest`
- Start proxy: `cd ai-server && npm ci && npm start` (dev: `npm run dev`)
- Client (provider): `python3 llm-cli.py --provider bedrock --url http://127.0.0.1:8000/invoke`
- Client (mock): `python3 llm-cli.py --url http://127.0.0.1:8000/mock` (no `--mock` flag on main CLI)
- CLI flags (main CLI): `--url`, `--provider {bedrock,azure}`. Toggle thinking, tools, context, and RAG via in‑REPL commands.
- Debug client (advanced): `python3 -m debug.debug [--http|--raw|--block|--live|--interactive] --provider {bedrock,azure} [--mock --mock-file file --mock-delay ms] [--model name --max-tokens N] [--timeout 60 --live-window 6]`
- Env (debug/mock/proxy): `LLM_MOCK_DELAY_MS` for mock delay; proxy uses `.env` (see below).
- Tests: `pytest -q`

## Coding Style & Naming Conventions
- Python: 4‑space indent, snake_case; CapWords for classes; add type hints where obvious. Keep functions small and streaming‑safe. Black‑compatible style.
- Node (proxy): 2‑space indent, camelCase, semicolons; target Node 18+ (`fetch`, `Readable.fromWeb`). Keep endpoints concise and non‑blocking.
- Layout: CLI helpers live in `debug/`; application modules in `chat/`, `context/`, `rag/`, `util/`; proxy code stays in `ai-server/`.

## Testing Guidelines
- Framework: `pytest` for Python. Prefer focused tests around stream parsing, rendering, providers, and helpers.
- Run: `pytest -q`. For proxy, consider `supertest` against `/invoke` and `/mock`.
- Validate flows: start proxy, then either use main CLI with `--url http://127.0.0.1:8000/mock` or the debug client with `--mock`.
- Debug SSE: `python3 -m debug.debug --http "your prompt"` or block‑buffered via `python3 -m debug.debug --block "your prompt"`.

## Commit & Pull Request Guidelines
- Commits: imperative, scoped summaries, small diffs.
  - Examples: `feat(cli): wire streaming_client`, `feat(debug): add --live mode`, `fix(proxy): handle upstream content-* headers)`
- PRs: include description, repro/validation steps, linked issues, and any config changes (`.env` keys/ports). Add before/after snippets for rendering changes.

## Security & Configuration Tips
- Do not commit secrets. Use `ai-server/.env` with `OAUTH_TOKEN_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `LLM_API_ENDPOINT` (optional `HOST`/`PORT`).
- Avoid logging credentials; remove OAuth debug prints.
- Default proxy binds `127.0.0.1:8000`; keep localhost during development.
- Providers: select via `--provider {bedrock,azure}` on CLI; set provider‑specific credentials via environment where applicable.
