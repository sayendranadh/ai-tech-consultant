// Usage: npx tsx harness.ts <base_url> <bearer_token> <question>
// Prints JSON {ok, status_code?, body?, error?}. Exit 0 always.
import { KBClient } from "../src/kb/client.js";

const [baseUrl, token, question] = process.argv.slice(2);

try {
  const c = new KBClient({
    baseUrl,
    bearerToken: token,
    timeoutMs: 5000,
    maxRetries: 1,
    backoffBaseMs: 100,
  });
  const r = await c.query({ question });
  process.stdout.write(JSON.stringify({ ok: true, body: r }) + "\n");
  process.exit(0);
} catch (err) {
  const name = err && (err as any).constructor ? (err as any).constructor.name : "Error";
  const message = err && (err as any).message ? (err as any).message : String(err);
  process.stdout.write(JSON.stringify({ ok: false, error: name, message }) + "\n");
  process.exit(0);
}
