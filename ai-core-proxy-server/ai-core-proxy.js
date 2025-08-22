// Node 18+ (uses built-in fetch). Save as oauth-proxy-v2.js
const express = require("express");
const { Readable } = require("stream");
const { Buffer } = require("buffer");

const OAUTH_TOKEN_URL =
  "https://1mjnm8bjbc0q82d3.authentication.eu12.hana.ondemand.com/oauth/token"; // e.g. https://auth.example.com/oauth/token
const OAUTH_CLIENT_ID =
  "sb-26a94bff-c4ed-4d73-b7f9-c6216d3a21e3!b1362961|xsuaa_std!b318061";
const OAUTH_CLIENT_SECRET =
  "81cd60f9-5e3c-4985-bf8c-8dd8f619c527$k4Vc1uGyuatFWWavB9MiJaVD8XzINgculKRFmXjiWpA=";
const LLM_API_ENDPOINT =
  "https://api.ai.intprod-eu12.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d69942a0cb0b7e3f/invoke-with-response-stream";
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
    `AI Core Serivce proxy listening at http://${HOST}:${PORT}/invoke`
  );
});
