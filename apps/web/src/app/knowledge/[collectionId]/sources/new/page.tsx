import { SourceWizard } from "@/components/knowledge/source-wizard";

export default async function NewSourcePage({
  params,
}: {
  params: Promise<{ collectionId: string }>;
}) {
  const { collectionId } = await params;
  return <SourceWizard collectionId={collectionId} />;
}
