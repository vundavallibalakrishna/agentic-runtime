import { CollectionScreen } from "@/components/knowledge/collection-screen";

export default async function CollectionPage({
  params,
}: {
  params: Promise<{ collectionId: string }>;
}) {
  const { collectionId } = await params;
  return <CollectionScreen collectionId={collectionId} />;
}
