import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

function repoRoot(): string {
  let current = process.cwd();
  for (let depth = 0; depth < 6; depth += 1) {
    if (existsSync(resolve(current, "compose.yaml"))) {
      return current;
    }
    const parent = dirname(current);
    if (parent === current) {
      break;
    }
    current = parent;
  }
  return process.cwd();
}

/** Root `.env` value, with the process environment winning. */
export function rootEnv(name: string): string | undefined {
  const fromProcess = process.env[name];
  if (fromProcess) {
    return fromProcess;
  }
  const path = resolve(repoRoot(), ".env");
  if (!existsSync(path)) {
    return undefined;
  }
  for (const line of readFileSync(path, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) {
      continue;
    }
    const separator = trimmed.indexOf("=");
    if (trimmed.slice(0, separator).trim() !== name) {
      continue;
    }
    return trimmed.slice(separator + 1).trim();
  }
  return undefined;
}

export const apiPort = rootEnv("AR_PORT") ?? "8000";
export const webPort = rootEnv("AR_WEB_HOST_PORT") ?? "3000";
export const apiProxyUrl = rootEnv("API_PROXY_URL") ?? `http://127.0.0.1:${apiPort}`;
