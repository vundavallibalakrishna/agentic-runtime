import { ApprovalDetail } from "@/components/approvals/approval-detail";

export default async function ApprovalPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ApprovalDetail approvalId={id} />;
}
