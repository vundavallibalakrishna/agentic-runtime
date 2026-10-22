import { api } from "@/lib/api";

export async function confirmStepUp(): Promise<void> {
  await api("/api/v1/auth/step-up", {
    method: "POST",
    body: JSON.stringify({ confirmed: true }),
  });
}
