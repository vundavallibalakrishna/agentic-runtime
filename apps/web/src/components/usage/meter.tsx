export function Meter({ used, limit }: { used: number; limit: number }) {
  const max = Math.max(limit, 1);
  const value = limit <= 0 ? max : Math.min(used, max);
  return (
    <progress
      aria-label={`${used} of ${limit}`}
      className="h-2 w-full appearance-none overflow-hidden rounded-full bg-[var(--muted)] accent-[var(--foreground)] [&::-moz-progress-bar]:bg-[var(--foreground)] [&::-webkit-progress-bar]:bg-[var(--muted)] [&::-webkit-progress-value]:bg-[var(--foreground)]"
      max={max}
      value={value}
    />
  );
}
