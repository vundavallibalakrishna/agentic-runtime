import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default async function LoginPage() {
  const t = await getTranslations("auth");
  return (
    <main className="mx-auto flex min-h-screen max-w-md items-center p-6">
      <Card className="w-full space-y-4 p-6">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p>{t("body")}</p>
        <form action="/api/v1/auth/dev-login" method="post">
          <Button type="submit">{t("devLogin")}</Button>
        </form>
        <Button asChild variant="outline">
          <a href="/api/v1/auth/login">{t("continue")}</a>
        </Button>
      </Card>
    </main>
  );
}
