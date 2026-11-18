/** API origin for this process, read when a request arrives.

Compose sets ``API_PROXY_URL`` at container start. A build does not see it, so
nothing here is captured while the image is built. ``AR_API_URL`` is the same
origin when the proxy variable is unset. A bare port uses loopback, which is
what ``next dev`` on the host talks to.
*/
export function apiOrigin(): string {
  const explicit = read("API_PROXY_URL") || read("AR_API_URL");
  if (explicit) {
    return explicit.replace(/\/$/, "");
  }
  const port = read("AR_API_PORT") || read("AR_PORT") || "8000";
  return `http://127.0.0.1:${port}`;
}

function read(name: string): string {
  const value = process.env[name];
  return typeof value === "string" ? value.trim() : "";
}
