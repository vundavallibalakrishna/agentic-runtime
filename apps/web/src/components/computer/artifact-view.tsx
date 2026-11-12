"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";

type FileRow = {
  id?: string;
  name?: string;
  mimeType?: string;
  preview?: { rows?: string[][] };
  text?: string;
};

const CODE = new Set(["text/plain", "text/markdown", "application/json", "text/x-python"]);
const PREVIEW_CHARS = 200_000;

function isMarkup(mime: string, name: string): boolean {
  return mime === "text/html" || mime === "image/svg+xml" || name.endsWith(".html");
}

function isCsv(mime: string, name: string): boolean {
  return mime === "text/csv" || mime === "application/csv" || name.endsWith(".csv");
}

function isCode(mime: string, name: string): boolean {
  return CODE.has(mime) || name.endsWith(".md") || name.endsWith(".py") || name.endsWith(".txt");
}

type Loaded = { text: string; state: "ready" | "loading" | "error" };

/** The text of a file the caller did not send. Read once from the file's own content. */
function useFileText(file: FileRow, wanted: boolean): Loaded {
  const given = file.text;
  const id = file.id ?? "";
  const [loaded, setLoaded] = useState<Loaded>({ text: "", state: "loading" });
  const fetching = wanted && given === undefined && id !== "";
  useEffect(() => {
    if (!fetching) {
      return;
    }
    let gone = false;
    setLoaded({ text: "", state: "loading" });
    void (async () => {
      try {
        const response = await fetch(`/api/v1/files/${id}/content`, { credentials: "include" });
        if (!response.ok) {
          throw new Error(response.statusText);
        }
        const body = await response.text();
        if (!gone) {
          setLoaded({ text: body.slice(0, PREVIEW_CHARS), state: "ready" });
        }
      } catch {
        if (!gone) {
          setLoaded({ text: "", state: "error" });
        }
      }
    })();
    return () => {
      gone = true;
    };
  }, [fetching, id]);
  return fetching ? loaded : { text: given ?? "", state: "ready" };
}

export function ArtifactView({ file }: { file: FileRow }) {
  const t = useTranslations("computer");
  const mime = file.mimeType ?? "";
  const name = file.name ?? "file";
  const markup = isMarkup(mime, name);
  const csv = isCsv(mime, name) && !file.preview?.rows;
  const code = isCode(mime, name);
  const image = mime.startsWith("image/") && mime !== "image/svg+xml";
  const { text, state } = useFileText(file, !image && (markup || csv || code));
  if (image && file.id) {
    return (
      <img
        alt={name}
        className="max-h-80 rounded-lg border border-[var(--border)]"
        src={`/api/v1/files/${file.id}/content`}
      />
    );
  }
  if (isCsv(mime, name) && file.preview?.rows) {
    return <Table rows={file.preview.rows} />;
  }
  if (mime.includes("spreadsheet") || name.endsWith(".xlsx")) {
    return <Table rows={file.preview?.rows ?? []} />;
  }
  if (mime === "application/pdf") {
    return (
      <a className="underline" href={`/api/v1/files/${file.id}/content`}>
        {name}
      </a>
    );
  }
  if (markup || csv || code) {
    if (state === "loading") {
      return (
        <div aria-busy="true" aria-label={t("previewLoading")} role="status">
          <Skeleton className="h-24 w-full" />
        </div>
      );
    }
    if (state === "error") {
      return (
        <p className="text-sm text-[var(--destructive)]" role="alert">
          {t("previewError")}
        </p>
      );
    }
    if (csv) {
      return <Table rows={parseCsv(text)} />;
    }
    if (!text) {
      return <p className="text-sm text-[var(--muted-foreground)]">{t("previewEmpty")}</p>;
    }
    return (
      <pre
        className="overflow-auto rounded-lg bg-[var(--muted)] p-3 font-mono text-xs"
        data-testid={markup ? "html-source" : "text-source"}
      >
        {text}
      </pre>
    );
  }
  return <p className="text-sm text-[var(--muted-foreground)]">{name}</p>;
}

function Table({ rows }: { rows: string[][] }) {
  const t = useTranslations("computer");
  if (rows.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">{t("noRows")}</p>;
  }
  return (
    <div className="overflow-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-left text-sm">
        <tbody>
          {rows.slice(0, 1000).map((row) => (
            <tr key={row.join("|")}>
              {row.map((cell) => (
                <td
                  className="border-b border-[var(--border)] px-2 py-1"
                  key={`${row.join("|")}-${cell}`}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function parseCsv(text: string): string[][] {
  if (!text.trim()) {
    return [];
  }
  return text
    .split("\n")
    .slice(0, 1000)
    .map((line) => line.split(",").map((cell) => cell.slice(0, 200)));
}
