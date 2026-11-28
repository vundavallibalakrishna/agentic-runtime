import { sameDataValue } from "@/lib/format";

export type Gate = {
  required: boolean;
  minPassRate: number;
  maxRegressionPct: number;
  mustPassTags: string[];
  [key: string]: unknown;
};
export type Suite = {
  id: string;
  name: string;
  description: string;
  kind: string;
  caseCount: number;
  agent: { id: string; name?: string } | null;
  gate: Gate;
  lastRun: { id: string; status: string; passRate?: number | null } | null;
};
const text = (value: unknown): value is string =>
  typeof value === "string" && Boolean(value.trim());
const finite = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);
export const gateFields = ["required", "minPassRate", "maxRegressionPct", "mustPassTags"];
export function suiteValid(value: unknown, agentId?: string): value is Suite {
  if (!value || typeof value !== "object") return false;
  const row = value as Suite,
    gate = row.gate;
  return (
    text(row.id) &&
    text(row.name) &&
    typeof row.description === "string" &&
    text(row.kind) &&
    Number.isSafeInteger(row.caseCount) &&
    row.caseCount >= 0 &&
    (row.agent === null ||
      Boolean(
        row.agent &&
          text(row.agent.id) &&
          (row.agent.name == null || typeof row.agent.name === "string"),
      )) &&
    (!agentId || row.agent?.id === agentId) &&
    Boolean(
      gate &&
        typeof gate === "object" &&
        !Array.isArray(gate) &&
        typeof gate.required === "boolean" &&
        finite(gate.minPassRate) &&
        finite(gate.maxRegressionPct) &&
        Array.isArray(gate.mustPassTags) &&
        gate.mustPassTags.every((value) => typeof value === "string"),
    ) &&
    (row.lastRun === null ||
      Boolean(
        row.lastRun &&
          text(row.lastRun.id) &&
          text(row.lastRun.status) &&
          (row.lastRun.passRate == null ||
            (finite(row.lastRun.passRate) &&
              row.lastRun.passRate >= 0 &&
              row.lastRun.passRate <= 1)),
      ))
  );
}
export function suitesFrom(
  page: { items?: unknown },
  agentId: string | undefined,
  message: string,
): Suite[] {
  if (
    !Array.isArray(page?.items) ||
    !page.items.every((value) => suiteValid(value, agentId)) ||
    new Set(page.items.map((value) => (value as Suite).id)).size !== page.items.length
  )
    throw new Error(message);
  return page.items as Suite[];
}
/** Shift the number's decimal representation without a floating-point percentage multiply/divide. */
function decimalShift(value: string, places: number): string {
  const [coefficient = "", power = "0"] = value.toLowerCase().split("e"),
    negative = coefficient.startsWith("-"),
    unsigned = coefficient.replace(/^[+-]/, "");
  const [whole = "", fraction = ""] = unsigned.split("."),
    digits = whole + fraction,
    point = whole.length + Number(power) + places;
  let result =
    point <= 0
      ? `0.${"0".repeat(-point)}${digits}`
      : point >= digits.length
        ? digits + "0".repeat(point - digits.length)
        : `${digits.slice(0, point)}.${digits.slice(point)}`;
  const [integer = "", decimal = ""] = result.split(".");
  result =
    (integer.replace(/^0+/, "") || "0") +
    (decimal.replace(/0+$/, "") ? `.${decimal.replace(/0+$/, "")}` : "");
  return negative && result !== "0" ? `-${result}` : result;
}
export const fromRate = (value: number) => decimalShift(String(value), 2);
export function toRate(value: string): number | null {
  const normalized = value.trim();
  if (!/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(normalized)) return null;
  const percent = Number(normalized);
  if (!Number.isFinite(percent) || percent < 0 || percent > 100) return null;
  const rate = Number(decimalShift(normalized, -2));
  return fromRate(rate) === decimalShift(normalized, 0) ? rate : null;
}
export function decimalNumber(value: string): number | null {
  const normalized = value.trim();
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(normalized)) return null;
  const number = Number(normalized);
  if (!Number.isFinite(number)) return null;
  if (number === 0) return /[1-9]/.test(normalized.split(/[eE]/)[0] ?? "") ? null : 0;
  return decimalShift(String(number), 0) === decimalShift(normalized, 0) ? number : null;
}
export function matchesSuite(
  saved: Suite,
  body: Record<string, unknown>,
  original: Suite | null,
  agentId?: string,
): boolean {
  return (
    (!original || saved.id === original.id) &&
    saved.agent?.id === (original?.agent?.id ?? agentId ?? undefined) &&
    Object.entries(body).every(([key, value]) =>
      key === "agentId"
        ? (saved.agent?.id ?? null) === value
        : key === "gate"
          ? Boolean(
              value &&
                typeof value === "object" &&
                Object.entries(value as Record<string, unknown>).every(([field, expected]) =>
                  sameDataValue(saved.gate[field], expected),
                ),
            )
          : sameDataValue(saved[key as keyof Suite], value),
    )
  );
}
export const sameSuite = (left: Suite, right: Suite) =>
  left.id === right.id &&
  left.name === right.name &&
  left.description === right.description &&
  left.kind === right.kind &&
  left.agent?.id === right.agent?.id &&
  sameDataValue(left.gate, right.gate);
