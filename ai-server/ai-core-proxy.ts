// Node 22+ with native TypeScript support
import "dotenv/config";
import express, { type Request, type Response } from "express";
import { Readable } from "stream";
import { Buffer } from "buffer";
import { promises as fs } from "node:fs";

interface EnvConfig {
  OAUTH_TOKEN_URL: string;
  OAUTH_CLIENT_ID: string;
  OAUTH_CLIENT_SECRET: string;
  LLM_API_ENDPOINT: string;
  HOST: string;
  PORT: string;
}

const {
  OAUTH_TOKEN_URL,
  OAUTH_CLIENT_ID,
  OAUTH_CLIENT_SECRET,
  LLM_API_ENDPOINT,
  HOST = "127.0.0.1",
  PORT = "8000",
} = process.env as EnvConfig;

// ANSI color helpers to distinguish request/response logs in the console
const COLOR_RESET = "\x1b[0m";
const COLOR_REQUEST = "\x1b[36m"; // cyan
const COLOR_RESPONSE = "\x1b[32m"; // green
const COLOR_INFO = "\x1b[32m"; // green
const COLOR_URL = "\x1b[33m"; // yellow

const logRequest = (message: unknown) => {
  console.log(`${COLOR_REQUEST}${String(message)}${COLOR_RESET}`);
};

const logResponse = (message: unknown) => {
  console.log(`${COLOR_RESPONSE}${String(message)}${COLOR_RESET}`);
};

const logInfo = (message: unknown, highlight?: string) => {
  if (highlight) {
    console.log(
      `${COLOR_INFO}${String(message)}${COLOR_URL}${highlight}${COLOR_RESET}`,
    );
    return;
  }
  console.log(`${COLOR_INFO}${String(message)}${COLOR_RESET}`);
};

console.log(LLM_API_ENDPOINT);

const app = express();

interface MockParams {
  file?: string;
  delay_ms?: number | string;
  delay?: number | string;
}

app.post("/mock", async (req: Request, res: Response) => {
  let params: MockParams = {};
  try {
    const bodyBuf = await readBody(req);
    if (bodyBuf && bodyBuf.length) {
      params = JSON.parse(bodyBuf.toString("utf8"));
    }
  } catch (e: unknown) {
    const error = e as Error;
    return res.status(400).json({
      error: "mock_invalid_body",
      message: error?.message || String(e),
    });
  }

  const pickString = (value: unknown): string | undefined => {
    if (Array.isArray(value)) {
      return value.length ? String(value[0]) : undefined;
    }
    return typeof value === "string" && value.trim() ? value.trim() : undefined;
  };

  const pickDelay = (value: unknown): number | undefined => {
    if (Array.isArray(value)) value = value[0];
    if (value === undefined || value === null || value === "") return undefined;
    const num = Number(value);
    return Number.isFinite(num) ? Math.max(0, num) : undefined;
  };

  const filePath =
    pickString(params.file) || pickString(req.query?.file) || "mock.dat";
  const delayMs =
    pickDelay(params.delay_ms ?? params.delay) ??
    pickDelay(req.query?.delay_ms ?? req.query?.delay) ??
    pickDelay(process.env.LLM_MOCK_DELAY_MS) ??
    0;

  // Random jitter between 20 and 100 ms
  const jitter = () => 20 + Math.floor(Math.random() * (100 - 50 + 1));

  // SSE headers
  res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders?.();

  let body;
  try {
    body = await fs.readFile(filePath, "utf8");
  } catch (e: unknown) {
    const error = e as Error;
    res.status(404);
    res.write(
      `data: ${JSON.stringify({
        error: "mock_file_not_found",
        message: error?.message || String(e),
        file: filePath,
      })}\n\n`,
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

  // Optional startup delay before first chunk to let clients show spinners
  console.log(`Debugging... ${delayMs} ms initial delay`);
  if (delayMs > 0) setTimeout(writeNext, delayMs);
  else writeNext();
});

// ---- tiny raw-body helper (no body-parser needed)
async function readBody(req: Request): Promise<Buffer | null> {
  const chunks: Buffer[] = [];
  for await (const c of req) chunks.push(c);
  return chunks.length ? Buffer.concat(chunks) : null;
}

// --- token cache
interface TokenResponse {
  access_token: string;
  expires_in?: number;
}

let token: string | null = null;
let tokenExp: number = 0;

async function getToken(): Promise<string> {
  if (token && Date.now() < tokenExp - 30_000) {
    console.log("Using cached access token");
    return token;
  }

  const params = new URLSearchParams({ grant_type: "client_credentials" });

  const basic = Buffer.from(
    `${OAUTH_CLIENT_ID}:${OAUTH_CLIENT_SECRET}`,
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
  const data = (await resp.json()) as TokenResponse;
  token = data.access_token;
  const ttl = Number(data.expires_in ?? 300);
  tokenExp = Date.now() + ttl * 1000;
  console.log(`New access token: ${token} (expires in ${ttl} seconds)`);
  return token;
}

// === SINGLE ENDPOINT ===
app.post("/invoke", async (req: Request, res: Response) => {
  try {
    const access = await getToken();
    const bodyBuf = await readBody(req);

    // Print received request to console for debugging
    if (bodyBuf) {
      try {
        const requestData = JSON.parse(bodyBuf.toString());
        logRequest("==== Received Request ====");
        logRequest(JSON.stringify(requestData, null, 2));
        logRequest("=======================");
      } catch (e: unknown) {
        logRequest("==== Raw Request Body ====");
        logRequest(bodyBuf.toString());
        logRequest("=======================");
      }
    }

    // prepare headers
    const headers = new Headers();
    headers.set("authorization", `Bearer ${access}`);
    headers.set("AI-Resource-Group", "default");
    // preserve original content-type if present; default to JSON
    const contentType = req.headers["content-type"] || "application/json";
    headers.set(
      "content-type",
      Array.isArray(contentType) ? contentType.join(", ") : contentType,
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

    // Log response chunks to console
    logResponse("==== API Response ====");
    nodeStream.on("data", (chunk) => {
      logResponse(chunk.toString());
    });
    logResponse("==========================");

    nodeStream.on("error", (e: Error) => {
      if (!res.headersSent) res.status(502);
      try {
        res.end(`\n[proxy stream error] ${e?.message || e}`);
      } catch {}
    });
    nodeStream.pipe(res);
  } catch (e: unknown) {
    const error = e as Error;
    res
      .status(500)
      .json({ error: "proxy_error", message: error?.message || String(e) });
  }
});

app.listen(Number(PORT), HOST, () => {
  logInfo(
    "SAP AI Core Service proxy listening at ",
    `http://${HOST}:${PORT}/invoke`,
  );
});
