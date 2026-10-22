import { RoutineDetail } from "@/components/routines/routine-detail";

export default async function RoutinePage({ params }: { params: Promise<{ routineId: string }> }) {
  const { routineId } = await params;
  return <RoutineDetail routineId={routineId} />;
}
