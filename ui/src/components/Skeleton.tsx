import Card from "./Card";

/* ------------------------------------------------------------------ */
/*  Base skeleton                                                      */
/* ------------------------------------------------------------------ */

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`bg-surface animate-pulse rounded ${className}`} />;
}

/* ------------------------------------------------------------------ */
/*  Text block – N lines with varying widths                           */
/* ------------------------------------------------------------------ */

const WIDTH_PATTERN = ["w-full", "w-4/5", "w-3/5"];

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={`h-4 rounded-md ${WIDTH_PATTERN[i % WIDTH_PATTERN.length]}`}
        />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Table – mimics DataTable                                           */
/* ------------------------------------------------------------------ */

export function SkeletonTable({
  columns = 4,
  rows = 5,
}: {
  columns?: number;
  rows?: number;
}) {
  return (
    <table className="w-full">
      <thead>
        <tr>
          {Array.from({ length: columns }).map((_, c) => (
            <th key={c} className="px-4 py-3">
              <Skeleton className="h-5 rounded-md" />
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r}>
            {Array.from({ length: columns }).map((_, c) => (
              <td key={c} className="px-4 py-3">
                <Skeleton className="h-4 rounded-md" />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ------------------------------------------------------------------ */
/*  Stat cards row                                                     */
/* ------------------------------------------------------------------ */

export function SkeletonStatCards({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i} className="p-4">
          <Skeleton className="h-4 w-1/2 rounded-md mb-2" />
          <Skeleton className="h-10 w-3/4 rounded-md" />
        </Card>
      ))}
    </div>
  );
}
