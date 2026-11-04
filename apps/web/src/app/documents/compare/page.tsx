import { CompareScreen } from "@/components/documents/screens";

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ comparisonId?: string }>;
}) {
  const query = await searchParams;
  return <CompareScreen comparisonId={query.comparisonId ?? ""} />;
}
