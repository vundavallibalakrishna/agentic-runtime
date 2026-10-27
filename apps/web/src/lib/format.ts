/** Group digits the same way in every browser locale. */
export function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

/** Costs arrive as millionths of the tenant's billing currency. */
export function formatCost(costMicros: number, currency = "INR"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 6,
  }).format(costMicros / 1_000_000);
}
