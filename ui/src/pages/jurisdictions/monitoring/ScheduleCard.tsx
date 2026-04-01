import { useState, useEffect } from "react";
import Card from "../../../components/Card";
import Badge from "../../../components/Badge";
import { api, type MonitoringSchedule } from "../../../lib/api";
import { useToast } from "../../../hooks/useToast";
import { formatDateTime } from "../../../lib/utils";

interface ScheduleCardProps {
  jurisdictionCode: string;
}

const CADENCE_OPTIONS = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "custom", label: "Custom Cron" },
];

export default function ScheduleCard({ jurisdictionCode }: ScheduleCardProps) {
  const { toast } = useToast();
  const [schedule, setSchedule] = useState<MonitoringSchedule | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [cadence, setCadence] = useState("weekly");
  const [cronExpression, setCronExpression] = useState("");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.monitoring
      .getSchedule(jurisdictionCode)
      .then((s) => {
        setSchedule(s);
        setEnabled(s.enabled);
        setCadence(s.cadence);
        setCronExpression(s.cron_expression || "");
      })
      .catch(() => {
        // No schedule exists yet — that's fine
        setSchedule(null);
      })
      .finally(() => setLoading(false));
  }, [jurisdictionCode]);

  useEffect(() => {
    if (!schedule) {
      setDirty(enabled || cadence !== "weekly");
      return;
    }
    setDirty(
      enabled !== schedule.enabled ||
        cadence !== schedule.cadence ||
        cronExpression !== (schedule.cron_expression || "")
    );
  }, [enabled, cadence, cronExpression, schedule]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const result = await api.monitoring.updateSchedule(jurisdictionCode, {
        enabled,
        cadence: cadence as MonitoringSchedule["cadence"],
        cron_expression: cadence === "custom" ? cronExpression : null,
      });
      setSchedule(result);
      setDirty(false);
      toast("Schedule updated", "success");
    } catch (e) {
      console.error(e);
      toast("Failed to update schedule", "error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-6">
        <div className="text-sm text-dim">Loading schedule...</div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold uppercase tracking-widest text-dim">
            Monitoring Schedule
          </h3>
          <Badge value={enabled ? "active" : "disabled"} />
        </div>
        {dirty && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn-primary px-4 py-1.5 text-sm"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label className="block text-xs text-dim mb-1">Enabled</label>
          <button
            onClick={() => setEnabled(!enabled)}
            className={`w-12 h-6 rounded-full transition-colors relative cursor-pointer ${
              enabled ? "bg-accent" : "bg-surface border border-border"
            }`}
          >
            <span
              className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                enabled ? "translate-x-6" : "translate-x-0.5"
              }`}
            />
          </button>
        </div>

        <div>
          <label className="block text-xs text-dim mb-1">Cadence</label>
          <select
            value={cadence}
            onChange={(e) => setCadence(e.target.value)}
            className="input-field w-full text-sm"
          >
            {CADENCE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {cadence === "custom" && (
          <div>
            <label className="block text-xs text-dim mb-1">Cron Expression</label>
            <input
              type="text"
              value={cronExpression}
              onChange={(e) => setCronExpression(e.target.value)}
              placeholder="0 3 * * 1"
              className="input-field w-full text-sm font-mono"
            />
          </div>
        )}

        <div>
          <label className="block text-xs text-dim mb-1">Next Run</label>
          <div className="text-sm text-muted">
            {schedule?.next_run_at ? formatDateTime(schedule.next_run_at) : "Not scheduled"}
          </div>
        </div>

        <div>
          <label className="block text-xs text-dim mb-1">Last Run</label>
          <div className="text-sm text-muted">
            {schedule?.last_run_at ? formatDateTime(schedule.last_run_at) : "Never"}
          </div>
        </div>
      </div>
    </Card>
  );
}
