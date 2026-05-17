import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, X } from "lucide-react";
import { api } from "../../lib/api";
import { useToast } from "../../hooks/useToast";

interface TriageRunModalProps {
  open: boolean;
  onClose: () => void;
  /** Pre-fills the jurisdiction filter (e.g. when triggered from a row). */
  defaultJurisdictionCode?: string;
}

export default function TriageRunModal({
  open,
  onClose,
  defaultJurisdictionCode,
}: TriageRunModalProps) {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [jurisdictionCode, setJurisdictionCode] = useState(
    defaultJurisdictionCode || "",
  );
  const [maxItems, setMaxItems] = useState(50);
  const [busy, setBusy] = useState(false);

  if (!open) return null;

  const submit = async () => {
    setBusy(true);
    try {
      const job = await api.triage.run({
        jurisdiction_code: jurisdictionCode.trim() || null,
        max_items: maxItems,
      });
      toast(`Triage run #${job.id} dispatched`, "success");
      navigate(`/app/agent-monitoring/runs/${job.id}`);
      onClose();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to start triage";
      toast(msg, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="bg-bg border border-border rounded-lg shadow-xl w-full max-w-lg p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-accent" />
            <h2 className="text-lg font-semibold text-text">Triage with AI</h2>
          </div>
          <button
            className="p-1 text-muted hover:text-text rounded"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-sm text-muted leading-relaxed mb-5">
          The triage agent will verify each pending item against its source URL
          via web search and either{" "}
          <span className="text-success font-medium">approve</span>,{" "}
          <span className="text-danger font-medium">reject</span>, or{" "}
          <span className="text-warning font-medium">defer</span> it for you.
          Every decision is logged on the run&apos;s Conversation tab with the
          agent&apos;s reasoning.
        </p>

        <div className="space-y-4">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-dim">
              Jurisdiction filter (optional)
            </span>
            <input
              type="text"
              value={jurisdictionCode}
              onChange={(e) => setJurisdictionCode(e.target.value.toUpperCase())}
              placeholder="e.g. US (country) or US-NY-NYC"
              className="mt-1 w-full bg-surface border border-border rounded-md px-3 py-2 text-sm font-mono"
              disabled={busy}
            />
            <span className="text-xs text-dim mt-1 block">
              Empty = the whole pending queue. A country code includes all
              sub-jurisdictions.
            </span>
          </label>

          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-dim">
              Max items: <span className="text-text tabular-nums">{maxItems}</span>
            </span>
            <input
              type="range"
              min={10}
              max={200}
              step={10}
              value={maxItems}
              onChange={(e) => setMaxItems(Number(e.target.value))}
              disabled={busy}
              className="mt-2 w-full"
            />
            <div className="flex justify-between text-xs text-dim mt-1">
              <span>10</span>
              <span>50</span>
              <span>100</span>
              <span>200</span>
            </div>
          </label>
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <button
            className="btn-secondary text-sm py-1.5 px-3"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            className="btn-primary text-sm py-1.5 px-3 flex items-center gap-1.5 disabled:opacity-50"
            onClick={submit}
            disabled={busy}
          >
            <Sparkles className="w-4 h-4" />
            {busy ? "Starting…" : "Start triage"}
          </button>
        </div>
      </div>
    </div>
  );
}
