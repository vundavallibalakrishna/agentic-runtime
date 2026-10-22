type FileRow = {
  id?: string;
  name?: string;
  mimeType?: string;
  preview?: { rows?: string[][] };
  text?: string;
};

const CODE = new Set(["text/plain", "text/markdown", "application/json"]);

export function ArtifactView({ file }: { file: FileRow }) {
  const mime = file.mimeType ?? "";
  const name = file.name ?? "file";
  if (mime.startsWith("image/") && mime !== "image/svg+xml" && file.id) {
    return (
      <img
        alt={name}
        className="max-h-80 rounded-lg border border-[var(--border)]"
        src={`/api/v1/files/${file.id}/content`}
      />
    );
  }
  if (mime === "text/csv" || mime === "application/csv" || name.endsWith(".csv")) {
    return <Table rows={file.preview?.rows ?? parseCsv(file.text ?? "")} />;
  }
  if (mime.includes("spreadsheet") || name.endsWith(".xlsx")) {
    return <Table rows={file.preview?.rows ?? []} />;
  }
  if (mime === "text/html" || mime === "image/svg+xml" || name.endsWith(".html")) {
    return (
      <pre
        className="overflow-auto rounded-lg bg-[var(--muted)] p-3 font-mono text-xs"
        data-testid="html-source"
      >
        {file.text || "HTML is shown as source."}
      </pre>
    );
  }
  if (mime === "application/pdf") {
    return (
      <a className="underline" href={`/api/v1/files/${file.id}/content`}>
        {name}
      </a>
    );
  }
  if (CODE.has(mime) || name.endsWith(".md") || name.endsWith(".py")) {
    return (
      <pre className="overflow-auto rounded-lg bg-[var(--muted)] p-3 font-mono text-xs">
        {file.text}
      </pre>
    );
  }
  return <p className="text-sm text-[var(--muted-foreground)]">{name}</p>;
}

function Table({ rows }: { rows: string[][] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">No rows.</p>;
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
