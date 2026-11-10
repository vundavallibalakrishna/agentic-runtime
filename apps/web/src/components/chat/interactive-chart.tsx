"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Bar, BarChart, Tooltip, XAxis, YAxis } from "recharts";

type ChartRow = { label: string; value: number };
type ChartSeries = { name: string; values: number[] };

const FILLS = ["currentColor"];

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

export function chartData(presentation: Record<string, unknown>): {
  data: Record<string, string | number>[];
  keys: string[];
} {
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
  return { data, keys };
}

type ChartFile = { id: string; name: string };

export function ChartView({
  presentation,
  files,
}: {
  presentation: Record<string, unknown>;
  files: ChartFile[];
}) {
  const t = useTranslations("chat");
  const { data, keys } = chartData(presentation);
  const image = files.find((file) => /\.(png|jpe?g|gif|webp)$/i.test(file.name));
  const [mode, setMode] = useState<"image" | "interactive">(image ? "image" : "interactive");
  const frame = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(520);

  useEffect(() => {
    const node = frame.current;
    if (!node || mode !== "interactive") return;
    const measure = () => setWidth(Math.max(280, Math.floor(node.clientWidth)));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [mode]);

  if (!image && data.length === 0) return null;
  return (
    <div className="mt-3" data-testid="chart-view">
      {image && data.length > 0 ? (
        <div className="mb-2 flex gap-2" role="tablist">
          <button
            aria-pressed={mode === "image"}
            className="rounded-md bg-[var(--muted)] px-2 py-1 text-xs"
            onClick={() => setMode("image")}
            type="button"
          >
            {t("chartImage")}
          </button>
          <button
            aria-pressed={mode === "interactive"}
            className="rounded-md bg-[var(--muted)] px-2 py-1 text-xs"
            onClick={() => setMode("interactive")}
            type="button"
          >
            {t("chartInteractive")}
          </button>
        </div>
      ) : null}
      {mode === "image" && image ? (
        <img
          alt={textTitle(presentation) || image.name}
          className="max-h-80 w-full rounded-lg border border-[var(--border)] object-contain"
          src={`/api/v1/files/${image.id}/content`}
        />
      ) : null}
      {mode === "interactive" && data.length > 0 && keys.length > 0 ? (
        <div
          className="w-full min-w-0 text-[var(--foreground)]"
          data-testid="interactive-chart"
          ref={frame}
        >
          <BarChart
            data={data}
            height={260}
            margin={{ bottom: 8, left: 0, right: 8, top: 8 }}
            width={width}
          >
            <XAxis
              dataKey="label"
              stroke="currentColor"
              tick={{ fill: "currentColor", fontSize: 12 }}
            />
            <YAxis stroke="currentColor" tick={{ fill: "currentColor", fontSize: 12 }} width={36} />
            <Tooltip />
            {keys.map((key, index) => (
              <Bar
                dataKey={key}
                fill={FILLS[index % FILLS.length]}
                isAnimationActive={false}
                key={key}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        </div>
      ) : null}
    </div>
  );
}

function textTitle(presentation: Record<string, unknown>): string {
  return typeof presentation.title === "string" ? presentation.title : "";
}
