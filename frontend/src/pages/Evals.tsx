import { useQuery } from "@tanstack/react-query";
import { FlaskConical, Info, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { DataTable } from "../components/charts/ChartKit";
import { Card, CardHeader, EmptyState, ErrorState, PageHeader, SegmentedControl, Spinner, VerdictBadge } from "../components/ui";
import { ApiError, api } from "../lib/api";
import { formatTime, pct } from "../lib/format";
import type { EvalReport, VerdictResult } from "../lib/types";

const COMMAND = "cd backend && python -m evals.run";

function systemName(name: string): string {
  if (name === "outcome-polarity") return "Baseline: copy the outcome";
  if (name === "heuristic") return "Keyword rules (v1, bug fixed)";
  if (name === "gemini") return "Gemini";
  if (name.startsWith("hash-")) return "Hashing embeddings (offline)";
  if (name.startsWith("gemini-embedding")) return "Gemini embeddings";
  return name;
}

/** A single-series meter: value as text first, then a thin bar on a lighter track of the same hue. */
function Metric({ value }: { value: number | null }) {
  return (
    <div className="flex items-center justify-end gap-2.5">
      <span className="tabular w-12 text-right">{pct(value, 1)}</span>
      <div
        className="hidden h-1.5 w-20 rounded-r-full sm:block"
        style={{ background: "color-mix(in oklab, var(--accent) 14%, var(--surface))" }}
      >
        <div className="h-1.5 rounded-r-full bg-accent" style={{ width: `${(value ?? 0) * 100}%` }} />
      </div>
    </div>
  );
}

function Confusion({ result }: { result: VerdictResult }) {
  const max = Math.max(1, ...result.confusion.flat());
  return (
    <div className="overflow-x-auto">
      <table className="text-sm">
        <thead>
          <tr className="text-xs text-ink-3">
            <th className="pb-2 pr-3 text-left font-medium">gold ↓ / predicted →</th>
            {result.labels.map((l) => (
              <th key={l} className="w-24 pb-2 text-center font-medium">
                {l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.confusion.map((row, i) => (
            <tr key={result.labels[i]}>
              <th className="pr-3 text-left text-xs font-medium text-ink-2">{result.labels[i]}</th>
              {row.map((count, j) => (
                <td key={j} className="p-0.5">
                  <div
                    className="tabular flex h-10 items-center justify-center rounded-md text-ink"
                    style={{ background: `color-mix(in oklab, var(--accent) ${Math.round((count / max) * 55)}%, var(--surface-2))` }}
                    title={`gold ${result.labels[i]}, predicted ${result.labels[j]}: ${count}`}
                  >
                    {count}
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ExtractionSection({ data }: { data: NonNullable<EvalReport["extraction"]> }) {
  const [shown, setShown] = useState(3);
  return (
    <Card>
      <CardHeader
        title="1 · Assumption extraction"
        subtitle={`Did it find the assumptions a human labeled? ${data.n_cases} decisions; a prediction counts when its ${data.matcher.kind} with a gold assumption is ≥ ${data.matcher.threshold} (one-to-one).`}
      />
      <DataTable
        columns={[
          { key: "system", label: "System" },
          { key: "p", label: "Precision", align: "right" },
          { key: "r", label: "Recall", align: "right" },
          { key: "f1", label: "F1", align: "right" },
          { key: "cat", label: "Category right", align: "right" },
        ]}
        rows={data.results.map((r) => ({
          system: systemName(r.system),
          p: <Metric value={r.precision} />,
          r: <Metric value={r.recall} />,
          f1: <Metric value={r.f1} />,
          cat: pct(r.category_accuracy, 1),
        }))}
      />
      <div className="mt-5 space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-ink-2">Side by side</p>
        {data.examples.slice(0, shown).map((ex) => (
          <div key={ex.key} className="rounded-lg border border-line p-3.5 text-sm">
            <p className="font-medium text-ink">{ex.title}</p>
            <div className="mt-2 grid gap-3 md:grid-cols-2">
              <div>
                <p className="text-xs text-ink-3">Gold (hand-labeled)</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-4 text-ink-2">
                  {ex.gold.map((g) => (
                    <li key={g}>{g}</li>
                  ))}
                </ul>
              </div>
              {Object.entries(ex.predictions).map(([system, preds]) => (
                <div key={system}>
                  <p className="text-xs text-ink-3">{systemName(system)}</p>
                  {preds.length ? (
                    <ul className="mt-1 list-disc space-y-0.5 pl-4 text-ink-2">
                      {preds.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-ink-3">nothing found</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
        {shown < data.examples.length && (
          <button className="text-sm font-medium text-accent-ink hover:underline" onClick={() => setShown(data.examples.length)}>
            Show {data.examples.length - shown} more
          </button>
        )}
      </div>
    </Card>
  );
}

function VerdictsSection({ data }: { data: NonNullable<EvalReport["verdicts"]> }) {
  const models = data.results.filter((r) => r.system !== "outcome-polarity");
  const best = [...models].sort((a, b) => b.macro_f1 - a.macro_f1)[0] ?? data.results[0]!;
  const [selected, setSelected] = useState(best.system);
  const result = data.results.find((r) => r.system === selected) ?? best;
  return (
    <Card>
      <CardHeader
        title="2 · Assumption verdicts"
        subtitle={`After the outcome, is each assumption held, failed or unclear? ${data.n} hand-labeled verdicts. Macro-F1 weights the rare "unclear" class equally.`}
      />
      <DataTable
        columns={[
          { key: "system", label: "System" },
          { key: "acc", label: "Accuracy", align: "right" },
          { key: "f1", label: "Macro-F1", align: "right" },
          { key: "grounded", label: "Quotes grounded", align: "right" },
        ]}
        rows={data.results.map((r) => ({
          system: systemName(r.system),
          acc: <Metric value={r.accuracy} />,
          f1: <Metric value={r.macro_f1} />,
          grounded: pct(r.grounding_rate, 1),
        }))}
      />
      <p className="mt-3 flex gap-2 text-xs text-ink-3">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        The copy-the-outcome baseline is deliberately strong: most assumptions in a failed decision did fail. A model has to beat it, not just the keyword rules.
      </p>
      <div className="mt-5 grid gap-6 lg:grid-cols-[auto_1fr]">
        <div>
          <div className="mb-3 flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-2">Confusion matrix</p>
            <SegmentedControl
              label="System"
              size="sm"
              value={selected}
              onChange={setSelected}
              options={data.results.map((r) => ({ value: r.system, label: systemName(r.system).split(":")[0]!.split(" (")[0]! }))}
            />
          </div>
          <Confusion result={result} />
        </div>
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-2">Where {systemName(result.system)} disagrees</p>
          {result.errors.length === 0 ? (
            <p className="text-sm text-ink-2">{result.system === "outcome-polarity" ? "The baseline has no evidence to show." : "No disagreements."}</p>
          ) : (
            <ul className="space-y-2.5">
              {result.errors.slice(0, 5).map((e) => (
                <li key={`${e.key}-${e.assumption}`} className="rounded-lg border border-line p-3 text-sm">
                  <p className="text-ink">{e.assumption}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-ink-3">
                    gold <VerdictBadge verdict={e.gold} /> predicted <VerdictBadge verdict={e.predicted} />
                  </div>
                  {e.evidence && <p className="mt-1.5 text-xs text-ink-2">quoted: “{e.evidence}”</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Card>
  );
}

function RetrievalSection({ data }: { data: NonNullable<EvalReport["retrieval"]> }) {
  return (
    <Card>
      <CardHeader
        title="3 · Similar-decision retrieval"
        subtitle={`For each of ${data.n_queries} reviewed decisions, are the other two in its theme among the top ${data.k}? This drives “you've assumed this before”.`}
      />
      <DataTable
        columns={[
          { key: "system", label: "Method" },
          { key: "recall", label: `Recall@${data.k}`, align: "right" },
          { key: "mrr", label: "MRR", align: "right" },
        ]}
        rows={data.results.map((r) => ({
          system: systemName(r.system.replace(" embeddings", "")),
          recall: <Metric value={r.recall_at_k} />,
          mrr: <span className="tabular">{r.mrr.toFixed(3)}</span>,
        }))}
      />
      {data.thresholds.length > 0 && (
        <ul className="mt-4 space-y-1 text-xs text-ink-3">
          {data.thresholds.map((t) => (
            <li key={t.embedding}>
              {systemName(t.embedding.replace(" embeddings", ""))}: same-theme pairs average {t.relevant_mean.toFixed(2)} cosine vs{" "}
              {t.irrelevant_mean.toFixed(2)} otherwise. The best cut-off is {t.threshold?.toFixed(2) ?? "n/a"} (F1 {t.f1.toFixed(2)}), and it sets the app's “similar” threshold.
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function Evals() {
  const report = useQuery({ queryKey: ["evals"], queryFn: api.evals, retry: false });

  if (report.isPending) return <Spinner label="Loading the eval report" />;
  if (report.isError) {
    if (report.error instanceof ApiError && report.error.status === 404)
      return (
        <Card>
          <EmptyState
            icon={<FlaskConical className="size-6" />}
            title="No eval report yet"
            body={<>Run <code className="rounded bg-surface-2 px-1.5 py-0.5">{COMMAND}</code> to score the auditors.</>}
          />
        </Card>
      );
    return <ErrorState error={report.error} onRetry={() => report.refetch()} />;
  }

  const r = report.data;
  const hasGemini = r.systems.some((s) => s.name === "gemini");
  const versions = r.systems.flatMap((s) => s.model_versions);
  return (
    <div className="space-y-6">
      <PageHeader
        title="How do we know it works?"
        subtitle="Each AI step is scored against hand-labeled answers, next to baselines it has to beat. These are the same 36 decisions as the demo journal."
      />
      <Card>
        <dl className="grid gap-4 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-ink-3">Dataset</dt>
            <dd className="mt-0.5 text-ink">{r.dataset.decisions} decisions · {r.dataset.judged_assumptions} verdicts</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-3">Systems</dt>
            <dd className="mt-0.5 text-ink">{r.systems.map((s) => systemName(s.name)).join(" · ")}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-3">Model version</dt>
            <dd className="mt-0.5 text-ink">{versions.length ? versions.join(", ") : "n/a (offline run)"}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-3">Generated</dt>
            <dd className="mt-0.5 text-ink">{formatTime(r.generated_at)}</dd>
          </div>
        </dl>
        <p className="mt-4 text-xs text-ink-3">
          Reproduce with <code className="rounded bg-surface-2 px-1.5 py-0.5 text-ink-2">{COMMAND}</code>. Gemini calls are cached by prompt hash, so re-runs are free.
        </p>
      </Card>

      {!hasGemini && (
        <div className="flex items-start gap-3 rounded-xl border border-line wash-warning px-4 py-3 text-sm text-ink">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            This report only has the offline systems. Add <code>GEMINI_API_KEY</code> to <code>.env</code> and run the command above to fill in Gemini's rows.
          </span>
        </div>
      )}

      {r.extraction && <ExtractionSection data={r.extraction} />}
      {r.verdicts && <VerdictsSection data={r.verdicts} />}
      {r.retrieval && <RetrievalSection data={r.retrieval} />}

      <Card>
        <CardHeader title="Limits of this eval" />
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-ink-2">
          <li>The decisions are synthetic and were labeled by the developer, not by independent raters.</li>
          <li>It's small (36 decisions, {r.dataset.judged_assumptions} verdicts), so a few points of difference are noise.</li>
          <li>Extraction scoring depends on the matcher, so the report records which one was used and its threshold.</li>
        </ul>
      </Card>
    </div>
  );
}
