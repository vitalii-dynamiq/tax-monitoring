import { useNavigate } from "react-router-dom";
import { ArrowLeft, RotateCw, AlertCircle } from "lucide-react";
import Card from "../Card";
import Badge from "../Badge";
import TokenBreakdown from "./TokenBreakdown";
import { type MonitoringJob } from "../../lib/api";
import { formatDateTime, formatDuration, formatRelative } from "../../lib/utils";

interface RunHeroHeaderProps {
  job: MonitoringJob;
  onRunAgain?: () => void;
}

function isPreApiFailure(job: MonitoringJob): boolean {
  // Run that failed before the first API turn — telemetry exists but is all
  // zeros because no turn was ever recorded.
  return (
    job.status === "failed" &&
    job.model === null &&
    job.total_input_tokens === 0
  );
}

export default function RunHeroHeader({ job, onRunAgain }: RunHeroHeaderProps) {
  const navigate = useNavigate();
  const preApi = isPreApiFailure(job);

  return (
    <Card className="p-6 mb-6">
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <button
            className="text-sm text-muted hover:text-text mb-3 flex items-center gap-1"
            onClick={() => navigate("/app/agent-monitoring")}
          >
            <ArrowLeft className="w-4 h-4" /> Back to Agent Monitoring
          </button>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-semibold text-text tracking-tight">
              Run #{job.id}
            </h1>
            <Badge value={job.status} />
            <Badge value={job.job_type} />
            <Badge value={job.trigger_type} />
          </div>
          <div className="mt-2 text-sm text-muted flex flex-wrap items-center gap-x-4 gap-y-1">
            <span>
              <span className="text-dim">Jurisdiction:</span>{" "}
              <span className="font-mono text-text">
                {job.jurisdiction_code || "—"}
              </span>
            </span>
            <span>
              <span className="text-dim">Model:</span>{" "}
              <span className="font-mono text-text">{job.model || "—"}</span>
            </span>
            <span>
              <span className="text-dim">Started:</span>{" "}
              {formatDateTime(job.started_at)}
              {job.started_at && (
                <span className="text-dim"> ({formatRelative(job.started_at)})</span>
              )}
            </span>
            <span>
              <span className="text-dim">Duration:</span>{" "}
              {formatDuration(job.started_at, job.completed_at)}
            </span>
            <span>
              <span className="text-dim">Changes:</span>{" "}
              <span className="tabular-nums text-text">{job.changes_detected}</span>
            </span>
          </div>
        </div>
        {onRunAgain && (
          <button
            onClick={onRunAgain}
            className="btn-secondary flex items-center gap-1.5"
          >
            <RotateCw className="w-4 h-4" /> Run again
          </button>
        )}
      </div>

      {preApi ? (
        <div className="flex items-start gap-2 p-3 rounded-md border border-danger/30 bg-danger/5 text-sm">
          <AlertCircle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" />
          <div className="text-muted">
            <span className="font-semibold text-danger">
              Failed before the first API call.
            </span>{" "}
            No tokens were spent. See the Overview tab for the error.
          </div>
        </div>
      ) : (
        <TokenBreakdown
          inputTokens={job.total_input_tokens}
          outputTokens={job.total_output_tokens}
          cacheCreation={job.total_cache_creation_tokens}
          cacheRead={job.total_cache_read_tokens}
          webSearchCount={job.total_web_search_count}
          costUsd={job.estimated_cost_usd}
        />
      )}
    </Card>
  );
}
