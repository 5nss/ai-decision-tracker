import { useMutation, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Lock, Sparkles } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router";

import { Button, Card, CardHeader, Field, PageHeader, inputClass } from "../components/ui";
import { api } from "../lib/api";
import { DOMAIN_LABEL, isoDayFromToday } from "../lib/format";
import { usePreferences } from "../lib/preferences";
import { DOMAINS } from "../lib/types";
import type { Domain } from "../lib/types";

const PRESETS = [
  { label: "1 week", days: 7 },
  { label: "2 weeks", days: 14 },
  { label: "1 month", days: 30 },
  { label: "3 months", days: 90 },
];

export function NewDecision() {
  const { workspace } = usePreferences();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState("");
  const [reasoning, setReasoning] = useState("");
  const [alternatives, setAlternatives] = useState("");
  const [expected, setExpected] = useState("");
  const [confidence, setConfidence] = useState(75);
  const [domain, setDomain] = useState<Domain>("career");
  const [reviewAt, setReviewAt] = useState(isoDayFromToday(14));

  const create = useMutation({
    mutationFn: () =>
      api.createDecision(workspace, {
        title: title.trim(),
        reasoning: reasoning.trim(),
        alternatives: alternatives.trim() || undefined,
        expected_outcome: expected.trim(),
        confidence: confidence / 100,
        domain,
        review_at: reviewAt,
      }),
    onSuccess: (decision) => {
      queryClient.setQueryData(["decision", workspace, decision.id], decision);
      void queryClient.invalidateQueries({ queryKey: ["insights", workspace] });
      void queryClient.invalidateQueries({ queryKey: ["decisions", workspace] });
      void queryClient.invalidateQueries({ queryKey: ["traces"] });
      navigate(`/decisions/${decision.id}`);
    },
  });

  const valid = title.trim().length >= 3 && reasoning.trim().length >= 20 && expected.trim().length >= 3;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (valid && !create.isPending) create.mutate();
  };

  return (
    <>
      <PageHeader
        title="Log a decision"
        subtitle={
          workspace === "demo"
            ? "This goes into the demo journal. Switch to Personal in the sidebar to keep your own."
            : "Write it the way you'd explain it to a friend. You can't edit it later, and that's the point."
        }
      />
      <div className="grid gap-6 xl:grid-cols-[1fr_300px]">
        <Card>
          <form className="space-y-5" onSubmit={submit}>
            <Field label="What are you deciding?" htmlFor="title" hint="One line, e.g. “Learn Docker over one weekend before the internship”.">
              <input id="title" className={inputClass} value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} required />
            </Field>
            <Field label="Why? Your reasoning" htmlFor="reasoning" hint="What you expect, what you're counting on, what you think will happen. At least 20 characters.">
              <textarea id="reasoning" className={clsx(inputClass, "min-h-32")} value={reasoning} maxLength={5000} onChange={(e) => setReasoning(e.target.value)} required />
            </Field>
            <Field label="Alternatives you considered" htmlFor="alternatives" hint="Optional, but the audit flags it if you list none.">
              <input id="alternatives" className={inputClass} value={alternatives} maxLength={2000} onChange={(e) => setAlternatives(e.target.value)} />
            </Field>
            <Field label="Expected outcome" htmlFor="expected" hint="Something you'll be able to answer yes or no on the review date.">
              <input id="expected" className={inputClass} value={expected} maxLength={1000} onChange={(e) => setExpected(e.target.value)} required />
            </Field>

            <div className="space-y-2">
              <div className="flex items-baseline justify-between">
                <label htmlFor="confidence" className="text-sm font-medium text-ink">
                  How sure are you it'll happen?
                </label>
                <span className="text-2xl font-semibold text-ink">{confidence}%</span>
              </div>
              <input
                id="confidence"
                type="range"
                min={50}
                max={99}
                value={confidence}
                onChange={(e) => setConfidence(Number(e.target.value))}
                className="w-full accent-[var(--accent)]"
              />
              <p className="text-xs text-ink-3">
                Out of 10 decisions you're this sure about, about {Math.round(confidence / 10)} should work out.
              </p>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Domain" htmlFor="domain">
                <select id="domain" className={inputClass} value={domain} onChange={(e) => setDomain(e.target.value as Domain)}>
                  {DOMAINS.map((d) => (
                    <option key={d} value={d}>
                      {DOMAIN_LABEL[d]}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Review on" htmlFor="review">
                <input id="review" type="date" className={inputClass} value={reviewAt} min={isoDayFromToday(0)} onChange={(e) => setReviewAt(e.target.value)} required />
              </Field>
            </div>
            <div className="-mt-2 flex flex-wrap gap-2">
              {PRESETS.map((p) => (
                <button
                  key={p.days}
                  type="button"
                  onClick={() => setReviewAt(isoDayFromToday(p.days))}
                  className={clsx(
                    "rounded-full border border-line px-3 py-1 text-xs font-medium transition",
                    reviewAt === isoDayFromToday(p.days) ? "bg-ink text-surface" : "text-ink-2 hover:bg-surface-2",
                  )}
                >
                  in {p.label}
                </button>
              ))}
            </div>

            {create.isError && (
              <p className="rounded-lg wash-critical px-3 py-2 text-sm text-ink" role="alert">
                {create.error.message}
              </p>
            )}
            <div className="flex items-center gap-3 border-t border-line pt-5">
              <Button type="submit" disabled={!valid} loading={create.isPending}>
                {create.isPending ? "Auditing your reasoning" : "Save and audit"}
              </Button>
              <span className="flex items-center gap-1.5 text-xs text-ink-3">
                <Lock className="size-3.5" aria-hidden /> Reasoning is locked once saved
              </span>
            </div>
          </form>
        </Card>

        <Card className="h-fit">
          <CardHeader title="What happens next" />
          <ol className="space-y-4 text-sm text-ink-2">
            <li className="flex gap-3">
              <Sparkles className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
              <span>
                <strong className="font-medium text-ink">Audit, right away.</strong> The assumptions this
                depends on, what you're not considering, and a one-line pre-mortem.
              </span>
            </li>
            <li className="flex gap-3">
              <Sparkles className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
              <span>
                <strong className="font-medium text-ink">“You've assumed this before.”</strong> Similar past
                decisions, and the assumptions that failed in them.
              </span>
            </li>
            <li className="flex gap-3">
              <Sparkles className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
              <span>
                <strong className="font-medium text-ink">Review on the date.</strong> Say what happened. Each
                assumption is judged held or failed, and your confidence is scored.
              </span>
            </li>
          </ol>
        </Card>
      </div>
    </>
  );
}
