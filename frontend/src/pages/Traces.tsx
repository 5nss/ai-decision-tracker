import { useQuery } from "@tanstack/react-query";
import { CircleCheck, CircleX } from "lucide-react";
import { Link } from "react-router";

import { DataTable } from "../components/charts/ChartKit";
import { Card, CardHeader, EmptyState, ErrorState, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { compact, formatTime, pct } from "../lib/format";

function Tile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <Card>
      <div className="text-sm text-ink-2">{label}</div>
      <div className="mt-2 text-3xl font-semibold tracking-tight text-ink">{value}</div>
      <div className="mt-1 text-xs text-ink-3">{note}</div>
    </Card>
  );
}

const ms = (value: number | null) => (value == null ? "—" : value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${value} ms`);

export function TracesPage() {
  const traces = useQuery({ queryKey: ["traces"], queryFn: api.traces, refetchInterval: 15_000 });

  if (traces.isPending) return <Spinner label="Loading traces" />;
  if (traces.isError) return <ErrorState error={traces.error} onRetry={() => traces.refetch()} />;

  const t = traces.data;
  const audit = t.by_operation.find((o) => o.operation === "audit");
  const tokensIn = t.by_operation.reduce((sum, o) => sum + o.input_tokens, 0);
  const tokensOut = t.by_operation.reduce((sum, o) => sum + o.output_tokens, 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Traces"
        subtitle="Every model call, recorded with its latency, retries, tokens and errors. A failed call shows up here; it never disappears silently."
      />
      {t.total_calls === 0 ? (
        <Card>
          <EmptyState title="No calls yet" body="Log a decision or record an outcome, and its model calls will appear here." />
        </Card>
      ) : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Tile label="Model calls" value={compact(t.total_calls)} note="most recent 2,000" />
            <Tile label="Error rate" value={pct(t.error_rate, 1)} note="after retries" />
            <Tile label="Audit latency" value={ms(audit?.p50_ms ?? null)} note={`median · p95 ${ms(audit?.p95_ms ?? null)}`} />
            <Tile label="Tokens" value={compact(tokensIn + tokensOut)} note={`${compact(tokensIn)} in · ${compact(tokensOut)} out`} />
          </section>

          <Card>
            <CardHeader title="By operation" />
            <DataTable
              columns={[
                { key: "op", label: "Operation" },
                { key: "provider", label: "Provider" },
                { key: "calls", label: "Calls", align: "right" },
                { key: "errors", label: "Errors", align: "right" },
                { key: "p50", label: "p50", align: "right" },
                { key: "p95", label: "p95", align: "right" },
                { key: "tokens", label: "Tokens in / out", align: "right" },
              ]}
              rows={t.by_operation.map((o) => ({
                op: o.operation,
                provider: o.provider,
                calls: o.calls,
                errors: o.errors,
                p50: ms(o.p50_ms),
                p95: ms(o.p95_ms),
                tokens: `${compact(o.input_tokens)} / ${compact(o.output_tokens)}`,
              }))}
            />
          </Card>

          <Card>
            <CardHeader title="Recent calls" subtitle="Newest first" />
            <DataTable
              columns={[
                { key: "when", label: "When" },
                { key: "op", label: "Operation" },
                { key: "model", label: "Model" },
                { key: "latency", label: "Latency", align: "right" },
                { key: "attempts", label: "Attempts", align: "right" },
                { key: "status", label: "Status" },
                { key: "decision", label: "Decision" },
              ]}
              rows={t.calls.map((c) => ({
                when: <span className="whitespace-nowrap text-ink-2">{formatTime(c.created_at)}</span>,
                op: c.operation,
                model: (
                  <span className="text-ink-2" title={c.model_version ?? undefined}>
                    {c.model}
                  </span>
                ),
                latency: ms(c.latency_ms),
                attempts: c.attempts,
                status: c.ok ? (
                  <span className="inline-flex items-center gap-1 text-ink-2">
                    <CircleCheck className="size-3.5 text-good" aria-hidden /> ok
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-ink" title={c.error ?? undefined}>
                    <CircleX className="size-3.5 text-critical" aria-hidden /> {c.error?.slice(0, 40) ?? "error"}
                  </span>
                ),
                decision:
                  c.decision_id != null && c.workspace ? (
                    <Link to={`/decisions/${c.decision_id}`} className="text-accent-ink hover:underline">
                      #{c.decision_id}
                    </Link>
                  ) : (
                    <span className="text-ink-3">{c.workspace ?? "—"}</span>
                  ),
              }))}
            />
          </Card>
        </>
      )}
    </div>
  );
}
