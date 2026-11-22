import { useState } from "react";
import type { PointerEvent } from "react";

import { fixed, formatMonth, pct } from "../../lib/format";
import type { TrendPoint } from "../../lib/types";
import { ChartTooltip, TooltipValue, useWidth } from "./ChartKit";
import type { TooltipState } from "./ChartKit";

const HEIGHT = 240;
const M = { top: 18, right: 48, bottom: 30, left: 44 };
const COIN_FLIP = 0.25; // Brier score of always saying 50%

/** Brier score by the month the decision was made. A crosshair snaps to the nearest month. */
export function TrendChart({ trend }: { trend: TrendPoint[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);

  const points = trend.filter((t): t is TrendPoint & { brier: number } => t.brier != null);
  const maxY = Math.max(0.5, Math.ceil(Math.max(0, ...points.map((p) => p.brier)) * 10) / 10);
  const ticks = Array.from({ length: Math.round(maxY / 0.1) + 1 }, (_, i) => +(i * 0.1).toFixed(1));
  const innerW = Math.max(0, width - M.left - M.right);
  const innerH = HEIGHT - M.top - M.bottom;
  const x = (i: number) => M.left + (points.length === 1 ? innerW / 2 : (i * innerW) / (points.length - 1));
  const y = (b: number) => M.top + (1 - b / maxY) * innerH;

  const nearest = (event: PointerEvent<SVGRectElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const px = event.clientX - box.left + M.left;
    let best = 0;
    points.forEach((_, i) => {
      if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i;
    });
    setActive(best);
  };

  const activePoint = active != null ? points[active] : undefined;
  const tip: TooltipState | null =
    activePoint && active != null
      ? {
          x: x(active),
          y: y(activePoint.brier) - 6,
          content: (
            <TooltipValue
              value={`Brier ${fixed(activePoint.brier)}`}
              label={`${formatMonth(activePoint.month)} · ${activePoint.n} decision${activePoint.n === 1 ? "" : "s"} · ${pct(activePoint.hit_rate)} happened, you said ${pct(activePoint.mean_confidence)}`}
            />
          ),
        }
      : null;

  const last = points[points.length - 1];

  return (
    <div ref={ref} className="relative" onPointerLeave={() => setActive(null)}>
      {width > 0 && points.length > 0 && (
        <svg width={width} height={HEIGHT} role="img" aria-label="Brier score by month; lower is better">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={width - M.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--axis)" : "var(--grid)"} />
              <text x={M.left - 10} y={y(t)} dy="0.32em" textAnchor="end" className="tabular fill-ink-3 text-[11px]">
                {t.toFixed(1)}
              </text>
            </g>
          ))}
          <line x1={M.left} x2={width - M.right} y1={y(COIN_FLIP)} y2={y(COIN_FLIP)} stroke="var(--axis)" strokeWidth={1.5} />
          <text x={M.left + 6} y={y(COIN_FLIP) - 6} className="fill-ink-3 text-[11px]">
            always saying 50%
          </text>
          {points.map((p, i) => (
            <text key={p.month} x={x(i)} y={HEIGHT - 8} textAnchor="middle" className="fill-ink-3 text-[11px]">
              {formatMonth(p.month).split(" ")[0]}
            </text>
          ))}

          {activePoint && active != null && (
            <line x1={x(active)} x2={x(active)} y1={M.top} y2={M.top + innerH} stroke="var(--axis)" />
          )}
          {points.length > 1 && (
            <polyline
              points={points.map((p, i) => `${x(i)},${y(p.brier)}`).join(" ")}
              fill="none"
              stroke="var(--accent)"
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )}
          {points.map((p, i) => (
            <circle
              key={p.month}
              cx={x(i)}
              cy={y(p.brier)}
              r={i === active ? 5.5 : 4}
              fill="var(--accent)"
              stroke="var(--surface)"
              strokeWidth={2}
            />
          ))}
          {last && (
            <text x={x(points.length - 1) + 10} y={y(last.brier)} dy="0.32em" className="tabular fill-ink-2 text-[12px] font-medium">
              {fixed(last.brier)}
            </text>
          )}
          <rect
            x={M.left}
            y={M.top}
            width={innerW}
            height={innerH}
            fill="transparent"
            tabIndex={0}
            aria-label="Move across the chart to read each month"
            onPointerMove={nearest}
            onFocus={() => setActive(points.length - 1)}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft") setActive((a) => Math.max(0, (a ?? 0) - 1));
              if (e.key === "ArrowRight") setActive((a) => Math.min(points.length - 1, (a ?? -1) + 1));
            }}
            onBlur={() => setActive(null)}
          />
        </svg>
      )}
      <ChartTooltip state={tip} width={width} />
    </div>
  );
}
