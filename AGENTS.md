# Repository Guidelines

## Project Structure & Module Organization
- `llm-cli.py`: Main Python CLI that streams SSE and renders live Markdown; supports multiline input and tool calls.
- `debug/`: Local tools — `try.py` (block‑buffered Markdown, Esc abort) and `debug_cli.py` (raw/HTTP). Older helpers like `stream_cli.py` and `richify.py` have been removed.
- `providers/`: Provider registry and adapters (`bedrock`, `azure`) mapping raw SSE → unified events.
- `tools/`: Built‑in tools and executor (calculator, weather, time) for Claude tool‑calling.
- `render/`: Rendering utilities (live vs block‑buffered Markdown).
- `ai-server/`: Node 18+ proxy (`ai-core-proxy.js`) exposing `/invoke`, `/mock`, and `/healthz`; config via `.env`. Includes `mock.dat` for demo streams.
- `logs/`: Optional local logs/output; not required to run.

## Build, Test, and Development Commands
- Python deps: `pip install rich requests prompt-toolkit`
- Start proxy: `cd ai-server && npm ci && npm start` (use `npm run dev` for dev env)
- Client (mock): `python3 llm-cli.py --mock` (targets `/mock`)
- Client (provider): `python3 llm-cli.py --provider bedrock --url http://127.0.0.1:8000/invoke`
- Flags: `--provider {bedrock,azure}`, `--model <name>`, `--max-tokens 4096`, `--mock-file path/to/file.dat`, `--mock-delay <ms>`, `--timeout 90`, `--live-window 6`, `--no-rule`.
  - Env: `LLM_URL` (default URL), `LLM_PROVIDER` (default provider), `LLM_MOCK_DELAY_MS` (mock stream delay override).
- Useful debug:
  - Raw SSE lines: `python3 debug/debug_cli.py --http "your prompt"`
  - Block‑buffered renderer: `python3 debug/try.py` (press `Esc` to abort)
  - Adjust repaint size: `llm-cli.py --live-window 6`
  - Spinner: CLI shows “Waiting for response…” until first token.

## CLI Shortcuts & Commands
- Multiline input: Enter=submit; Ctrl+J=newline; Up/Down navigate history.
- Abort/cancel: `Esc` during stream; `Esc`/Ctrl+C cancels input.
- Commands:
  - `/think` toggle reasoning mode (shows [ON] in prompt when enabled).
  - `/tools` toggle tool calling (calculator, weather, time).
  - `/clear` clear in‑memory chat history.

## Coding Style & Naming Conventions
- Python: 4-space indent, snake_case; CapWords for classes; add type hints where obvious. Keep functions small and streaming-safe. Follow Black-compatible style and short module docstrings.
- Node (proxy): 2-space indent, camelCase, semicolons; target Node 18+ (built-in `fetch`, `Readable.fromWeb`). Keep endpoints concise and non-blocking.
- Layout: CLI utilities live in `debug/`; proxy code stays in `ai-server/`.

## Testing Guidelines
- Python tests present (root and `tests/`). Run: `pytest -q`.
- Validate flows:
  - Mock: start proxy, then `python3 llm-cli.py --mock` (optionally `--mock-delay`/`--mock-file`).
  - Provider: set `ai-server/.env`, run with `--provider` and `--url`.
- Inspect raw SSE with `--http`. Provider adapters map to unified events: `model`, `thinking`, `text`, `tool_start`, `tool_input_delta`, `tool_ready`, `tokens`, `done`.
- For proxy tests, consider `supertest` against `/invoke` and `/mock`.

## Commit & Pull Request Guidelines
- Commits: imperative, scoped summaries, small diffs.
  - Examples: `feat(cli): support --live-window`, `fix(proxy): handle upstream content-* headers`.
- PRs: include description, repro/validation steps, linked issues, and config changes (`.env` keys/ports). Add before/after snippets for rendering changes.

## Security & Configuration Tips
- Do not commit secrets. Use `ai-server/.env` with `OAUTH_TOKEN_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `LLM_API_ENDPOINT` (optional `HOST`/`PORT`).
- Avoid logging credentials; remove debug prints of OAuth values in the proxy before committing.
- Default proxy binds `127.0.0.1:8000`; scope to localhost during development.
- Providers: use `bedrock` or `azure` via `--provider` or `LLM_PROVIDER`.
