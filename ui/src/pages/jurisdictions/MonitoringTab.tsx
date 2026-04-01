import { useState, useCallback } from "react";
import StatCard from "../../components/StatCard";
import { api, type MonitoringJob } from "../../lib/api";
import { useApi } from "../../hooks/useApi";
import { usePollingApi } from "../../hooks/usePollingApi";
import ScheduleCard from "./monitoring/ScheduleCard";
import ManualRunSection from "./monitoring/ManualRunSection";
import JobHistoryTable from "./monitoring/JobHistoryTable";

export default function MonitoringTab({
  jurisdictionCode,
}: {
  jurisdictionCode: string;
}) {
  const [activeJobId, setActiveJobId] = useState<number | null>(null);

  const {
    data: jobs,
    loading: jobsLoading,
    refetch: refetchJobs,
  } = useApi(
    () =>
      api.monitoring.listJobs({ jurisdiction_code: jurisdictionCode, job_type: "monitoring", limit: "50" }),
    [jurisdictionCode]
  );

  // Poll the active job while it's running
  const { data: activeJob } = usePollingApi<MonitoringJob>(
    () => api.monitoring.getJob(activeJobId!),
    [activeJobId],
    {
      intervalMs: 2000,
      enabled: activeJobId != null && activeJobId > 0,
      stopWhen: (j) => {
        if (j.status === "completed" || j.status === "failed") {
          refetchJobs();
          return true;
        }
        return false;
      },
    }
  );

  const handleJobStarted = useCallback((jobId: number) => {
    if (jobId === 0) {
      // Clear / dismiss
      setActiveJobId(null);
      return;
    }
    setActiveJobId(jobId);
  }, []);

  const allJobs = jobs || [];
  const completedCount = allJobs.filter((j) => j.status === "completed").length;
  const failedCount = allJobs.filter((j) => j.status === "failed").length;
  const totalChanges = allJobs.reduce((sum, j) => sum + j.changes_detected, 0);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <StatCard
          label="Total Jobs"
          value={allJobs.length}
          sub="All monitoring runs"
        />
        <StatCard
          label="Successful"
          value={completedCount}
          accent={completedCount > 0 ? "success" : "default"}
          sub={`${failedCount} failed`}
        />
        <StatCard
          label="Total Changes Found"
          value={totalChanges}
          accent={totalChanges > 0 ? "warning" : "default"}
          sub="Across all runs"
        />
      </div>

      <ScheduleCard jurisdictionCode={jurisdictionCode} />

      <ManualRunSection
        jurisdictionCode={jurisdictionCode}
        activeJob={activeJob}
        isPolling={activeJobId != null && activeJobId > 0}
        onJobStarted={handleJobStarted}
      />

      <div>
        <div className="text-xs font-semibold uppercase tracking-widest text-dim mb-3">
          Job History
        </div>
        <JobHistoryTable jobs={allJobs} loading={jobsLoading} />
      </div>
    </div>
  );
}
