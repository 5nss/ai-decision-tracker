import { useState } from "react";

import { CATEGORY, pct } from "../../lib/format";
import type { Pattern } from "../../lib/types";
import { ChartTooltip, TooltipValue, useWidth } from "./ChartKit";
import type { TooltipState } from "./ChartKit";

/**
 * Failure rate per assumption category. Bars are the observed rate; the ink tick is the 95% Wilson
 * lower bound, which is what the ranking uses (so 4/5 outranks 1/1).
 */
export function PatternBars({ patterns }: { patterns: Pattern[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TooltipState | null>(null);

  const show = (p: Pattern, el: HTMLElement) => {
    const host = ref.current?.getBoundingClientRect();
    const box = el.getBoundingClientRect();
    if (!host) return;
    setTip({
      x: box.left - host.left + ((p.failure_rate ?? 0) * box.width),
      y: box.top - host.top,
      content: (
        <TooltipValue
          value={`${p.failed} of ${p.judged} failed (${pct(p.failure_rate)})`}
          label={`${CATEGORY[p.category].label} assumptions · at least ${pct(p.lower_bound)} with 95% confidence${p.unclear ? ` · ${p.unclear} unclear` : ""}`}
        />
      ),
    });
  };

  return (
    <div ref={ref} className="relative" onPointerLeave={() => setTip(null)}>
      <ul className="space-y-3.5">
        {patterns.map((p) => (
          <li key={p.category} className="grid grid-cols-[92px_1fr_auto] items-center gap-3">
            <div className="min-w-0">
              <div className="text-sm font-medium text-ink">{CATEGORY[p.category].label}</div>
              <div className="truncate text-[11px] text-ink-3">{CATEGORY[p.category].hint}</div>
            </div>
            <div
              className="relative h-6 cursor-default"
              tabIndex={0}
              aria-label={`${CATEGORY[p.category].label}: ${p.failed} of ${p.judged} failed, lower bound ${pct(p.lower_bound)}`}
              onPointerEnter={(e) => show(p, e.currentTarget)}
              onFocus={(e) => show(p, e.currentTarget)}
              onBlur={() => setTip(null)}
            >
              <div
                className="absolute inset-y-[5px] left-0 right-0 rounded-r-[4px]"
                style={{ background: "color-mix(in oklab, var(--accent) 13%, var(--surface))" }}
              />
              <div
                className="absolute inset-y-[5px] left-0 rounded-r-[4px] bg-accent"
                style={{ width: `${(p.failure_rate ?? 0) * 100}%` }}
              />
              <div
                className="absolute inset-y-0 w-[2px] -translate-x-1/2 rounded-full bg-ink"
                style={{ left: `${p.lower_bound * 100}%` }}
              />
            </div>
            <div className="tabular w-[92px] text-right text-sm text-ink">
              {p.failed}/{p.judged}
              <span className="ml-1.5 text-ink-3">{pct(p.failure_rate)}</span>
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-ink-3">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-4 rounded-r-[3px] bg-accent" /> failure rate
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-3 w-[2px] bg-ink" /> 95% lower bound (ranking)
        </span>
      </div>
      <ChartTooltip state={tip} width={width} />
    </div>
  );
}
