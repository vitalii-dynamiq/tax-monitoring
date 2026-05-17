import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Card from "../components/Card";
import PageContainer from "../components/PageContainer";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { api, type MonitoringJob } from "../lib/api";
import RunHeroHeader from "../components/agent-runs/RunHeroHeader";
import RunOverviewTab from "../components/agent-runs/RunOverviewTab";
import RunConversationTab from "../components/agent-runs/RunConversationTab";
import RunProducedTab from "../components/agent-runs/RunProducedTab";
import RunRawTab from "../components/agent-runs/RunRawTab";

type Tab = "overview" | "conversation" | "produced" | "raw";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "conversation", label: "Conversation" },
  { id: "produced", label: "Produced changes" },
  { id: "raw", label: "Raw" },
];

export default function AgentRunDetail() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const { toast } = useToast();
  const numericId = jobId ? Number(jobId) : NaN;

  const [job, setJob] = useState<MonitoringJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  useEffect(() => {
    if (!isAdmin) return;
    if (Number.isNaN(numericId)) {
      setError("Invalid run id");
      return;
    }
    let cancelled = false;
    api.monitoring
      .getJob(numericId)
      .then((j) => !cancelled && setJob(j))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [numericId, isAdmin]);

  const onRunAgain = useMemo(() => {
    if (!job?.jurisdiction_code) return undefined;
    return async () => {
      if (!window.confirm(`Trigger a new ${job.job_type} run for ${job.jurisdiction_code}?`))
        return;
      try {
        const newJob =
          job.job_type === "discovery"
            ? await api.discovery.triggerRun(job.jurisdiction_code!)
            : await api.monitoring.triggerRun(job.jurisdiction_code!);
        toast(`Dispatched run #${newJob.id}`, "success");
        navigate(`/app/agent-monitoring/runs/${newJob.id}`);
      } catch (e) {
        toast(e instanceof Error ? e.message : "Failed to dispatch", "error");
      }
    };
  }, [job, navigate, toast]);

  if (!isAdmin) {
    return (
      <PageContainer maxWidth="max-w-4xl">
        <Card className="p-8 text-center">
          <h2 className="text-lg font-semibold text-text mb-2">Admin access required</h2>
          <p className="text-muted mb-4">This page is only available to administrators.</p>
          <button className="btn-primary" onClick={() => navigate("/app")}>
            Back to Dashboard
          </button>
        </Card>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer maxWidth="max-w-5xl">
        <Card className="p-8 text-center text-danger">{error}</Card>
      </PageContainer>
    );
  }
  if (!job) {
    return (
      <PageContainer maxWidth="max-w-5xl">
        <Card className="p-8 text-center text-muted">Loading run…</Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer maxWidth="max-w-6xl">
      <RunHeroHeader job={job} onRunAgain={onRunAgain} />

      <div className="flex items-center gap-1 border-b border-border mb-4">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === t.id
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-text"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === "overview" && <RunOverviewTab job={job} />}
      {activeTab === "conversation" && <RunConversationTab jobId={job.id} job={job} />}
      {activeTab === "produced" && <RunProducedTab jobId={job.id} />}
      {activeTab === "raw" && <RunRawTab job={job} />}
    </PageContainer>
  );
}
