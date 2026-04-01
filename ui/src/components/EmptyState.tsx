import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export default function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 max-w-sm mx-auto text-center">
      <div className="w-12 h-12 rounded-full bg-surface flex items-center justify-center mb-4">
        <Icon className="w-6 h-6 text-dim" />
      </div>
      <h3 className="text-base font-semibold text-text mb-1">{title}</h3>
      {description && <p className="text-sm text-dim mb-4">{description}</p>}
      {action && (
        <button onClick={action.onClick} className="btn-primary text-sm h-9 px-4">
          {action.label}
        </button>
      )}
    </div>
  );
}
