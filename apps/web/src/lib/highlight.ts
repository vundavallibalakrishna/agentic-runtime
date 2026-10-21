import { createHighlighter, type Highlighter } from "shiki";

const languages = ["python", "typescript", "json", "bash", "markdown", "text"] as const;

let pending: Promise<Highlighter> | null = null;

function highlighter(): Promise<Highlighter> {
  pending ??= createHighlighter({
    themes: ["github-light", "github-dark"],
    langs: [...languages],
  });
  return pending;
}

export type Token = { content: string; color?: string };

export async function highlightCode(code: string, language: string): Promise<Token[][]> {
  const engine = await highlighter();
  const known = (
    languages.includes(language as (typeof languages)[number]) ? language : "text"
  ) as (typeof languages)[number];
  const dark = document.documentElement.classList.contains("dark");
  const rendered = engine.codeToTokens(code, {
    lang: known,
    theme: dark ? "github-dark" : "github-light",
  });
  return rendered.tokens.map((line) =>
    line.map((token) => ({ content: token.content, color: token.color })),
  );
}
