import { PackFrame } from "@/components/packs/pack-frame";

export default async function PackPage({ params }: { params: Promise<{ packId: string }> }) {
  const { packId } = await params;
  return <PackFrame packId={packId} />;
}
