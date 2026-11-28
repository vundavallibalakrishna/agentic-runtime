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

/** The scores of one case result. Only `llm_judge` scores carry judged statements. */
export type JudgedScores = Record<string, Score> | undefined;

function judged(scores: JudgedScores): JudgedItem[] {
  return Object.entries(scores ?? {})
    .filter(([key]) => key.startsWith("llmJudge"))
    .flatMap(([, score]) => (Array.isArray(score?.items) ? score.items : []));
}

/** How many of the facts a case must state its answer stated, or null when no model judged it. */
export function factsMet(scores: JudgedScores): { met: number; total: number } | null {
  const musts = judged(scores).filter((item) => item.kind === "must");
  if (musts.length === 0) return null;
  return { met: musts.filter((item) => item.verdict === "stated").length, total: musts.length };
}

/**
 * What the judge model found in one answer: the facts it missed, the claims it should not
 * have made (with the answer's own words) and the statements the judge could not decide.
 */
export function JudgedFindings({ scores }: { scores: JudgedScores }) {
  const t = useTranslations("evals");
  const items = judged(scores);
  const missed = items.filter((item) => item.kind === "must" && item.verdict !== "stated");
  const broken = items.filter((item) => item.kind === "must_not" && item.verdict === "stated");
  const unjudged = items.filter((item) => item.verdict === "failed");
  if (missed.length === 0 && broken.length === 0 && unjudged.length === 0) return null;
  return (
    <div className="mt-2 space-y-2" data-testid="judged-findings">
      {missed.length > 0 ? (
        <div>
          <h3 className="font-medium">{t("missed")}</h3>
          <ul className="mt-1 list-disc pl-5">
            {missed.map((item) => (
              <li className="break-words" key={item.statement}>
                {item.statement}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {broken.length > 0 ? (
        <div>
          <h3 className="font-medium text-[var(--destructive)]">{t("forbidden")}</h3>
          <ul className="mt-1 list-disc pl-5">
            {broken.map((item) => (
              <li className="break-words" key={item.statement}>
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
    </div>
  );
}
