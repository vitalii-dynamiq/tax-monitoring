/**
 * Pure SVG donut chart — no chart library needed.
 * Renders a ring with colored segments and a center label.
 */

interface Segment {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  segments: Segment[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerValue?: string | number;
}

export default function DonutChart({
  segments,
  size = 180,
  thickness = 28,
  centerLabel,
  centerValue,
}: DonutChartProps) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  if (total === 0) return null;

  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  let offset = 0;
  const arcs = segments.map((seg) => {
    const pct = seg.value / total;
    const dashLength = pct * circumference;
    const dashOffset = -offset * circumference;
    offset += pct;
    return { ...seg, dashLength, dashOffset, pct };
  });

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          {/* Background ring */}
          <circle
            cx={center} cy={center} r={radius}
            fill="none" stroke="var(--color-surface)" strokeWidth={thickness}
          />
          {/* Segments */}
          {arcs.map((arc, i) => (
            <circle
              key={i}
              cx={center} cy={center} r={radius}
              fill="none"
              stroke={arc.color}
              strokeWidth={thickness}
              strokeDasharray={`${arc.dashLength} ${circumference - arc.dashLength}`}
              strokeDashoffset={arc.dashOffset}
              strokeLinecap="round"
              className="transition-all duration-500"
            />
          ))}
        </svg>
        {/* Center text */}
        {(centerLabel || centerValue) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {centerValue && (
              <span className="text-2xl font-bold text-text tabular-nums">{centerValue}</span>
            )}
            {centerLabel && (
              <span className="text-xs text-dim uppercase tracking-wide">{centerLabel}</span>
            )}
          </div>
        )}
      </div>
      {/* Legend */}
      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1.5">
        {arcs.map((arc, i) => (
          <div key={i} className="flex items-center gap-1.5 text-xs">
            <span
              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: arc.color }}
            />
            <span className="text-dim">{arc.label}</span>
            <span className="font-semibold text-text tabular-nums">{arc.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
