import { api } from "@/lib/api";

/**
 * The model aliases an agent can answer with. Only a chat model can answer, so embedding
 * and rerank aliases are left out. A failed read gives an empty list; the caller keeps the
 * value it already has.
 */
export async function chatAliases(): Promise<string[]> {
  try {
    const page = await api<{ items?: { alias?: unknown; kind?: unknown }[] }>(
      "/api/v1/model-aliases",
    );
    return Array.from(
      new Set(
        (page.items ?? [])
          .filter((row) => String(row.kind ?? "chat") === "chat")
          .map((row) => String(row.alias ?? ""))
          .filter((alias) => alias.length > 0),
      ),
    );
  } catch {
    return [];
  }
}
