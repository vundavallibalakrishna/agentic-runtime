import { CopyButton } from "@/components/common/copy-button";

/** A titled block of text to copy as it is: a command, a snippet, a key. */
export function CodeSample({ title, value }: { title: string; value: string }) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium">{title}</p>
        <CopyButton label={title} value={value} />
      </div>
      <pre className="mt-2 whitespace-pre-wrap break-all rounded-lg bg-[var(--muted)] p-3 text-xs">
        {value}
      </pre>
    </div>
  );
}
