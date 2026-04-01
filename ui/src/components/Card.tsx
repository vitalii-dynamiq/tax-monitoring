import { cn } from "../lib/utils";

export default function Card({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("bg-card border border-border rounded-md shadow-sm shadow-black/5 transition-shadow duration-200", className)}>
      {children}
    </div>
  );
}
