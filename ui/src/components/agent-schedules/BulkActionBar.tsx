import { useState } from "react";
import { X, PlayCircle, PauseCircle, Clock } from "lucide-react";

type Cadence = "daily" | "weekly" | "monthly" | "custom";

interface BulkActionBarProps {
  selectedCount: number;
  busy: boolean;
  onClear: () => void;
  onEnable: () => void;
  onDisable: () => void;
  onSetCadence: (cadence: Cadence, cron?: string) => void;
}

export default function BulkActionBar({
  selectedCount,
  busy,
  onClear,
  onEnable,
  onDisable,
  onSetCadence,
}: BulkActionBarProps) {
  const [cadence, setCadence] = useState<Cadence>("weekly");
  const [cron, setCron] = useState("");

  return (
    <div className="sticky top-2 z-10 mb-4 p-3 bg-accent-dim border border-accent/30 rounded-md flex flex-wrap items-center gap-3 shadow-sm">
      <span className="text-sm font-semibold text-accent">
        {selectedCount} selected
      </span>
      <span className="text-dim">·</span>

      <button
        className="btn-secondary flex items-center gap-1.5 text-sm py-1.5 px-3 disabled:opacity-50"
        onClick={onEnable}
        disabled={busy}
      >
        <PlayCircle className="w-4 h-4" /> Enable
      </button>
      <button
        className="btn-secondary flex items-center gap-1.5 text-sm py-1.5 px-3 disabled:opacity-50"
        onClick={onDisable}
        disabled={busy}
      >
        <PauseCircle className="w-4 h-4" /> Disable
      </button>

      <div className="flex items-center gap-1.5 ml-2">
        <Clock className="w-4 h-4 text-muted" />
        <select
          className="text-sm bg-surface border border-border rounded-md px-2 py-1.5"
          value={cadence}
          onChange={(e) => setCadence(e.target.value as Cadence)}
          disabled={busy}
        >
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
          <option value="custom">Custom (cron)</option>
        </select>
        {cadence === "custom" && (
          <input
            type="text"
            placeholder="0 3 * * 1"
            className="text-sm bg-surface border border-border rounded-md px-2 py-1.5 w-32 font-mono"
            value={cron}
            onChange={(e) => setCron(e.target.value)}
            disabled={busy}
          />
        )}
        <button
          className="btn-primary text-sm py-1.5 px-3 disabled:opacity-50"
          onClick={() =>
            onSetCadence(cadence, cadence === "custom" ? cron : undefined)
          }
          disabled={busy || (cadence === "custom" && !cron.trim())}
        >
          Apply cadence
        </button>
      </div>

      <button
        className="ml-auto p-1.5 rounded-md text-muted hover:text-text hover:bg-hover"
        onClick={onClear}
        aria-label="Clear selection"
        disabled={busy}
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
