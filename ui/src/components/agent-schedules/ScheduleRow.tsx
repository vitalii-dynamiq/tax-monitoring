import { useState } from "react";
import { Check, ChevronDown, ChevronRight, Play, Loader2 } from "lucide-react";
import Badge from "../Badge";
import RecentRunsPanel from "./RecentRunsPanel";
import { api, type MonitoringSchedule } from "../../lib/api";
import { formatDateTime } from "../../lib/utils";

type Cadence = "daily" | "weekly" | "monthly" | "custom";

interface ScheduleRowProps {
  schedule: MonitoringSchedule;
  selected: boolean;
  onToggleSelect: () => void;
  onUpdated: (updated: MonitoringSchedule) => void;
  onRunNow: () => Promise<void> | void;
  onError: (msg: string) => void;
}

export default function ScheduleRow({
  schedule,
  selected,
  onToggleSelect,
  onUpdated,
  onRunNow,
  onError,
}: ScheduleRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [running, setRunning] = useState(false);
  const [cronDraft, setCronDraft] = useState(schedule.cron_expression || "");
  const code = schedule.jurisdiction_code || "";

  const update = async (patch: Partial<MonitoringSchedule>) => {
    setBusy(true);
    try {
      const updated = await api.monitoring.updateSchedule(code, {
        ...patch,
        job_type: schedule.job_type,
      } as Partial<MonitoringSchedule>);
      onUpdated(updated);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 1500);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setBusy(false);
    }
  };

  const handleRunNow = async () => {
    setRunning(true);
    try {
      await onRunNow();
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <tr className="border-t border-border hover:bg-hover/40">
        <td className="px-3 py-3 align-middle">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            className="rounded border-border cursor-pointer"
            aria-label={`Select ${code}`}
          />
        </td>
        <td className="px-3 py-3 align-middle">
          <button
            className="p-1 rounded hover:bg-hover text-muted hover:text-text"
            onClick={() => setExpanded(!expanded)}
            aria-label={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </button>
        </td>
        <td className="px-3 py-3 align-middle">
          <div className="flex flex-col">
            <span className="text-sm font-mono font-semibold text-text">
              {code}
            </span>
          </div>
        </td>
        <td className="px-3 py-3 align-middle">
          <label className="inline-flex items-center cursor-pointer gap-2">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={schedule.enabled}
              onChange={(e) => update({ enabled: e.target.checked })}
              disabled={busy}
            />
            <span className="relative w-10 h-5 bg-dim/30 rounded-full transition-colors peer-checked:bg-success peer-disabled:opacity-50 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-transform peer-checked:after:translate-x-5" />
            <span className="text-xs text-muted">
              {schedule.enabled ? "On" : "Off"}
            </span>
          </label>
        </td>
        <td className="px-3 py-3 align-middle">
          <div className="flex items-center gap-2">
            <select
              className="text-sm bg-surface border border-border rounded-md px-2 py-1"
              value={schedule.cadence}
              onChange={(e) => update({ cadence: e.target.value as Cadence })}
              disabled={busy}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="custom">Custom</option>
            </select>
            {schedule.cadence === "custom" && (
              <input
                type="text"
                placeholder="0 3 * * 1"
                className="text-sm bg-surface border border-border rounded-md px-2 py-1 w-28 font-mono"
                value={cronDraft}
                onChange={(e) => setCronDraft(e.target.value)}
                onBlur={() => {
                  if (cronDraft && cronDraft !== schedule.cron_expression) {
                    update({ cron_expression: cronDraft });
                  }
                }}
                disabled={busy}
              />
            )}
            {savedFlash && (
              <span className="inline-flex items-center gap-0.5 text-xs text-success animate-fadeIn">
                <Check className="w-3.5 h-3.5" /> Saved
              </span>
            )}
          </div>
        </td>
        <td className="px-3 py-3 align-middle whitespace-nowrap">
          <div className="flex items-center gap-2">
            {schedule.last_run_status ? (
              <Badge value={schedule.last_run_status} />
            ) : (
              <span className="text-dim text-xs">—</span>
            )}
            <span className="text-xs text-dim">
              {formatDateTime(schedule.last_run_at)}
            </span>
          </div>
        </td>
        <td className="px-3 py-3 align-middle whitespace-nowrap text-xs text-muted">
          {schedule.enabled ? formatDateTime(schedule.next_run_at) : "—"}
        </td>
        <td className="px-3 py-3 align-middle">
          <button
            className="btn-secondary flex items-center gap-1.5 text-xs py-1 px-2 disabled:opacity-50"
            onClick={handleRunNow}
            disabled={running || busy}
            title="Run agent once now"
          >
            {running ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5" />
            )}
            Run now
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={8} className="p-0">
            <RecentRunsPanel
              jurisdictionCode={code}
              jobType={schedule.job_type}
            />
          </td>
        </tr>
      )}
    </>
  );
}
