// Node 18+ (uses built-in fetch). Save as oauth-proxy-v2.js
const express = require("express");
const { Readable } = require("stream");
const { Buffer } = require("buffer");

const OAUTH_TOKEN_URL = "https://doctranspoc.authentication.sap.hana.ondemand.com/oauth/token";     // e.g. https://auth.example.com/oauth/token
const OAUTH_CLIENT_ID = "sb-5dd63299-09d5-4591-a9e0-3522a2c9e913!b32119|xsuaa_std!b77089";
const OAUTH_CLIENT_SECRET = "074c11e1-9a42-4da4-a3c6-0e3e9fce3450$6miA57s4EhBGHCT8aYuXSDMn1TRRV-gFv80PUOTdaEQ=";
//const LLM_API_ENDPOINT = "https://api.ai.internalprod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d1766de26a5952a5/invoke-with-response-stream";
const LLM_API_ENDPOINT = "https://api.ai.internalprod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d05cd4d1672689f5/invoke-with-response-stream";
const PORT = "8000";
const HOST = "127.0.0.1";

const app = express();

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
  if (token && Date.now() < tokenExp - 30_000) return token;

  const params = new URLSearchParams({ grant_type: "client_credentials" });

  const basic = Buffer.from(`${OAUTH_CLIENT_ID}:${OAUTH_CLIENT_SECRET}`).toString("base64");
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
  return token;
}

// Health (optional)
app.get("/healthz", (_req, res) => res.json({ ok: true }));

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
    headers.set("content-type", Array.isArray(contentType) ? contentType.join(", ") : contentType);

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
      try { res.end(`\n[proxy stream error] ${e?.message || e}`); } catch {}
    });
    nodeStream.pipe(res);
  } catch (e) {
    res.status(500).json({ error: "proxy_error", message: e?.message || String(e) });
  }
});

app.listen(Number(PORT), HOST, () => {
  console.log(`AI Core Serivce proxy listening at http://${HOST}:${PORT}/invoke`);
});