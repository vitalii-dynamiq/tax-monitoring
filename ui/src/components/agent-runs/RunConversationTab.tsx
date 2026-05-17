import { useEffect, useState } from "react";
import Card from "../Card";
import TurnCard from "./TurnCard";
import { api, type AgentRunTurn, type MonitoringJob } from "../../lib/api";

interface RunConversationTabProps {
  jobId: number;
  job: MonitoringJob;
}

export default function RunConversationTab({ jobId, job }: RunConversationTabProps) {
  const [turns, setTurns] = useState<AgentRunTurn[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.monitoring
      .getJobTurns(jobId)
      .then((data) => !cancelled && setTurns(data))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (error) {
    return (
      <Card className="p-6 text-sm text-danger">
        Failed to load turns: {error}
      </Card>
    );
  }
  if (turns === null) {
    return <Card className="p-6 text-muted">Loading conversation…</Card>;
  }
  if (turns.length === 0) {
    return (
      <Card className="p-6 text-sm text-muted">
        {job.status === "failed"
          ? "No turns recorded — the run failed before its first API call. See the Overview tab for the error."
          : "No turns recorded for this run."}
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="text-sm text-dim">
        {turns.length} turn{turns.length === 1 ? "" : "s"} · click any &ldquo;Show request&rdquo; to inspect the messages sent to the model.
      </div>
      {turns.map((t) => (
        <TurnCard key={t.id} turn={t} />
      ))}
    </div>
  );
}
