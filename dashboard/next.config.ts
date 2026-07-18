import fs from "node:fs";
import path from "node:path";
import type { NextConfig } from "next";

// Load the repo-root `.env` so dashboard server code sees the same
// DATABASE_URL / PACA_WIKI_DIR / OMLX_* the Python side reads. Next would
// normally only look for `dashboard/.env*`; this lightweight loader keeps
// the operator from maintaining two env files. Done inline (no dotenv dep)
// because the format we need is the trivial `KEY=value` subset.
function loadRepoEnv() {
  const envPath = path.resolve(process.cwd(), "..", ".env");
  let raw: string;
  try {
    raw = fs.readFileSync(envPath, "utf8");
  } catch {
    return;
  }
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq < 0) continue;
    const key = trimmed.slice(0, eq).trim();
    if (!key || key in process.env) continue;
    let value = trimmed.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    process.env[key] = value;
  }
}

loadRepoEnv();

const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
