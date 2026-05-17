import Card from "../Card";
import JsonViewer from "./JsonViewer";
import MarkdownToggleBlock from "./MarkdownToggleBlock";
import { type MonitoringJob } from "../../lib/api";

interface RunOverviewTabProps {
  job: MonitoringJob;
}

export default function RunOverviewTab({ job }: RunOverviewTabProps) {
  return (
    <div className="space-y-4">
      {/* Final result summary */}
      {job.result_summary && (
        <Card className="p-5">
          <h2 className="text-base font-semibold text-text mb-2">Final result</h2>
          {typeof (job.result_summary as { summary?: string }).summary === "string" && (
            <p className="text-sm text-muted leading-relaxed mb-3">
              {(job.result_summary as { summary: string }).summary}
            </p>
          )}
          <JsonViewer data={job.result_summary} collapsed={false} maxHeight="20rem" />
        </Card>
      )}

      {job.error_message && (
        <Card className="overflow-hidden border-danger/40">
          <div className="px-4 py-2 border-b border-danger/40 bg-danger/5">
            <span className="text-xs font-semibold uppercase tracking-widest text-danger">
              Error
            </span>
          </div>
          <pre className="text-sm whitespace-pre-wrap p-4 text-danger font-mono">
            {job.error_message}
          </pre>
          {job.error_traceback && (
            <details className="border-t border-danger/20 bg-danger/5">
              <summary className="px-4 py-2 text-xs text-danger cursor-pointer">
                Traceback
              </summary>
              <pre className="text-xs whitespace-pre-wrap p-4 text-danger/80 font-mono overflow-auto max-h-96">
                {job.error_traceback}
              </pre>
            </details>
          )}
        </Card>
      )}

      {/* System + initial user prompt — the inputs to the run */}
      {job.system_prompt && (
        <MarkdownToggleBlock title="System prompt" text={job.system_prompt} />
      )}
      {job.initial_user_prompt && (
        <MarkdownToggleBlock title="Initial user prompt" text={job.initial_user_prompt} />
      )}
    </div>
  );
}
