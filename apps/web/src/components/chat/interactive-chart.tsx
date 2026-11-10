"use client";

import { useTranslations } from "next-intl";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type ChartRow = { label: string; value: number };
type ChartSeries = { name: string; values: number[] };

const FILLS = ["var(--foreground)", "var(--muted-foreground)", "var(--primary)", "var(--accent)"];

function rowsOf(presentation: Record<string, unknown>): ChartRow[] {
  const raw = presentation.rows;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const row = item as { label?: unknown; value?: unknown };
      const value = Number(row.value);
      if (!Number.isFinite(value)) return null;
      return { label: String(row.label ?? ""), value };
    })
    .filter((item): item is ChartRow => item !== null);
}

function seriesOf(presentation: Record<string, unknown>): {
  categories: string[];
  series: ChartSeries[];
} {
  const categories = Array.isArray(presentation.categories)
    ? presentation.categories.map((item) => String(item))
    : [];
  const raw = presentation.series;
  const series = Array.isArray(raw)
    ? raw
        .map((item) => {
          if (!item || typeof item !== "object") return null;
          const row = item as { name?: unknown; values?: unknown };
          const values = Array.isArray(row.values)
            ? row.values.map((value) => Number(value)).filter((value) => Number.isFinite(value))
            : [];
          if (!values.length) return null;
          return { name: String(row.name ?? ""), values };
        })
        .filter((item): item is ChartSeries => item !== null)
    : [];
  return { categories, series };
}

/** The PNG is the record. This view uses the same rows the renderer drew. */
export function InteractiveChart({ presentation }: { presentation: Record<string, unknown> }) {
  const t = useTranslations("chat");
  const rows = rowsOf(presentation);
  const { categories, series } = seriesOf(presentation);
  const data = rows.length
    ? rows
    : categories.map((label, index) => {
        const point: Record<string, string | number> = { label };
        for (const item of series) point[item.name] = item.values[index] ?? 0;
        return point;
      });
  const keys = rows.length ? ["value"] : series.map((item) => item.name);
  if (!data.length || !keys.length) return null;
  return (
    <div className="mt-3" data-testid="interactive-chart">
      <p className="mb-1 text-xs text-[var(--muted-foreground)]">{t("interactiveChart")}</p>
      <div className="h-52 w-full">
        <ResponsiveContainer height="100%" width="100%">
          <BarChart data={data}>
            <XAxis
              dataKey="label"
              stroke="var(--muted-foreground)"
              tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            />
            <YAxis
              stroke="var(--muted-foreground)"
              tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
              width={40}
            />
            <Tooltip />
            {keys.map((key, index) => (
              <Bar
                dataKey={key}
                fill={FILLS[index % FILLS.length]}
                key={key}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
