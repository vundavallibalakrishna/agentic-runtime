"use client";

import { useTranslations } from "next-intl";

/** One statement the judge model checked, as the results endpoint returns it. */
export type JudgedItem = {
  kind?: string;
  statement?: string;
  verdict?: string;
  quote?: string;
  reason?: string;
};

type Score = {
  passed?: boolean;
  score?: number;
  detail?: string;
  verdict?: string;
  items?: JudgedItem[];
};

export type EvalResult = {
  passed?: boolean;
  outputText?: string;
  latencyMs?: number | null;
  case?: { id?: string; name?: string; tags?: string[] };
  scores?: Record<string, Score>;
};

function judged(result: EvalResult): JudgedItem[] {
  return Object.entries(result.scores ?? {})
    .filter(([key]) => key.startsWith("llmJudge"))
    .flatMap(([, score]) => score.items ?? []);
}

/**
 * The results of one eval run. A case judged by a model lists the facts its answer
 * missed and the claims it should not have made, with the answer's own words.
 */
export function EvalResults({ results }: { results: EvalResult[] }) {
  const t = useTranslations("evals");
  if (results.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">{t("noResults")}</p>;
  }
  const passed = results.filter((result) => result.passed).length;
  return (
    <div>
      <p className="mb-3 text-sm text-[var(--muted-foreground)]">
        {t("summary", { passed, total: results.length })}
      </p>
      <ul className="row-list">
        {results.map((result, index) => {
          const items = judged(result);
          const missed = items.filter((item) => item.kind === "must" && item.verdict !== "stated");
          const broken = items.filter(
            (item) => item.kind === "must_not" && item.verdict === "stated",
          );
          const unjudged = items.filter((item) => item.verdict === "failed");
          return (
            <li className="p-4 text-sm" key={result.case?.id ?? `${index}`}>
              <details>
                <summary className="cursor-pointer">
                  <span className="font-medium">{result.case?.name}</span>
                  {" · "}
                  {result.passed ? t("passed") : t("failed")}
                  {items.length > 0
                    ? ` · ${t("factsMet", {
                        met: items.filter((i) => i.kind === "must" && i.verdict === "stated")
                          .length,
                        total: items.filter((i) => i.kind === "must").length,
                      })}`
                    : ""}
                  {result.latencyMs != null ? ` · ${(result.latencyMs / 1000).toFixed(1)} s` : ""}
                </summary>
                <div className="mt-3 space-y-3">
                  {missed.length > 0 ? (
                    <div>
                      <h3 className="font-medium">{t("missed")}</h3>
                      <ul className="mt-1 list-disc pl-5">
                        {missed.map((item) => (
                          <li key={item.statement}>{item.statement}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {broken.length > 0 ? (
                    <div>
                      <h3 className="font-medium text-[var(--destructive)]">{t("forbidden")}</h3>
                      <ul className="mt-1 list-disc pl-5">
                        {broken.map((item) => (
                          <li key={item.statement}>
                            {item.statement}
                            {item.quote ? (
                              <q className="block text-[var(--muted-foreground)]">{item.quote}</q>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {unjudged.length > 0 ? (
                    <p className="text-[var(--muted-foreground)]">
                      {t("unjudged", { count: unjudged.length })}
                    </p>
                  ) : null}
                  <div>
                    <h3 className="font-medium">{t("answer")}</h3>
                    <p className="mt-1 whitespace-pre-wrap text-[var(--muted-foreground)]">
                      {result.outputText || t("noAnswer")}
                    </p>
                  </div>
                </div>
              </details>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
