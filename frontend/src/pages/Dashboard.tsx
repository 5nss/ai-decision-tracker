import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { BookOpen, RotateCcw, TriangleAlert } from "lucide-react";
import { Link } from "react-router";

import { ChartFrame, DataTable } from "../components/charts/ChartKit";
import { PatternBars } from "../components/charts/PatternBars";
import { ReliabilityChart, binLabel } from "../components/charts/ReliabilityChart";
import { TrendChart } from "../components/charts/TrendChart";
import { DecisionRow } from "../components/DecisionRow";
import { Button, Card, CardHeader, EmptyState, ErrorState, PageHeader, Spinner, buttonTone } from "../components/ui";
import { api } from "../lib/api";
import { CATEGORY, fixed, formatMonth, pct, relativeDay, signedPoints } from "../lib/format";
import { usePreferences } from "../lib/preferences";
import type { Calibration, DecisionSummary, Insights } from "../lib/types";

function HeroTile({ cal }: { cal: Calibration }) {
  const gap = cal.overconfidence ?? 0;
  const verdict =
    Math.abs(gap) < 0.03 ? "Well calibrated" : gap > 0 ? "Overconfident" : "Underconfident";
  return (
    <Card className="flex flex-col justify-between">
      <div className="text-sm text-ink-2">{verdict}</div>
      <div className="mt-2 text-5xl font-semibold tracking-tight text-ink">{signedPoints(gap)}</div>
      <p className="mt-2 text-sm text-ink-2">
        You say <strong className="font-semibold text-ink">{pct(cal.mean_confidence)}</strong> on
        average; <strong className="font-semibold text-ink">{pct(cal.base_rate)}</strong> of your
        expected outcomes happen.
      </p>
      {cal.small_sample && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-3">
          <TriangleAlert className="size-3.5 text-warning" aria-hidden /> Small sample, so treat this as a hint.
        </p>
      )}
    </Card>
  );
}

function StatTile({ label, value, note, href }: { label: string; value: string; note: string; href?: string }) {
  const body = (
    <>
      <div className="text-sm text-ink-2">{label}</div>
      <div className="mt-2 text-3xl font-semibold tracking-tight text-ink">{value}</div>
      <div className="mt-1 text-xs text-ink-3">{note}</div>
    </>
  );
  return href ? (
    <Link to={href} className="block rounded-xl border border-line bg-surface p-5 transition hover:bg-surface-2">
      {body}
    </Link>
  ) : (
    <Card>{body}</Card>
  );
}

function DemoBanner() {
  const queryClient = useQueryClient();
  const { setWorkspace } = usePreferences();
  const reset = useMutation({
    mutationFn: api.resetDemo,
    onSuccess: () => queryClient.invalidateQueries(),
  });
  return (
    <div className="mb-6 flex flex-col gap-3 rounded-xl border border-line wash-accent px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3 text-sm text-ink">
        <BookOpen className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
        <span>
          <strong className="font-semibold">Demo journal.</strong> Six months of decisions by a fictional
          final-year CS student, with hand-labeled audits. Switch to <em>Personal</em> to log your own.
        </span>
      </div>
      <div className="flex shrink-0 gap-2">
        <Button variant="secondary" size="sm" onClick={() => setWorkspace("personal")}>
          Use my journal
        </Button>
        <Button variant="ghost" size="sm" loading={reset.isPending} onClick={() => reset.mutate()}>
          <RotateCcw className="size-3.5" aria-hidden /> Reset demo
        </Button>
      </div>
    </div>
  );
}

