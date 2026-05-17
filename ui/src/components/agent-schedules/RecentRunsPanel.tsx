import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type MonitoringJob } from "../../lib/api";
import Badge from "../Badge";
import { formatDateTime, formatDuration } from "../../lib/utils";

interface RecentRunsPanelProps {
  jurisdictionCode: string;
  jobType: "monitoring" | "discovery";
}

export default function RecentRunsPanel({
  jurisdictionCode,
  jobType,
}: RecentRunsPanelProps) {
  const [jobs, setJobs] = useState<MonitoringJob[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.monitoring
      .listJobs({
        jurisdiction_code: jurisdictionCode,
        job_type: jobType,
        limit: "20",
      })
      .then((data) => !cancelled && setJobs(data))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [jurisdictionCode, jobType]);

  if (error) {
    return (
      <div className="p-4 text-sm text-danger">Failed to load runs: {error}</div>
    );
  }
  if (jobs === null) {
    return <div className="p-4 text-sm text-muted">Loading recent runs…</div>;
  }
  if (jobs.length === 0) {
    return (
      <div className="p-4 text-sm text-muted">
        No runs yet for this jurisdiction.
      </div>
    );
  }

  return (
    <div className="bg-bg/60 border-t border-border">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-dim text-xs uppercase tracking-wide">
            <tr>
              <th className="px-4 py-2 font-semibold">Started</th>
              <th className="px-4 py-2 font-semibold">Status</th>
              <th className="px-4 py-2 font-semibold">Duration</th>
              <th className="px-4 py-2 font-semibold">Trigger</th>
              <th className="px-4 py-2 font-semibold">Changes</th>
              <th className="px-4 py-2 font-semibold">Details</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => {
              return (
                <tr
                  key={job.id}
                  className="border-t border-border/60 align-top"
                >
                  <td className="px-4 py-2 whitespace-nowrap">
                    {formatDateTime(job.started_at || job.created_at)}
                  </td>
                  <td className="px-4 py-2">
                    <Badge value={job.status} />
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap">
                    {formatDuration(job.started_at, job.completed_at)}
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap">
                    <Badge value={job.trigger_type} />
                  </td>
                  <td className="px-4 py-2 tabular-nums">{job.changes_detected}</td>
                  <td className="px-4 py-2">
                    <Link
                      to={`/app/agent-monitoring/runs/${job.id}`}
                      className="text-accent hover:underline text-xs whitespace-nowrap"
                    >
                      View details →
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
