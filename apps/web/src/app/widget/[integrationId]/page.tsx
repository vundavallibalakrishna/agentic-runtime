import { WidgetChat } from "@/components/widget/widget-chat";

export default async function WidgetPage({
  params,
}: {
  params: Promise<{ integrationId: string }>;
}) {
  const { integrationId } = await params;
  return <WidgetChat integrationId={integrationId} />;
}
