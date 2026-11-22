import { useState } from "react";

import { pct } from "../../lib/format";
import type { CalibrationBin } from "../../lib/types";
import { ChartTooltip, TooltipValue, useWidth } from "./ChartKit";
import type { TooltipState } from "./ChartKit";

const HEIGHT = 300;
const M = { top: 16, right: 20, bottom: 46, left: 50 };

type Point = CalibrationBin & { mean_confidence: number; hit_rate: number };

export const binLabel = (b: CalibrationBin) =>
  `${Math.round(b.lo * 100)}–${Math.round(b.hi * 100) - (b.hi < 1 ? 1 : 0)}%`;

/**
 * Reliability diagram: x = how sure you said you were (bin average), y = how often it happened.
 * On the diagonal is perfect calibration; below it is overconfidence.
 */
export function ReliabilityChart({ bins }: { bins: CalibrationBin[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TooltipState | null>(null);

  const innerW = Math.max(0, width - M.left - M.right);
  const innerH = HEIGHT - M.top - M.bottom;
  const x = (p: number) => M.left + ((p - 0.5) / 0.5) * innerW;
  const y = (r: number) => M.top + (1 - r) * innerH;
  const radius = (n: number) => Math.min(10, 4 + Math.sqrt(n));

  const points = bins.filter(
    (b): b is Point => b.n > 0 && b.mean_confidence != null && b.hit_rate != null,
  );
  // One direct label, on the band where miscalibration is both large and well-supported
  // (gap × √n), so 2 noisy decisions don't outshout 14. The rest live in tooltip + table.
  const weight = (p: Point) => Math.abs(p.mean_confidence - p.hit_rate) * Math.sqrt(p.n);
  const worst = points.reduce<Point | undefined>(
    (best, p) => (!best || weight(p) > weight(best) ? p : best),
    undefined,
  );

  const show = (p: Point) =>
    setTip({
      x: x(p.mean_confidence),
      y: y(p.hit_rate) - radius(p.n),
      content: (
        <TooltipValue
          value={`${pct(p.hit_rate)} happened`}
          label={`${binLabel(p)} band · you said ${pct(p.mean_confidence)} on average · ${p.n} decision${p.n === 1 ? "" : "s"}`}
        />
      ),
    });

  return (
    <div ref={ref} className="relative" onPointerLeave={() => setTip(null)}>
      {width > 0 && (
        <svg
          width={width}
          height={HEIGHT}
          role="img"
          aria-label="Reliability diagram: stated confidence against how often the expected outcome happened"
        >
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t}>
              <line x1={M.left} x2={width - M.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--axis)" : "var(--grid)"} />
              <text x={M.left - 10} y={y(t)} dy="0.32em" textAnchor="end" className="tabular fill-ink-3 text-[11px]">
                {pct(t)}
              </text>
            </g>
          ))}
          {[0.5, 0.6, 0.7, 0.8, 0.9, 1].map((t) => (
            <text key={t} x={x(t)} y={HEIGHT - M.bottom + 18} textAnchor="middle" className="tabular fill-ink-3 text-[11px]">
              {pct(t)}
            </text>
          ))}
          <text x={M.left + innerW / 2} y={HEIGHT - 6} textAnchor="middle" className="fill-ink-3 text-[11px]">
            How sure you said you were
          </text>
          <text
            transform={`translate(13, ${M.top + innerH / 2}) rotate(-90)`}
            textAnchor="middle"
            className="fill-ink-3 text-[11px]"
          >
            How often it happened
          </text>

          {/* perfect calibration */}
          <line x1={x(0.5)} y1={y(0.5)} x2={x(1)} y2={y(1)} stroke="var(--axis)" strokeWidth={1.5} />
          <text x={x(1) - 6} y={y(1) + 16} textAnchor="end" className="fill-ink-3 text-[11px]">
            perfectly calibrated
          </text>
          {/* Region hints only where there's room; on a phone they'd collide with the dots. */}
          {width >= 520 && (
            <>
              <text x={x(0.99)} y={y(0.06)} textAnchor="end" className="fill-ink-3 text-[11px]">
                overconfident ↓
              </text>
              <text x={x(0.51)} y={y(0.94)} className="fill-ink-3 text-[11px]">
                ↑ underconfident
              </text>
            </>
          )}

          {points.length > 1 && (
            <polyline
              points={points.map((p) => `${x(p.mean_confidence)},${y(p.hit_rate)}`).join(" ")}
              fill="none"
              stroke="var(--accent)"
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )}
          {points.map((p) => (
            <circle
              key={`dot-${p.lo}`}
              cx={x(p.mean_confidence)}
              cy={y(p.hit_rate)}
              r={radius(p.n)}
              fill="var(--accent)"
              stroke="var(--surface)"
              strokeWidth={2}
            />
          ))}
          {worst && Math.abs(worst.mean_confidence - worst.hit_rate) >= 0.05 && (
            // Below the point: the line runs through it horizontally-ish, the space underneath is
            // the (empty) overconfident region. Clamped so it never runs off either edge.
            <text
              x={Math.min(Math.max(x(worst.mean_confidence), M.left + 80), width - M.right - 80)}
              y={y(worst.hit_rate) + radius(worst.n) + 18}
              textAnchor="middle"
              className="fill-ink-2 text-[12px] font-medium"
            >
              {`Said ${pct(worst.mean_confidence)}, ${pct(worst.hit_rate)} happened`}
            </text>
          )}
          {/* hit targets: bigger than the dots, keyboard-focusable */}
          {points.map((p) => (
            <circle
              key={`hit-${p.lo}`}
              cx={x(p.mean_confidence)}
              cy={y(p.hit_rate)}
              r={16}
              fill="transparent"
              tabIndex={0}
              aria-label={`${binLabel(p)}: said ${pct(p.mean_confidence)}, ${pct(p.hit_rate)} happened, ${p.n} decisions`}
              onPointerEnter={() => show(p)}
              onFocus={() => show(p)}
              onBlur={() => setTip(null)}
            />
          ))}
        </svg>
      )}
      <ChartTooltip state={tip} width={width} />
    </div>
  );
}
