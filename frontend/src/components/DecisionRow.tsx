import { ChevronRight } from "lucide-react";
import { Link } from "react-router";

import { DOMAIN_LABEL, formatDay, pct, relativeDay } from "../lib/format";
import type { DecisionSummary } from "../lib/types";
import { StatusBadge } from "./ui";

export function DecisionRow({ decision: d }: { decision: DecisionSummary }) {
  const when =
    d.status === "reviewed"
      ? `logged ${formatDay(d.created_at, true)}`
      : d.status === "due"
        ? `review was due ${relativeDay(d.review_at)}`
        : `review ${relativeDay(d.review_at)}`;
  return (
    <li>
      <Link
        to={`/decisions/${d.id}`}
        className="group grid grid-cols-[1fr_auto] items-center gap-x-4 rounded-lg px-3 py-3 transition hover:bg-surface-2"
      >
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-ink">{d.title}</div>
          <div className="mt-0.5 text-xs text-ink-3">
            {DOMAIN_LABEL[d.domain]} · {pct(d.confidence)} sure · {when}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {d.failed_count > 0 && (
            <span className="hidden text-xs text-ink-2 sm:inline">
              {d.failed_count} of {d.assumption_count} assumptions failed
            </span>
          )}
          <StatusBadge status={d.status} happened={d.happened} />
          <ChevronRight className="size-4 text-ink-3 transition group-hover:translate-x-0.5" aria-hidden />
        </div>
      </Link>
    </li>
  );
}
