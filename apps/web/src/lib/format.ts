/** Group digits the same way in every browser locale. */
export function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}
