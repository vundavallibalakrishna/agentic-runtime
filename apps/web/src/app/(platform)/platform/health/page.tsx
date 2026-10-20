import { getTranslations } from "next-intl/server";

export default async function PlatformHealthPage() {
  const t = await getTranslations("platform");
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-semibold">{t("healthTitle")}</h1>
      <p className="mt-2 text-sm text-[var(--muted)]">{t("healthBody")}</p>
      <a className="mt-6 inline-block text-sm underline" href="/chat">
        {t("back")}
      </a>
    </main>
  );
}
