import { DocumentScreen } from "@/components/documents/screens";

export default async function DocumentPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  return <DocumentScreen documentId={documentId} />;
}
