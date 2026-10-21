export function PageHeader({ title, body }: { title: string; body: string }) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-medium tracking-tight">{title}</h1>
      <p className="mt-2 max-w-2xl text-[15px] text-[var(--muted-foreground)]">{body}</p>
    </header>
  );
}
