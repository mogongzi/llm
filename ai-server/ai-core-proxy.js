// Node 18+ (uses built-in fetch). Save as ai-core-proxy.js
require("dotenv").config();
const express = require("express");
const { Readable } = require("stream");
const { Buffer } = require("buffer");

const {
  OAUTH_TOKEN_URL,
  OAUTH_CLIENT_ID,
  OAUTH_CLIENT_SECRET,
  LLM_API_ENDPOINT,
  HOST = "127.0.0.1",
  PORT = "8000",
} = process.env;

console.log(LLM_API_ENDPOINT);

const app = express();
const fs = require("node:fs/promises");

app.get("/mock", async (req, res) => {
  const filePath = req.query.file || "mock.dat";

  // ⬇️ Random jitter between 20 and 100 ms
  const jitter = () => 20 + Math.floor(Math.random() * (100 - 50 + 1));

  // SSE headers
  res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders?.();

  let body;
  try {
    body = await fs.readFile(filePath, "utf8");
  } catch (e) {
    res.status(404);
    res.write(
      `data: ${JSON.stringify({
        error: "mock_file_not_found",
        message: e?.message || String(e),
        file: filePath,
      })}\n\n`
    );
    return res.end();
  }

  body = body.replace(/\r\n/g, "\n").trim();

  const frames = body.split(/\n\n+/);
  let idx = 0;
  let closed = false;
  req.on("close", () => (closed = true));

  const writeNext = () => {
    if (closed) return;
    if (idx >= frames.length) return res.end();

    const chunk = frames[idx++];
    if (chunk) res.write(chunk + "\n\n");

    setTimeout(writeNext, jitter());
  };

  writeNext();
});

// ---- tiny raw-body helper (no body-parser needed)
async function readBody(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  return chunks.length ? Buffer.concat(chunks) : null;
}

// --- token cache
let token = null;
let tokenExp = 0;
async function getToken() {
  if (token && Date.now() < tokenExp - 30_000) {
    console.log("Using cached access token");
    return token;
  }

  const params = new URLSearchParams({ grant_type: "client_credentials" });

  const basic = Buffer.from(
    `${OAUTH_CLIENT_ID}:${OAUTH_CLIENT_SECRET}`
  ).toString("base64");
  const resp = await fetch(OAUTH_TOKEN_URL, {
    method: "POST",
    headers: {
      authorization: `Basic ${basic}`,
      "content-type": "application/x-www-form-urlencoded",
    },
    body: params,
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`Token request failed (${resp.status}): ${text}`);
  }
  const data = await resp.json();
  token = data.access_token;
  const ttl = Number(data.expires_in ?? 300);
  tokenExp = Date.now() + ttl * 1000;
  console.log(`New access token: ${token} (expires in ${ttl} seconds)`);
  return token;
}

// === SINGLE ENDPOINT ===
app.post("/invoke", async (req, res) => {
  try {
    const access = await getToken();
    const bodyBuf = await readBody(req);

    // prepare headers
    const headers = new Headers();
    headers.set("authorization", `Bearer ${access}`);
    headers.set("AI-Resource-Group", "default");
    // preserve original content-type if present; default to JSON
    const contentType = req.headers["content-type"] || "application/json";
    headers.set(
      "content-type",
      Array.isArray(contentType) ? contentType.join(", ") : contentType
    );

    // forward to provider (always stream response back)
    const upstreamResp = await fetch(LLM_API_ENDPOINT, {
      method: "POST",
      headers,
      body: bodyBuf ?? undefined,
      duplex: "half", // enable streaming request bodies (Node fetch)
    });

    // mirror status and content-* headers
    res.status(upstreamResp.status);
    for (const [k, v] of upstreamResp.headers) {
      if (k.toLowerCase().startsWith("content-")) res.setHeader(k, v);
    }

    // stream response (SSE/chunked/JSON)
    if (!upstreamResp.body) return res.end();
    const nodeStream = Readable.fromWeb(upstreamResp.body);
    nodeStream.on("error", (e) => {
      if (!res.headersSent) res.status(502);
      try {
        res.end(`\n[proxy stream error] ${e?.message || e}`);
      } catch {}
    });
    nodeStream.pipe(res);
  } catch (e) {
    res
      .status(500)
      .json({ error: "proxy_error", message: e?.message || String(e) });
  }
});

app.listen(Number(PORT), HOST, () => {
  console.log(
    `SAP AI Core Service proxy listening at http://${HOST}:${PORT}/invoke`
  );
});
