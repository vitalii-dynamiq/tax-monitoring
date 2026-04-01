import { cn } from "../lib/utils";

const VARIANTS: Record<string, string> = {
  active: "bg-success/10 text-success border-success/25",
  approved: "bg-success/10 text-success border-success/25",
  connected: "bg-success/10 text-success border-success/25",
  scheduled: "bg-accent/10 text-accent border-accent/25",
  draft: "bg-warning/10 text-warning border-warning/25",
  pending: "bg-warning/10 text-warning border-warning/25",
  needs_review: "bg-warning/10 text-warning border-warning/25",
  rejected: "bg-danger/10 text-danger border-danger/25",
  superseded: "bg-dim/8 text-dim border-dim/20",
  inactive: "bg-dim/8 text-dim border-dim/20",
  percentage: "bg-accent/10 text-accent border-accent/25",
  flat: "bg-warning/10 text-warning border-warning/25",
  tiered: "bg-success/10 text-success border-success/25",
  condition: "bg-accent/10 text-accent border-accent/25",
  exemption: "bg-success/10 text-success border-success/25",
  reduction: "bg-warning/10 text-warning border-warning/25",
  surcharge: "bg-danger/10 text-danger border-danger/25",
  cap: "bg-dim/8 text-dim border-dim/20",
  override: "bg-danger/10 text-danger border-danger/25",
  threshold: "bg-warning/10 text-warning border-warning/25",
  country: "bg-accent/10 text-accent border-accent/25",
  state: "bg-success/10 text-success border-success/25",
  city: "bg-warning/10 text-warning border-warning/25",
  district: "bg-dim/8 text-dim border-dim/20",
  government_website: "bg-accent/10 text-accent border-accent/25",
  tax_authority: "bg-success/10 text-success border-success/25",
  legal_gazette: "bg-warning/10 text-warning border-warning/25",
  regulatory_body: "bg-dim/8 text-dim border-dim/20",
  seed: "bg-dim/8 text-dim border-dim/20",
  api: "bg-accent/10 text-accent border-accent/25",
  ai_detection: "bg-warning/10 text-warning border-warning/25",
  manual_review: "bg-success/10 text-success border-success/25",
  bulk_import: "bg-dim/8 text-dim border-dim/20",
  running: "bg-accent/10 text-accent border-accent/25",
  completed: "bg-success/10 text-success border-success/25",
  failed: "bg-danger/10 text-danger border-danger/25",
  cancelled: "bg-dim/8 text-dim border-dim/20",
  manual: "bg-accent/10 text-accent border-accent/25",
  daily: "bg-accent/10 text-accent border-accent/25",
  weekly: "bg-success/10 text-success border-success/25",
  monthly: "bg-warning/10 text-warning border-warning/25",
  custom: "bg-dim/8 text-dim border-dim/20",
  disabled: "bg-dim/8 text-dim border-dim/20",
  admin: "bg-accent/10 text-accent border-accent/25",
  user: "bg-success/10 text-success border-success/25",
};

// Status values that show a colored dot indicator
const DOT_COLORS: Record<string, string> = {
  active: "bg-success",
  approved: "bg-success",
  completed: "bg-success",
  connected: "bg-success",
  running: "bg-accent",
  pending: "bg-warning",
  needs_review: "bg-warning",
  draft: "bg-warning",
  scheduled: "bg-accent",
  failed: "bg-danger",
  rejected: "bg-danger",
  inactive: "bg-dim",
  cancelled: "bg-dim",
  disabled: "bg-dim",
};

export default function Badge({ value, className }: { value: string; className?: string }) {
  const variant = VARIANTS[value] || "bg-surface text-muted border-border";
  const dotColor = DOT_COLORS[value];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1 rounded-md border text-[13px] font-semibold uppercase tracking-wide whitespace-nowrap",
        variant,
        className
      )}
    >
      {dotColor && <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", dotColor)} />}
      {value.replace(/_/g, " ")}
    </span>
  );
}
