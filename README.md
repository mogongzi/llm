**Overview**

- **Purpose:** Stream LLM responses over SSE and render Markdown cleanly in the terminal.
- **Clients:** `llm-cli.py` (polished live Markdown), `debug/try.py` (block-buffered), `debug/stream_cli.py` (minimal), `debug/debug_cli.py` (raw/http debug).
- **Proxy:** `ai-server/ai-core-proxy.js` forwards to your provider with OAuth client credentials and exposes `/invoke`, `/mock`, and `/healthz`.

**Quick Start**

- **Prerequisites:** Node 18+, Python 3.9+, `pip install rich requests`.
- **Install proxy deps:** `cd ai-server && npm ci`
- **Start proxy:** `npm start` (run from `ai-server`)
- **Run client (mock):** `python3 llm-cli.py --mock` (streams `ai-server/mock.dat`)
- **Run client (provider):** `python3 llm-cli.py --url http://127.0.0.1:8000/invoke`
- **Useful flags:** `--mock-file path/to/file.dat`, `--timeout 90`, `--live-window 6`, `--no-rule`

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

- `llm-cli.py`: live Markdown with stable scroll back, headings, and code blocks. Respects `LLM_URL` env var.
- `debug/try.py`: prints only completed blocks (paragraphs/fenced code) for clean output; abort with `q`.
- `debug/stream_cli.py`: simple token printer.
- `debug/debug_cli.py`: `--http` prints raw SSE lines; `--raw` prints raw text chunks.

**Troubleshooting**

- **Auth errors:** Check `.env` values and that OAuth client can request `client_credentials` tokens.
- **CORS/headers:** Proxy mirrors upstream `content-*` headers and streams body as-is.
- **Network timeouts:** Clients use a 60s timeout; adjust if your provider is slow.
- **Abort:** `Ctrl+C` anywhere; `q` during `try.py` streaming.
