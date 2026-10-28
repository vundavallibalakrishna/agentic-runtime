export function exactOrigins(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((origin): origin is string => {
    if (typeof origin !== "string" || /[\s;*\\]/.test(origin)) return false;
    try {
      const url = new URL(origin);
      return (
        url.origin === origin &&
        !url.username &&
        !url.password &&
        (url.protocol === "https:" ||
          (url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)))
      );
    } catch {
      return false;
    }
  });
}
