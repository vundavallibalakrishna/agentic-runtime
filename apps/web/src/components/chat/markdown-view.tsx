"use client";

import DOMPurify from "dompurify";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

import { highlightCode, type Token } from "@/lib/highlight";

import "katex/dist/katex.min.css";

export function MarkdownView({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        components={{
          pre({ children }) {
            return <div className="contents">{children}</div>;
          },
          code({ className, children }) {
            const value = String(children ?? "").replace(/\n$/, "");
            if (!className) {
              return <code>{value}</code>;
            }
            return <CodeBlock className={className} value={value} />;
          },
        }}
        rehypePlugins={[rehypeKatex, rehypeSanitize]}
        remarkPlugins={[remarkGfm]}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

function CodeBlock({ className, value }: { className: string; value: string }) {
  const language = /language-(\w+)/.exec(className)?.[1] ?? "text";
  const [lines, setLines] = useState<Token[][]>([]);
  const [copied, setCopied] = useState(false);
  const [diagram, setDiagram] = useState(false);
  const diagramRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    if (language === "mermaid") {
      void import("mermaid").then(async (mod) => {
        mod.default.initialize({ startOnLoad: false, securityLevel: "strict" });
        const id = `mmd-${Math.random().toString(36).slice(2)}`;
        try {
          const rendered = await mod.default.render(id, value);
          if (!cancelled && diagramRef.current) {
            diagramRef.current.innerHTML = DOMPurify.sanitize(rendered.svg, {
              USE_PROFILES: { svg: true, svgFilters: true },
            });
            setDiagram(true);
          }
        } catch {
          if (!cancelled) {
            setDiagram(false);
          }
        }
      });
      return () => {
        cancelled = true;
      };
    }
    void highlightCode(value, language).then((next) => {
      if (!cancelled) {
        setLines(next);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [language, value]);

  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div className="relative">
      <button
        className="absolute right-2 top-2 rounded-md px-2 py-1 text-xs text-[var(--muted-foreground)] hover:bg-[var(--background)]"
        onClick={() => void copy()}
        type="button"
      >
        {copied ? "Copied" : "Copy"}
      </button>
      {language === "mermaid" ? (
        <div className="overflow-auto rounded-xl bg-[var(--muted)] p-3" ref={diagramRef} />
      ) : null}
      {language !== "mermaid" && lines.length > 0 ? (
        <pre>
          <code>
            {lines.map((line) => {
              const seen = new Map<string, number>();
              return (
                <span key={line.map((token) => token.content).join("")}>
                  {line.map((token) => {
                    const mark = `${token.content}-${token.color ?? ""}`;
                    const count = seen.get(mark) ?? 0;
                    seen.set(mark, count + 1);
                    return (
                      <span
                        key={`${mark}-${count}`}
                        style={token.color ? { color: token.color } : undefined}
                      >
                        {token.content}
                      </span>
                    );
                  })}
                  {"\n"}
                </span>
              );
            })}
          </code>
        </pre>
      ) : null}
      {language !== "mermaid" && lines.length === 0 ? (
        <pre>
          <code>{value}</code>
        </pre>
      ) : null}
      {language === "mermaid" && !diagram ? (
        <pre>
          <code>{value}</code>
        </pre>
      ) : null}
    </div>
  );
}
