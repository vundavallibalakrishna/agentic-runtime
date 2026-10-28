"use client";

import { useParams } from "next/navigation";

import { EvalsScreen } from "@/components/evals/evals-screen";

export default function AgentEvalsPage() {
  const params = useParams<{ id: string }>();
  return <EvalsScreen agentId={params.id} />;
}
