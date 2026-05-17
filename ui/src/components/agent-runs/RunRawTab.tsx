import { useEffect, useState } from "react";
import Card from "../Card";
import JsonViewer from "./JsonViewer";
import { api, type AgentRunTurn, type MonitoringJob } from "../../lib/api";

interface RunRawTabProps {
  job: MonitoringJob;
}

export default function RunRawTab({ job }: RunRawTabProps) {
  const [turns, setTurns] = useState<AgentRunTurn[] | null>(null);
  useEffect(() => {
    api.monitoring.getJobTurns(job.id).then(setTurns).catch(() => setTurns([]));
  }, [job.id]);

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-text mb-2">Job record</h3>
        <JsonViewer data={job} collapsed={false} maxHeight="24rem" />
      </Card>
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-text mb-2">All turns</h3>
        {turns === null ? (
          <div className="text-muted text-sm">Loading…</div>
        ) : (
          <JsonViewer data={turns} collapsed={false} maxHeight="32rem" />
        )}
      </Card>
    </div>
  );
}
