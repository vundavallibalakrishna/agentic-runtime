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

// The light theme's colours that are too faint on the code block's background to meet
// 4.5:1, each with the nearest shade that does.
const readableLight: Record<string, string> = {
  "#D73A49": "#B42334",
  "#E36209": "#A04100",
  "#22863A": "#1A6B2E",
  "#6A737D": "#57606A",
};

function readableColor(color: string | undefined, dark: boolean): string | undefined {
  if (!color || dark) {
    return color;
  }
  return readableLight[color.toUpperCase()] ?? color;
}

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
    line.map((token) => ({
      content: token.content,
      color: readableColor(token.color, dark),
    })),
  );
}
