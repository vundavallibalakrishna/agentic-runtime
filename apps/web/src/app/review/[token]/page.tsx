import { ReviewForm } from "./review-form";

// The token is a credential. Do not cache one link's page under its URL.
export const dynamic = "force-dynamic";

export default async function ReviewPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <ReviewForm token={token} />;
}
