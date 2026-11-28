/** Group digits the same way in every browser locale. */
export function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

/** Costs arrive as millionths of the tenant's billing currency. */
export function formatCost(costMicros: number, currency?: string): string {
  const code = currency?.trim().toUpperCase();
  // A tenant without a billing currency has a quantity, not a named currency.
  if (!code || !/^[A-Z]{3}$/.test(code)) {
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 6 }).format(
      costMicros / 1_000_000,
    );
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: code,
    maximumFractionDigits: 6,
  }).format(costMicros / 1_000_000);
}

/** Preserve structured returned values instead of rendering [object Object]. */
export function formatDataValue(value: unknown): string {
  return value == null
    ? ""
    : typeof value === "object"
      ? JSON.stringify(value, null, 2)
      : String(value);
}

/** Display an instant in the viewer's time zone, including its zone label. */
export function formatDateTime(value: string, locale?: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "long",
  }).format(date);
}

const CURRENCY_AMOUNT_PATTERN = "(?:[0-9]+(?:[.][0-9]{0,6})?|[.][0-9]{1,6})";
const currencyAmount = new RegExp(`^${CURRENCY_AMOUNT_PATTERN}$`);

/** Parse decimal currency into safe integer millionths without floating-point rounding. */
export function toMicros(value: string): number | null {
  const text = value.trim();
  if (!currencyAmount.test(text)) return null;
  const [whole = "", fraction = ""] = text.split(".");
  const integral = whole.replace(/^0+/, "") || "0";
  if (integral.length > String(Math.floor(Number.MAX_SAFE_INTEGER / 1_000_000)).length) return null;
  const micros = BigInt(integral) * 1_000_000n + BigInt(fraction.padEnd(6, "0"));
  return micros <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(micros) : null;
}

/** Exact form text for an integer currency amount; missing data remains blank. */
export function fromMicros(value: number | undefined): string {
  if (value === undefined) return "";
  if (!Number.isFinite(value) || !Number.isInteger(value)) return String(value);
  const amount = BigInt(value);
  const absolute = amount < 0n ? -amount : amount;
  const fraction = (absolute % 1_000_000n).toString().padStart(6, "0").replace(/0+$/, "");
  return `${amount < 0n ? "-" : ""}${absolute / 1_000_000n}${fraction ? `.${fraction}` : ""}`;
}
