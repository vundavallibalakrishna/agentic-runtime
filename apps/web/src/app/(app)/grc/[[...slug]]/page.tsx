import Link from "next/link";

export default function RetiredPackRoute() {
  return (
    <main className="p-6">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="mt-2 text-sm text-[var(--muted-foreground)]">
        This page is no longer part of the product.
      </p>
      <Link className="mt-4 inline-block text-sm underline" href="/chat">
        Back to chat
      </Link>
    </main>
  );
}
