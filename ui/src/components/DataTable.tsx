import { ChevronRight } from "lucide-react";
import { cn } from "../lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  className?: string;
  hideBelow?: "sm" | "md" | "lg";
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  emptyMessage?: string;
  emptyIcon?: React.ComponentType<{ className?: string }>;
  onRowClick?: (row: T) => void;
  maxHeight?: string;
}

const HIDE_CLASSES = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
};

export default function DataTable<T>({
  columns,
  data,
  loading,
  emptyMessage = "No data found",
  emptyIcon: EmptyIcon,
  onRowClick,
  maxHeight,
}: DataTableProps<T>) {
  if (loading) {
    return (
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-surface">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "px-5 py-3.5 text-left",
                    col.hideBelow && HIDE_CLASSES[col.hideBelow]
                  )}
                >
                  <div className="h-4 w-20 bg-border/50 rounded animate-pulse" />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="border-b border-border">
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(
                      "px-5 py-4",
                      col.hideBelow && HIDE_CLASSES[col.hideBelow]
                    )}
                  >
                    <div
                      className="h-4 bg-surface rounded animate-pulse"
                      style={{ width: `${50 + Math.random() * 40}%` }}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className={cn("overflow-x-auto", maxHeight && "overflow-y-auto")} style={maxHeight ? { maxHeight } : undefined}>
      <table className="w-full">
        <thead className={maxHeight ? "sticky top-0 z-10" : undefined}>
          <tr className="border-b border-border bg-surface">
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  "px-5 py-3.5 text-left text-[13px] font-semibold uppercase tracking-wider text-dim",
                  col.className,
                  col.hideBelow && HIDE_CLASSES[col.hideBelow]
                )}
              >
                {col.header}
              </th>
            ))}
            {onRowClick && <th className="w-8" />}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length + (onRowClick ? 1 : 0)}
                className="px-5 py-16 text-center"
              >
                {EmptyIcon ? (
                  <div className="flex flex-col items-center gap-2">
                    <EmptyIcon className="w-8 h-8 text-dim/40" />
                    <span className="text-sm text-dim">{emptyMessage}</span>
                  </div>
                ) : (
                  <span className="text-sm text-dim">{emptyMessage}</span>
                )}
              </td>
            </tr>
          ) : (
            data.map((row, i) => (
              <tr
                key={i}
                onClick={() => onRowClick?.(row)}
                className={cn(
                  "border-b border-border transition-colors duration-100",
                  i % 2 === 1 && "bg-surface/30",
                  onRowClick && "cursor-pointer hover:bg-accent/5"
                )}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(
                      "px-5 py-4 text-sm",
                      col.className,
                      col.hideBelow && HIDE_CLASSES[col.hideBelow]
                    )}
                  >
                    {col.render(row)}
                  </td>
                ))}
                {onRowClick && (
                  <td className="px-2 py-4 text-dim/40">
                    <ChevronRight className="w-4 h-4" />
                  </td>
                )}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
