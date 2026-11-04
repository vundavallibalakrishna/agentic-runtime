import { CheckScreen } from "@/components/documents/screens";

export default async function CheckPage({ params }: { params: Promise<{ checkId: string }> }) {
  const { checkId } = await params;
  return <CheckScreen checkId={checkId} />;
}
