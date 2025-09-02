# Repository Guidelines

## Project Structure & Module Organization
- `llm-cli.py`: Main Python CLI that streams SSE and renders live Markdown.
- `debug/`: Local tools — `try.py` (block-buffered Markdown), `stream_cli.py` (minimal), `debug_cli.py` (raw/HTTP), `richify.py` and `render.py` (Markdown renderers).
- `ai-server/`: Node 18+ proxy (`ai-core-proxy.js`) exposing `/invoke`, `/mock`, and `/healthz`; config via `.env`. Includes `mock.dat` for demo streams.
- `logs/`: Optional local logs/output; not required to run.

## Build, Test, and Development Commands
- Python deps: `pip install rich requests`
- Start proxy: `cd ai-server && npm ci && npm start` (use `npm run dev` for dev env)
- Client (mock): `python3 llm-cli.py --mock` (targets `/mock`)
- Client (provider): `python3 llm-cli.py --url http://127.0.0.1:8000/invoke`
- Flags: `--mock-file path/to/file.dat`, `--timeout 90`, `--live-window 6`, `--no-rule`; default URL can be set via `LLM_URL`.
- Useful debug:
  - Raw SSE lines: `python3 debug/debug_cli.py --http "your prompt"`
  - Minimal token stream: `python3 debug/stream_cli.py`
  - Block-buffered renderer: `python3 debug/try.py` (press `q` to abort)
  - Adjust repaint size: `llm-cli.py --live-window 6`

## Coding Style & Naming Conventions
- Python: 4-space indent, snake_case; CapWords for classes; add type hints where obvious. Keep functions small and streaming-safe. Follow Black-compatible style and short module docstrings.
- Node (proxy): 2-space indent, camelCase, semicolons; target Node 18+ (built-in `fetch`, `Readable.fromWeb`). Keep endpoints concise and non-blocking.
- Layout: CLI utilities live in `debug/`; proxy code stays in `ai-server/`.

## Testing Guidelines
- No formal tests yet. Validate via:
  - Mock flow: `npm start` in `ai-server`, then `python3 llm-cli.py --mock`.
  - Provider flow: set `ai-server/.env` and run with `--url`.
  - Inspect SSE structure with `--http`; expected types include `message_start`, `content_block_delta` with `text_delta`, and `message_stop`.
- If adding tests: prefer `pytest` for Python CLIs and fixtures for sample SSE; for proxy, consider `supertest` against `/invoke` and `/mock`.

## Commit & Pull Request Guidelines
- Commits: imperative, scoped summaries, small diffs.
  - Examples: `feat(cli): support --live-window`, `fix(proxy): handle upstream content-* headers`.
- PRs: include description, repro/validation steps, linked issues, and config changes (`.env` keys/ports). Add before/after snippets for rendering changes.

## Security & Configuration Tips
- Do not commit secrets. Use `ai-server/.env` with `OAUTH_TOKEN_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `LLM_API_ENDPOINT` (optional `HOST`/`PORT`).
- Avoid logging credentials; remove debug prints of OAuth values in the proxy before committing.
- Default proxy binds `127.0.0.1:8000`; scope to localhost during development.
