interface TokenBreakdownProps {
  inputTokens: number;
  outputTokens: number;
  cacheCreation?: number;
  cacheRead?: number;
  webSearchCount?: number;
  costUsd?: string;
  compact?: boolean;
}

function Pill({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div className="flex flex-col gap-0.5 px-3 py-1.5 rounded-md bg-surface border border-border">
      <span className="text-[10px] uppercase tracking-wide text-dim">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${accent || "text-text"}`}>{value}</span>
    </div>
  );
}

const fmtN = (n: number) => n.toLocaleString();

export default function TokenBreakdown({
  inputTokens,
  outputTokens,
  cacheCreation = 0,
  cacheRead = 0,
  webSearchCount = 0,
  costUsd,
  compact = false,
}: TokenBreakdownProps) {
  return (
    <div className={`flex flex-wrap items-stretch ${compact ? "gap-1.5" : "gap-2"}`}>
      <Pill label="Input tokens" value={fmtN(inputTokens)} />
      <Pill label="Output tokens" value={fmtN(outputTokens)} />
      {(cacheCreation > 0 || cacheRead > 0) && (
        <>
          <Pill label="Cache write tokens" value={fmtN(cacheCreation)} />
          <Pill label="Cache read tokens" value={fmtN(cacheRead)} />
        </>
      )}
      <Pill label="Web searches" value={fmtN(webSearchCount)} />
      {costUsd !== undefined && (
        <Pill label="Est. cost (USD)" value={`$${costUsd}`} accent="text-accent" />
      )}
    </div>
  );
}
