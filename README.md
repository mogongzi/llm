**Overview**
- **Purpose:** Stream LLM responses over SSE and render Markdown cleanly in the terminal.
- **Clients:** `llm-cli.py` (polished live Markdown), `try.py` (block-buffered), `stream_cli.py` (minimal), `debug_cli.py` (raw/http debug).
- **Proxy:** `ai-core-proxy-server/ai-core-proxy.js` forwards to your provider with OAuth client credentials and exposes `/invoke` + `/mock`.

**Quick Start**
- **Prereqs:** Node 18+, Python 3.9+, `pip install rich requests`.
- **Install proxy deps:** `cd ai-core-proxy-server && npm ci`
- **Start proxy:** `npm start` (run from `ai-core-proxy-server`)
- **Run client (mock):** `python3 llm-cli.py --mock` (streams `ai-core-proxy-server/mock.dat`)
- **Run client (provider):** `python3 llm-cli.py --url http://127.0.0.1:8000/invoke`

**Mock Mode**
- **Start proxy:** `cd ai-core-proxy-server && npm start`
- **Stream mock data:** `python3 llm-cli.py --mock`
- **Notes:**
  - Hits `http://127.0.0.1:8000/mock` and streams frames from `mock.dat`.
  - Override file: `GET /mock?file=path/to/file.dat`.

**Provider Mode**
- **Configure env:** Create `ai-core-proxy-server/.env` with:
  - `OAUTH_TOKEN_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `LLM_API_ENDPOINT`
  - Optional: `HOST` (default `127.0.0.1`), `PORT` (default `8000`).
- **Start proxy:** `cd ai-core-proxy-server && npm start`
- **Use client:** `python3 llm-cli.py --url http://127.0.0.1:8000/invoke`

**CLIs**
- `llm-cli.py`: live Markdown with stable scrollback, headings, and code blocks.
- `try.py`: prints only completed blocks (paragraphs/fenced code) for clean output; abort with `q`.
- `stream_cli.py`: simple token printer.
- `debug_cli.py`: `--http` prints raw SSE lines; `--raw` prints raw text chunks.

 

**Troubleshooting**
- **Auth errors:** Check `.env` values and that OAuth client can request `client_credentials` tokens.
- **CORS/headers:** Proxy mirrors upstream `content-*` headers and streams body as-is.
- **Network timeouts:** Clients use a 60s timeout; adjust if your provider is slow.
- **Abort:** `Ctrl+C` anywhere; `q` during `try.py` streaming.
