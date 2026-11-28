import { sameDataValue } from "@/lib/format";

export type SavedCase = {
  id: string;
  suiteId: string;
  name: string;
  input: { messages: string[] };
  assertions: Record<string, unknown>[];
};

const text = (value: unknown): value is string =>
  typeof value === "string" && Boolean(value.trim());
export function caseValid(value: unknown, suiteId: string): value is SavedCase {
  if (!value || typeof value !== "object") return false;
  const row = value as SavedCase;
  return (
    text(row.id) &&
    row.suiteId === suiteId &&
    text(row.name) &&
    Boolean(
      row.input &&
        Array.isArray(row.input.messages) &&
        row.input.messages.every((value) => typeof value === "string"),
    ) &&
    Array.isArray(row.assertions) &&
    row.assertions.length > 0 &&
    row.assertions.every(
      (value) => value && typeof value === "object" && !Array.isArray(value) && text(value.type),
    )
  );
}
export function sameCase(left: SavedCase, right: SavedCase) {
  return (
    left.id === right.id &&
    left.suiteId === right.suiteId &&
    left.name === right.name &&
    sameDataValue(left.input, right.input) &&
    sameDataValue(left.assertions, right.assertions)
  );
}
export function casesFrom(
  page: { items?: unknown },
  destination: string,
  message: string,
): SavedCase[] {
  if (
    !Array.isArray(page?.items) ||
    !page.items.every((value) => caseValid(value, destination)) ||
    new Set(page.items.map((value) => (value as SavedCase).id)).size !== page.items.length
  )
    throw new Error(message);
  return page.items as SavedCase[];
}
