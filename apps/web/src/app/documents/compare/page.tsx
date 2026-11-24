import { CompareScreen } from "@/components/documents/compare-screen";

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ left?: string; right?: string }>;
}) {
  const query = await searchParams;
  return <CompareScreen left={query.left ?? ""} right={query.right ?? ""} />;
}
