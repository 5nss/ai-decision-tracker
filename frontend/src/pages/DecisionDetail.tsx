import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import {
  ArrowLeft,
  CircleCheck,
  CircleX,
  History,
  Info,
  Lock,
  Quote,
  RotateCcw,
  Sparkles,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, Spinner, StatusBadge, VerdictBadge, inputClass } from "../components/ui";
import { ApiError, api } from "../lib/api";
import { CATEGORY, DOMAIN_LABEL, RISK_LABEL, fixed, formatDay, pct, providerLabel, relativeDay } from "../lib/format";
import { usePreferences } from "../lib/preferences";
import type { Assumption, DecisionDetail as Detail } from "../lib/types";

function useDecisionCache() {
  const queryClient = useQueryClient();
  const { workspace } = usePreferences();
  return (decision: Detail) => {
    queryClient.setQueryData(["decision", workspace, decision.id], decision);
    void queryClient.invalidateQueries({ queryKey: ["insights", workspace] });
    void queryClient.invalidateQueries({ queryKey: ["decisions", workspace] });
    void queryClient.invalidateQueries({ queryKey: ["traces"] });
  };
}

function AssumptionItem({ assumption: a }: { assumption: Assumption }) {
  return (
    <li className="rounded-lg border border-line p-3.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-sm text-ink">{a.text}</p>
        {a.verdict && <VerdictBadge verdict={a.verdict} />}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Badge title={CATEGORY[a.category].hint}>{CATEGORY[a.category].label}</Badge>
        <Badge tone={a.risk === "high" ? "warning" : "neutral"}>{RISK_LABEL[a.risk]}</Badge>
      </div>
      {a.evidence && (
        <blockquote className="mt-3 flex gap-2 border-l-2 border-line pl-3 text-sm text-ink-2">
          <Quote className="mt-0.5 size-3.5 shrink-0 text-ink-3" aria-hidden />
          <span>{a.evidence}</span>
        </blockquote>
      )}
      {a.evidence_grounded === false && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-2">
          <TriangleAlert className="size-3.5 text-warning" aria-hidden /> This quote isn't in your notes. Treat the verdict with care.
        </p>
      )}
    </li>
  );
}

