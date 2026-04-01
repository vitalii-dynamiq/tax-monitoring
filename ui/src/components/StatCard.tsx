import Card from "./Card";
import { cn } from "../lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "default" | "success" | "warning" | "danger";
  icon?: React.ComponentType<{ className?: string }>;
  onClick?: () => void;
}

const ACCENTS = {
  default: "text-text",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
};

const STRIPE = {
  default: "",
  success: "border-t-2 border-t-success",
  warning: "border-t-2 border-t-warning",
  danger: "border-t-2 border-t-danger",
};

export default function StatCard({ label, value, sub, accent = "default", icon: Icon, onClick }: StatCardProps) {
  return (
    <Card
      className={cn(
        "p-6 hover:border-border-light transition-all duration-200",
        STRIPE[accent],
        onClick && "cursor-pointer hover:-translate-y-0.5 hover:shadow-md"
      )}
    >
      {onClick ? (
        <button onClick={onClick} className="w-full text-left focus:outline-none">
          <StatCardContent label={label} value={value} sub={sub} accent={accent} icon={Icon} />
        </button>
      ) : (
        <StatCardContent label={label} value={value} sub={sub} accent={accent} icon={Icon} />
      )}
    </Card>
  );
}

function StatCardContent({
  label, value, sub, accent = "default", icon: Icon,
}: Omit<StatCardProps, "onClick">) {
  return (
    <div className="relative">
      {Icon && (
        <div className="absolute top-0 right-0">
          <Icon className="w-8 h-8 text-dim/15" />
        </div>
      )}
      <div className="text-sm font-semibold uppercase tracking-wide text-dim mb-3">
        {label}
      </div>
      <div className={cn("text-3xl sm:text-4xl font-bold tabular-nums leading-none", ACCENTS[accent!])}>
        {value}
      </div>
      {sub && <div className="text-sm text-dim mt-2">{sub}</div>}
    </div>
  );
}
