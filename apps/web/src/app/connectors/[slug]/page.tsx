import { ConnectorsScreen } from "@/components/connectors/connectors-screen";

export default async function ConnectorDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <ConnectorsScreen slug={slug} />;
}
