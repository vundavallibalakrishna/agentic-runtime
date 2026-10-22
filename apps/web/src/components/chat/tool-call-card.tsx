export function ToolCallCard({ call, label }: { call: Record<string, unknown>; label: string }) {
  const name = String(call.qualifiedName ?? call.qualified_name ?? "tool");
  const preview = String(call.resultPreview ?? call.result_preview ?? "");
  const approvalId = String(call.approvalId ?? call.approval_id ?? "");
  const waiting = String(call.status ?? "") === "awaiting_approval";
  const error = call.error;
  const connect =
    error && typeof error === "object"
      ? String(
          (error as { connectUrl?: string; connect_url?: string }).connectUrl ??
            (error as { connect_url?: string }).connect_url ??
            "",
        )
      : "";
  return (
    <section className="mt-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm">
      <p className="sr-only">{label}</p>
      <p className="font-medium">{name}</p>
      <p className="text-[var(--muted-foreground)]">{String(call.status ?? "")}</p>
      {preview ? <p className="mt-1 whitespace-pre-wrap">{preview}</p> : null}
      {waiting && approvalId ? (
        <a className="mt-2 inline-block underline" href={`/approvals/${approvalId}`}>
          Review approval
        </a>
      ) : null}
      {connect ? (
        <a className="mt-2 inline-block underline" href={connect}>
          Connect account
        </a>
      ) : null}
    </section>
  );
}
