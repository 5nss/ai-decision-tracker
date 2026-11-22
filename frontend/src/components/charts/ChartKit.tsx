import { clsx } from "clsx";
import { ChartLine, Table2 } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { Card, CardHeader, SegmentedControl } from "../ui";

/** Width of an element, kept in sync by a ResizeObserver, so SVG text renders at true pixel size. */
export function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    setWidth(element.getBoundingClientRect().width);
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(entry.contentRect.width);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

export interface TooltipState {
  x: number;
  y: number;
  content: ReactNode;
}

/** One tooltip per chart. Positioned in the chart's own coordinate space, kept inside its width. */
export function ChartTooltip({ state, width }: { state: TooltipState | null; width: number }) {
  if (!state) return null;
  const left = Math.min(Math.max(state.x, 90), Math.max(90, width - 90));
  return (
    <div
      role="status"
      className="pointer-events-none absolute z-10 w-max max-w-[220px] -translate-x-1/2 -translate-y-full rounded-lg border border-line bg-surface px-3 py-2 text-xs text-ink-2 shadow-lg"
      style={{ left, top: state.y - 10 }}
    >
      {state.content}
    </div>
  );
}

/** Values lead, labels follow. */
export function TooltipValue({ value, label }: { value: ReactNode; label: ReactNode }) {
  return (
    <div>
      <div className="text-[13px] font-semibold text-ink">{value}</div>
      <div>{label}</div>
    </div>
  );
}

/** Every chart has a table twin, so no value is ever reachable only by hovering. */
export function ChartFrame({
  title,
  subtitle,
  table,
  children,
  footer,
  className,
}: {
  title: string;
  subtitle?: ReactNode;
  table: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  const [view, setView] = useState<"chart" | "table">("chart");
  return (
    <Card className={clsx("flex flex-col", className)}>
      <CardHeader
        title={title}
        subtitle={subtitle}
        action={
          <SegmentedControl
            label={`${title} view`}
            size="sm"
            value={view}
            onChange={setView}
            options={[
              { value: "chart", label: <ChartLine className="size-3.5" aria-label="Chart" />, title: "Chart" },
              { value: "table", label: <Table2 className="size-3.5" aria-label="Table" />, title: "Table" },
            ]}
          />
        }
      />
      <div className="flex-1">{view === "chart" ? children : table}</div>
      {footer && <div className="mt-4 border-t border-line pt-4">{footer}</div>}
    </Card>
  );
}

export function DataTable({
  columns,
  rows,
}: {
  columns: { key: string; label: string; align?: "left" | "right" }[];
  rows: Record<string, ReactNode>[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-ink-3">
            {columns.map((c) => (
              <th key={c.key} className={clsx("py-2 pr-4 font-medium", c.align === "right" && "text-right")}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-line last:border-0">
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={clsx("py-2 pr-4 text-ink", c.align === "right" && "tabular text-right")}
                >
                  {row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
