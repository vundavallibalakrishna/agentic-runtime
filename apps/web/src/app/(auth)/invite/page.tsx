import { InviteForm } from "@/components/auth/invite-form";

export default async function InvitePage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const query = await searchParams;
  return <InviteForm token={query.token ?? ""} />;
}