function DueList({ decisions }: { decisions: DecisionSummary[] | undefined }) {
  return (
    <Card>
      <CardHeader title="Due for review" subtitle="Decisions whose review date has passed" />
      {!decisions ? (
        <Spinner />
      ) : decisions.length === 0 ? (
        <p className="py-6 text-sm text-ink-2">Nothing due. Reviews show up here on their review date.</p>
      ) : (
        <ul className="-mx-3 space-y-1">
          {decisions.map((d) => (
            <li key={d.id}>
              <Link to={`/decisions/${d.id}`} className="block rounded-lg px-3 py-2.5 hover:bg-surface-2">
                <div className="text-sm font-medium text-ink">{d.title}</div>
                <div className="mt-0.5 text-xs text-ink-3">
                  {pct(d.confidence)} sure · due {relativeDay(d.review_at)}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function EmptyJournal() {
  return (
    <>
      <PageHeader title="Your judgment, measured" subtitle="Your personal journal is empty." />
      <Card>
        <EmptyState
          title="Log your first decision"
          body={
            <ol className="mt-2 space-y-1 text-left">
              <li>1. Write down a decision, your reasoning, and how sure you are.</li>
              <li>2. The audit pulls out the assumptions it depends on.</li>
              <li>3. On the review date, record what happened, and get graded.</li>
            </ol>
          }
          action={
            <Link to="/new" className={clsx("inline-flex h-10 items-center rounded-lg px-4 text-sm font-medium", buttonTone("primary"))}>
              Log a decision
            </Link>
          }
        />
      </Card>
    </>
  );
}

function TopPatternExamples({ insights }: { insights: Insights }) {
  const top = insights.patterns.patterns[0];
  if (!top || top.examples.length === 0) return null;
  return (
    <div>
      <div className="mb-2 text-xs font-medium text-ink-2">
        Recent {CATEGORY[top.category].label.toLowerCase()} assumptions that failed
      </div>
      <ul className="space-y-1.5">
        {top.examples.map((e) => (
          <li key={`${e.decision_id}-${e.text}`} className="text-sm">
            <span className="text-ink">“{e.text}”</span>{" "}
            <Link to={`/decisions/${e.decision_id}`} className="text-accent-ink hover:underline">
              {e.decision_title}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Dashboard() {
  const { workspace } = usePreferences();
  const insights = useQuery({
    queryKey: ["insights", workspace],
    queryFn: () => api.insights(workspace),
    placeholderData: keepPreviousData,
  });
  const due = useQuery({
    queryKey: ["decisions", workspace, "due"],
    queryFn: () => api.decisions(workspace, { status: "due" }),
  });
  const recent = useQuery({
    queryKey: ["decisions", workspace, "all"],
    queryFn: () => api.decisions(workspace),
  });

  if (insights.isPending) return <Spinner label="Loading your journal" />;
  if (insights.isError) return <ErrorState error={insights.error} onRetry={() => insights.refetch()} />;

  const data = insights.data;
  const { counts, calibration: cal, patterns } = data;
  if (counts.total === 0) return <EmptyJournal />;

  return (
    <div className={clsx("transition-opacity", insights.isPlaceholderData && "opacity-60")}>
      <PageHeader
        title="Your judgment, measured"
        subtitle={`${counts.total} decisions logged, ${counts.reviewed} reviewed against what actually happened.`}
      />
      {workspace === "demo" && <DemoBanner />}

      {cal.n === 0 ? (
        <Card className="mb-6">
          <EmptyState
            title="No reviews yet"
            body="Calibration needs outcomes. Record what happened once a decision's review date comes around."
          />
        </Card>
      ) : (
        <>
          <section className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-[1.4fr_1fr_1fr_1fr]">
            <HeroTile cal={cal} />
            <StatTile
              label="Brier score"
              value={fixed(cal.brier)}
              note={`lower is better · 0.25 = always saying 50%${cal.skill_score != null ? ` · skill ${cal.skill_score > 0 ? "+" : ""}${fixed(cal.skill_score)}` : ""}`}
            />
            <StatTile label="Reviewed" value={`${counts.reviewed}`} note={`of ${counts.total} decisions · ${counts.open} still open`} />
            <StatTile label="Due for review" value={`${counts.due}`} note="see the list below" href="/decisions?status=due" />
          </section>

          <section className="mb-6 grid gap-4 xl:grid-cols-3">
            <ChartFrame
              className="xl:col-span-2"
              title="Calibration"
              subtitle="Each dot is a confidence band; bigger dots hold more decisions."
              table={
                <DataTable
                  columns={[
                    { key: "band", label: "Confidence band" },
                    { key: "n", label: "Decisions", align: "right" },
                    { key: "said", label: "You said", align: "right" },
                    { key: "happened", label: "Happened", align: "right" },
                    { key: "gap", label: "Gap", align: "right" },
                  ]}
                  rows={cal.bins.map((b) => ({
                    band: binLabel(b),
                    n: b.n,
                    said: pct(b.mean_confidence),
                    happened: pct(b.hit_rate),
                    gap: b.mean_confidence != null && b.hit_rate != null ? signedPoints(b.mean_confidence - b.hit_rate) : "—",
                  }))}
                />
              }
            >
              <ReliabilityChart bins={cal.bins} />
            </ChartFrame>
            <DueList decisions={due.data} />
          </section>

          <section className="mb-6 grid gap-4 xl:grid-cols-2">
            <ChartFrame
              title="Which assumptions fail"
              subtitle={`Failure rate by category, ranked by the 95% lower bound (needs ${patterns.min_judged}+ judged)`}
              table={
                <DataTable
                  columns={[
                    { key: "category", label: "Category" },
                    { key: "failed", label: "Failed", align: "right" },
                    { key: "judged", label: "Judged", align: "right" },
                    { key: "rate", label: "Rate", align: "right" },
                    { key: "lb", label: "Lower bound", align: "right" },
                  ]}
                  rows={[...patterns.patterns, ...patterns.emerging].map((p) => ({
                    category: CATEGORY[p.category].label,
                    failed: p.failed,
                    judged: p.judged,
                    rate: pct(p.failure_rate),
                    lb: pct(p.lower_bound),
                  }))}
                />
              }
              footer={<TopPatternExamples insights={data} />}
            >
              {patterns.patterns.length ? (
                <PatternBars patterns={patterns.patterns} />
              ) : (
                <p className="py-6 text-sm text-ink-2">
                  Not enough judged assumptions yet. Patterns appear after {patterns.min_judged} per category.
                </p>
              )}
            </ChartFrame>
            <ChartFrame
              title="Calibration over time"
              subtitle="Brier score by the month you made the decision · lower is better"
              table={
                <DataTable
                  columns={[
                    { key: "month", label: "Month" },
                    { key: "n", label: "Decisions", align: "right" },
                    { key: "brier", label: "Brier", align: "right" },
                    { key: "said", label: "You said", align: "right" },
                    { key: "happened", label: "Happened", align: "right" },
                  ]}
                  rows={cal.trend.map((t) => ({
                    month: formatMonth(t.month),
                    n: t.n,
                    brier: fixed(t.brier),
                    said: pct(t.mean_confidence),
                    happened: pct(t.hit_rate),
                  }))}
                />
              }
            >
              <TrendChart trend={cal.trend} />
            </ChartFrame>
          </section>
        </>
      )}

      <Card>
        <CardHeader
          title="Recent decisions"
          action={
            <Link to="/decisions" className="text-sm font-medium text-accent-ink hover:underline">
              View all
            </Link>
          }
        />
        {recent.data ? (
          <ul className="-mx-3">
            {recent.data.slice(0, 6).map((d) => (
              <DecisionRow key={d.id} decision={d} />
            ))}
          </ul>
        ) : (
          <Spinner />
        )}
      </Card>
    </div>
  );
}
