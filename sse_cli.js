#!/usr/bin/env node
// Node 18+
// Usage:
//   node sse-cli.js                  # uses default URL & sample payload
//   node sse-cli.js -u http://127.0.0.1:8000/invoke -f body.json
//   echo '{"anthropic_version":"bedrock-2023-05-31","max_tokens":512,"messages":[{"role":"user","content":"hi"}]}' | node sse-cli.js -u http://127.0.0.1:8000/invoke

const { readFileSync } = require("fs");

function parseArgs(argv) {
  const args = { url: "http://127.0.0.1:8000/invoke", file: null };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if ((a === "-u" || a === "--url") && argv[i+1]) { args.url = argv[++i]; continue; }
    if ((a === "-f" || a === "--file") && argv[i+1]) { args.file = argv[++i]; continue; }
  }
  return args;
}

function getStdin() {
  return new Promise((resolve) => {
    let data = "";
    if (process.stdin.isTTY) return resolve("");
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", chunk => data += chunk);
    process.stdin.on("end", () => resolve(data));
  });
}

function samplePayload() {
  return {
    anthropic_version: "bedrock-2023-05-31",
    max_tokens: 2048,
    messages: [{ role: "user", content: "what is ArgoCD" }],
  };
}

// Process one SSE event payload (string after "data: ")
function handleEventJSON(s, state) {
  try {
    const evt = JSON.parse(s);

    // Common Anthropic/Bedrock stream events
    switch (evt.type) {
      case "message_start":
        state.started = true;
        return;
      case "content_block_delta":
        if (evt.delta?.type === "text_delta" && typeof evt.delta.text === "string") {
          process.stdout.write(evt.delta.text);
        }
        return;
      case "content_block_stop":
      case "message_delta":
        return;
      case "message_stop":
        // ensure trailing newline
        process.stdout.write("\n");
        return;
      default:
        // ignore other event types; uncomment to debug:
        // console.error("[event]", evt.type);
        return;
    }
  } catch (e) {
    // Not JSON? print raw for debugging
    // console.error("[non-json data]", s);
  }
}

(async () => {
  try {
    const { url, file } = parseArgs(process.argv);

    // Build body: file > stdin > sample
    let bodyStr = "";
    if (file) {
      bodyStr = readFileSync(file, "utf8");
    } else {
      const stdin = await getStdin();
      bodyStr = stdin.trim() ? stdin : JSON.stringify(samplePayload());
    }

    const resp = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: bodyStr,
      // duplex enables streaming request bodies; harmless here but ok to include
      duplex: "half",
    });

    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      console.error(`[HTTP ${resp.status}] ${text}`);
      process.exit(1);
    }

    // If server is not streaming (returns a single JSON), just print it and exit
    if (!resp.body || typeof resp.body.getReader !== "function") {
      const t = await resp.text();
      console.log(t);
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    const state = { started: false };

    // SSE frames are typically separated by \n\n; each line starts with "data: "
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      // handle line-by-line; split conservatively on single newlines
      let idx;
      while ((idx = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, idx).trimEnd();
        buf = buf.slice(idx + 1);

        // Only handle "data: ..." lines
        if (line.startsWith("data:")) {
          const payload = line.slice(5).trimStart();
          // Special terminator some APIs use:
          if (payload === "[DONE]") { process.stdout.write("\n"); break; }
          handleEventJSON(payload, state);
        }
      }
    }

    // Flush any trailing JSON (in case last chunk didn't end with newline)
    const trailing = buf.trim();
    if (trailing.startsWith("data:")) {
      handleEventJSON(trailing.slice(5).trimStart(), {});
    }
  } catch (err) {
    console.error("[client error]", err && err.message ? err.message : err);
    process.exit(1);
  }
})();

