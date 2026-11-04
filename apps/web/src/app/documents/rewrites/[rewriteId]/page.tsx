import { RewriteScreen } from "@/components/documents/screens";

export default async function RewritePage({ params }: { params: Promise<{ rewriteId: string }> }) {
  const { rewriteId } = await params;
  return <RewriteScreen rewriteId={rewriteId} />;
}
