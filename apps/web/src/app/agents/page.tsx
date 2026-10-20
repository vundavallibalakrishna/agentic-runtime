import { AppShell } from "@/components/app-shell";
import { UiGallery } from "@/components/ui-gallery";

export default function AgentsPage() {
  return (
    <AppShell>
      <h1 className="mb-4 text-2xl font-semibold">Agents</h1>
      <UiGallery />
    </AppShell>
  );
}
