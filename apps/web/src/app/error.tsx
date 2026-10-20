"use client";

export default function ErrorPage({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p>{error.message}</p>
      <button className="mt-4 underline" type="button" onClick={reset}>
        Try again
      </button>
    </div>
  );
}
