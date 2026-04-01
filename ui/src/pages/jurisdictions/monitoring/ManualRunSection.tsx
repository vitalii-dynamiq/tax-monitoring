import { useState, useEffect, useRef } from "react";
import Card from "../../../components/Card";
import Badge from "../../../components/Badge";
import ConfirmDialog from "../../../components/ConfirmDialog";
import { api, type MonitoringJob } from "../../../lib/api";
import { useToast } from "../../../hooks/useToast";
import { formatDuration } from "../../../lib/utils";
import { Play, CheckCircle2, XCircle, Loader2 } from "lucide-react";

interface ManualRunSectionProps {
  jurisdictionCode: string;
  activeJob: MonitoringJob | null;
  isPolling: boolean;
  onJobStarted: (jobId: number) => void;
}

export default function ManualRunSection({
  jurisdictionCode,
  activeJob,
  isPolling: _isPolling,
  onJobStarted,
}: ManualRunSectionProps) {
  void _isPolling; // Prop reserved for future use
  const { toast } = useToast();
  const [showConfirm, setShowConfirm] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Elapsed time counter while job is running
  useEffect(() => {
    if (activeJob?.status === "running") {
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [activeJob?.status]);

  const handleRun = async () => {
    setShowConfirm(false);
    setTriggering(true);
    setError(null);
    try {
      const job = await api.monitoring.triggerRun(jurisdictionCode);
      toast("Monitoring job started", "info");
      onJobStarted(job.id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start monitoring job");
      toast("Failed to start monitoring job", "error");
    } finally {
      setTriggering(false);
    }
  };

  const isRunning = activeJob?.status === "pending" || activeJob?.status === "running";
  const isCompleted = activeJob?.status === "completed";
  const isFailed = activeJob?.status === "failed";

  return (
    <>
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold uppercase tracking-widest text-dim">
            Manual Run
          </h3>
          {isRunning && <Badge value={activeJob!.status} />}
        </div>

        {!isRunning && !isCompleted && !isFailed && (
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowConfirm(true)}
              disabled={triggering}
              className="btn-primary px-5 py-2.5 text-sm flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              {triggering ? "Starting..." : "Run Tax Monitoring"}
            </button>
            <span className="text-sm text-dim">
              Scrape sources and detect tax changes for this jurisdiction
            </span>
          </div>
        )}

        {isRunning && (
          <div className="flex items-center gap-4 py-2">
            <Loader2 className="w-6 h-6 text-accent animate-spin" />
            <div>
              <div className="text-sm font-medium text-text">
                Monitoring in progress...
              </div>
              <div className="text-xs text-dim mt-0.5">
                Elapsed: {elapsed}s — Scraping sources and analyzing tax regulations
              </div>
            </div>
          </div>
        )}

        {isCompleted && activeJob && (
          <div className="flex items-start gap-4 py-2">
            <CheckCircle2 className="w-6 h-6 text-success flex-shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-medium text-text">Monitoring complete</div>
              <div className="text-xs text-dim mt-1 space-y-0.5">
                <div>
                  Changes detected:{" "}
                  <span className="font-medium text-text">
                    {activeJob.changes_detected}
                  </span>
                </div>
                {activeJob.result_summary && (
                  <>
                    <div>
                      Sources checked:{" "}
                      {(activeJob.result_summary as Record<string, number>).sources_checked ?? "—"}
                    </div>
                    <div>
                      Confidence:{" "}
                      {(
                        ((activeJob.result_summary as Record<string, number>).overall_confidence ??
                          0) * 100
                      ).toFixed(0)}
                      %
                    </div>
                  </>
                )}
                <div>
                  Duration: {formatDuration(activeJob.started_at, activeJob.completed_at)}
                </div>
              </div>
              <button
                onClick={() => onJobStarted(0)}
                className="text-xs text-accent hover:underline mt-2 cursor-pointer"
              >
                Clear &amp; run again
              </button>
            </div>
          </div>
        )}

        {isFailed && activeJob && (
          <div className="flex items-start gap-4 py-2">
            <XCircle className="w-6 h-6 text-danger flex-shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-medium text-danger">Monitoring failed</div>
              <div className="text-xs text-dim mt-1">
                {activeJob.error_message || "Unknown error"}
              </div>
              <button
                onClick={() => onJobStarted(0)}
                className="text-xs text-accent hover:underline mt-2 cursor-pointer"
              >
                Dismiss &amp; try again
              </button>
            </div>
          </div>
        )}

        {error && !isRunning && (
          <div className="mt-3 text-sm text-danger bg-danger/5 border border-danger/20 rounded-lg px-4 py-2">
            {error}
          </div>
        )}
      </Card>

      <ConfirmDialog
        open={showConfirm}
        title="Run Tax Monitoring"
        message={`This will check all monitored sources for ${jurisdictionCode} and use AI to detect tax changes. This may take a few minutes.`}
        confirmLabel="Run Now"
        onConfirm={handleRun}
        onCancel={() => setShowConfirm(false)}
      />
    </>
  );
}
