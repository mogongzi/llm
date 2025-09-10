# Repository Guidelines

## Project Structure & Module Organization
- `llm-cli.py`: Main Python CLI; streams SSE and renders live Markdown. Supports multiline input and tool calls.
- `debug/`: Local CLI/renderer tools (`try.py`, `debug_cli.py`).
- `providers/`: Adapters mapping raw SSE to unified events (`bedrock`, `azure`).
- `tools/`: Built‑in tools and executor (calculator, weather, time).
- `render/`: Rendering utilities (live vs block‑buffered).
- `ai-server/`: Node 18+ proxy exposing `/invoke`, `/mock`, `/healthz`; config via `.env`.
- `logs/`: Optional local logs/output.
- `tests/`: Python tests; run with `pytest`.

## Build, Test, and Development Commands
- Install Python deps: `pip install rich requests prompt-toolkit`
- Install dev deps (tests): `pip install pytest`
- Start proxy: `cd ai-server && npm ci && npm start` (dev: `npm run dev`)
- Client (mock): `python3 llm-cli.py --mock` (targets `/mock`)
- Client (provider): `python3 llm-cli.py --provider bedrock --url http://127.0.0.1:8000/invoke`
- Flags: `--model`, `--max-tokens 4096`, `--mock-file`, `--mock-delay`, `--timeout 90`, `--live-window 6`, `--no-rule`
- Env overrides: `LLM_URL`, `LLM_PROVIDER`, `LLM_MOCK_DELAY_MS`
- Tests: `pytest -q`

## Coding Style & Naming Conventions
- Python: 4‑space indent, snake_case; CapWords for classes; add type hints where obvious. Keep functions small and streaming‑safe. Black‑compatible style.
- Node (proxy): 2‑space indent, camelCase, semicolons; target Node 18+ (`fetch`, `Readable.fromWeb`). Keep endpoints concise and non‑blocking.
- Layout: CLI helpers live in `debug/`; proxy code stays in `ai-server/`.

## Testing Guidelines
- Framework: `pytest` for Python. Prefer focused tests around stream parsing and rendering.
- Run: `pytest -q`. For proxy, consider `supertest` against `/invoke` and `/mock`.
- Validate flows: start proxy, then `python3 llm-cli.py --mock`; or set `ai-server/.env` and run with `--provider` and `--url`.
- Debug SSE: `python3 debug/debug_cli.py --http "your prompt"` or try block‑buffered renderer via `python3 debug/try.py`.

## Commit & Pull Request Guidelines
- Commits: imperative, scoped summaries, small diffs.
  - Examples: `feat(cli): support --live-window`, `fix(proxy): handle upstream content-* headers)`
- PRs: include description, repro/validation steps, linked issues, and any config changes (`.env` keys/ports). Add before/after snippets for rendering changes.

## Security & Configuration Tips
- Do not commit secrets. Use `ai-server/.env` with `OAUTH_TOKEN_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `LLM_API_ENDPOINT` (optional `HOST`/`PORT`).
- Avoid logging credentials; remove OAuth debug prints.
- Default proxy binds `127.0.0.1:8000`; keep localhost during development.
- Providers: select via `--provider {bedrock,azure}` or `LLM_PROVIDER`.