function AuditCard({ decision: d }: { decision: Detail }) {
  const { workspace } = usePreferences();
  const save = useDecisionCache();
  const retry = useMutation({ mutationFn: () => api.retryAudit(workspace, d.id), onSuccess: save });

  return (
    <Card>
      <CardHeader
        title="Assumption audit"
        subtitle={d.audit_status === "done" ? `By ${providerLabel(d.audit_provider)}` : undefined}
      />
      {d.audit_status === "failed" && (
        <div className="mb-4 rounded-lg wash-critical p-3.5 text-sm">
          <p className="flex items-center gap-1.5 font-medium text-ink">
            <TriangleAlert className="size-4 text-critical" aria-hidden /> The audit didn't finish
          </p>
          <p className="mt-1 text-ink-2">{d.audit_error}</p>
          <p className="mt-1 text-ink-2">Your decision is saved. Retrying only re-runs the audit.</p>
          {!d.outcome && (
            <Button size="sm" variant="secondary" className="mt-3" loading={retry.isPending} onClick={() => retry.mutate()}>
              <RotateCcw className="size-3.5" aria-hidden /> Retry audit
            </Button>
          )}
        </div>
      )}
      {d.audit_status === "pending" && <Spinner label="Audit in progress" />}

      {d.assumptions.length > 0 ? (
        <ul className="space-y-2.5">
          {d.assumptions.map((a) => (
            <AssumptionItem key={a.id} assumption={a} />
          ))}
        </ul>
      ) : (
        d.audit_status === "done" && (
          <p className="text-sm text-ink-2">No assumptions were found in the reasoning.</p>
        )
      )}

      {d.premortem && (
        <div className="mt-4 rounded-lg wash-accent p-3.5">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-2">
            <Sparkles className="size-3.5 text-accent" aria-hidden /> Pre-mortem
          </p>
          <p className="mt-1 text-sm text-ink">{d.premortem}</p>
        </div>
      )}

      {d.missing_considerations.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-2">Not considered</p>
          <ul className="space-y-1.5">
            {d.missing_considerations.map((m) => (
              <li key={m} className="flex gap-2 text-sm text-ink-2">
                <Info className="mt-0.5 size-3.5 shrink-0 text-ink-3" aria-hidden />
                {m}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function OutcomeForm({ decision: d }: { decision: Detail }) {
  const { workspace } = usePreferences();
  const save = useDecisionCache();
  const [happened, setHappened] = useState<boolean | null>(null);
  const [notes, setNotes] = useState("");
  const record = useMutation({
    mutationFn: () => api.recordOutcome(workspace, d.id, { happened: happened!, what_happened: notes.trim() }),
    onSuccess: save,
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (happened != null && notes.trim().length >= 10) record.mutate();
  };

  return (
    <Card className={clsx(d.status === "due" && "ring-2 ring-[color-mix(in_oklab,var(--warning)_55%,transparent)]")}>
      <CardHeader
        title="Record the outcome"
        subtitle={d.status === "due" ? `Review was due ${relativeDay(d.review_at)}.` : `Review date: ${formatDay(d.review_at, true)} (${relativeDay(d.review_at)}).`}
      />
      <form className="space-y-4" onSubmit={submit}>
        <div>
          <p className="mb-2 text-sm text-ink">
            Did this happen: <span className="font-medium">“{d.expected_outcome}”</span>?
          </p>
          <div className="grid grid-cols-2 gap-2">
            {[
              { value: true, label: "Yes, it happened", icon: <CircleCheck className="size-4 text-good" aria-hidden /> },
              { value: false, label: "No, it didn't", icon: <CircleX className="size-4 text-critical" aria-hidden /> },
            ].map((option) => (
              <button
                key={String(option.value)}
                type="button"
                aria-pressed={happened === option.value}
                onClick={() => setHappened(option.value)}
                className={clsx(
                  "flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition",
                  happened === option.value ? "border-ink bg-surface-2 text-ink" : "border-line text-ink-2 hover:bg-surface-2",
                )}
              >
                {option.icon}
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <div className="space-y-1.5">
          <label htmlFor="notes" className="block text-sm font-medium text-ink">
            What actually happened?
          </label>
          <textarea
            id="notes"
            className={clsx(inputClass, "min-h-28")}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Be specific. The verdicts quote this text as evidence."
          />
        </div>
        {record.isError && (
          <p className="rounded-lg wash-critical px-3 py-2 text-sm text-ink" role="alert">
            {record.error.message}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={happened == null || notes.trim().length < 10} loading={record.isPending}>
          {record.isPending ? "Judging your assumptions" : "Save and review"}
        </Button>
      </form>
    </Card>
  );
}

function OutcomeCard({ decision: d }: { decision: Detail }) {
  const { workspace } = usePreferences();
  const save = useDecisionCache();
  const retry = useMutation({ mutationFn: () => api.retryReview(workspace, d.id), onSuccess: save });
  const o = d.outcome!;
  return (
    <Card>
      <CardHeader title="Outcome" subtitle={`Reviewed ${formatDay(o.created_at, true)}`} action={<StatusBadge status="reviewed" happened={o.happened} />} />
      <p className="whitespace-pre-wrap text-sm text-ink">{o.what_happened}</p>
      {o.lesson && (
        <div className="mt-4 rounded-lg wash-accent p-3.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-2">Lesson</p>
          <p className="mt-1 text-sm text-ink">{o.lesson}</p>
        </div>
      )}
      {d.brier != null && (
        <p className="mt-4 text-sm text-ink-2">
          This forecast scored <strong className="font-semibold text-ink">{fixed(d.brier)}</strong>{" "}
          (Brier: 0 is perfect, 0.25 is a coin flip). You said {pct(d.confidence)}.
        </p>
      )}
      {o.review_status === "failed" && (
        <div className="mt-4 rounded-lg wash-critical p-3.5 text-sm">
          <p className="font-medium text-ink">The review didn't finish: {o.review_error}</p>
          <Button size="sm" variant="secondary" className="mt-3" loading={retry.isPending} onClick={() => retry.mutate()}>
            <RotateCcw className="size-3.5" aria-hidden /> Retry review
          </Button>
        </div>
      )}
    </Card>
  );
}

function HistoryCard({ decision: d }: { decision: Detail }) {
  if (d.repeat_warnings.length === 0 && d.similar.length === 0) return null;
  return (
    <Card>
      <CardHeader title="You've been here before" subtitle="Similar earlier decisions, found by embedding similarity" />
      {d.repeat_warnings.length > 0 && (
        <ul className="mb-4 space-y-2.5">
          {d.repeat_warnings.map((w) => (
            <li key={`${w.past_decision_id}-${w.assumption}`} className="rounded-lg wash-warning p-3.5 text-sm">
              <p className="flex items-start gap-1.5 font-medium text-ink">
                <History className="mt-0.5 size-4 shrink-0" aria-hidden /> “{w.assumption}”
              </p>
              <p className="mt-1 text-ink-2">{w.note}</p>
              <Link to={`/decisions/${w.past_decision_id}`} className="mt-1 inline-block text-accent-ink hover:underline">
                See that decision
              </Link>
            </li>
          ))}
        </ul>
      )}
      {d.similar.length > 0 && (
        <ul className="space-y-3">
          {d.similar.map((s) => (
            <li key={s.id} className="text-sm">
              <div className="flex items-center gap-2">
                {s.happened ? (
                  <CircleCheck className="size-4 shrink-0 text-good" aria-label="Happened" />
                ) : (
                  <CircleX className="size-4 shrink-0 text-critical" aria-label="Didn't happen" />
                )}
                <Link to={`/decisions/${s.id}`} className="min-w-0 flex-1 truncate font-medium text-ink hover:underline">
                  {s.title}
                </Link>
                <span className="tabular text-xs text-ink-3">{pct(s.similarity)} similar</span>
              </div>
              {s.failed_assumptions.length > 0 && (
                <ul className="ml-6 mt-1 space-y-0.5 text-xs text-ink-2">
                  {s.failed_assumptions.map((f) => (
                    <li key={f}>failed: “{f}”</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function DecisionDetailPage() {
  const id = Number(useParams().id);
  const { workspace } = usePreferences();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const decision = useQuery({
    queryKey: ["decision", workspace, id],
    queryFn: () => api.decision(workspace, id),
    enabled: Number.isFinite(id),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteDecision(workspace, id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["insights", workspace] });
      void queryClient.invalidateQueries({ queryKey: ["decisions", workspace] });
      navigate("/decisions");
    },
  });

  if (decision.isPending) return <Spinner />;
  if (decision.isError) {
    if (decision.error instanceof ApiError && decision.error.status === 404)
      return (
        <Card>
          <EmptyState
            title="Decision not found"
            body="It may have been deleted, or it belongs to the other workspace."
            action={<Link to="/decisions" className="text-sm font-medium text-accent-ink hover:underline">Back to decisions</Link>}
          />
        </Card>
      );
    return <ErrorState error={decision.error} onRetry={() => decision.refetch()} />;
  }

  const d = decision.data;
  return (
    <>
      <Link to="/decisions" className="mb-4 inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Decisions
      </Link>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-[28px]">{d.title}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-ink-2">
          <StatusBadge status={d.status} happened={d.happened} />
          <Badge>{DOMAIN_LABEL[d.domain]}</Badge>
          <span>{pct(d.confidence)} sure</span>
          <span aria-hidden>·</span>
          <span className="inline-flex items-center gap-1">
            <Lock className="size-3.5" aria-hidden /> logged {formatDay(d.created_at, true)}
          </span>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <div className="space-y-6">
          <Card>
            <CardHeader title="Your reasoning" subtitle="Locked when you saved it, so hindsight can't edit it." />
            <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-ink">{d.reasoning}</p>
            <dl className="mt-5 grid gap-4 border-t border-line pt-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-ink-3">Expected outcome</dt>
                <dd className="mt-0.5 text-ink">{d.expected_outcome}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-3">Alternatives considered</dt>
                <dd className="mt-0.5 text-ink">{d.alternatives ?? <span className="text-ink-3">none written down</span>}</dd>
              </div>
            </dl>
          </Card>
          <AuditCard decision={d} />
        </div>
        <div className="space-y-6">
          {d.outcome ? <OutcomeCard decision={d} /> : <OutcomeForm decision={d} />}
          <HistoryCard decision={d} />
          <Button
            variant="danger"
            size="sm"
            loading={remove.isPending}
            onClick={() => {
              if (window.confirm("Delete this decision permanently? This can't be undone.")) remove.mutate();
            }}
          >
            <Trash2 className="size-3.5 text-critical" aria-hidden /> Delete decision
          </Button>
        </div>
      </div>
    </>
  );
}
