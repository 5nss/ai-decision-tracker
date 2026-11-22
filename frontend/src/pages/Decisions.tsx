import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Plus, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { DecisionRow } from "../components/DecisionRow";
import { Card, EmptyState, ErrorState, PageHeader, SegmentedControl, Spinner, buttonTone, inputClass } from "../components/ui";
import { api } from "../lib/api";
import { DOMAIN_LABEL } from "../lib/format";
import { usePreferences } from "../lib/preferences";
import { DOMAINS } from "../lib/types";
import type { Domain, Status } from "../lib/types";

type StatusFilter = Status | "all";

export function Decisions() {
  const { workspace } = usePreferences();
  const [params, setParams] = useSearchParams();
  const status = (params.get("status") as StatusFilter | null) ?? "all";
  const domain = (params.get("domain") as Domain | null) ?? undefined;
  const [search, setSearch] = useState(params.get("q") ?? "");
  const [q, setQ] = useState(search);

  useEffect(() => {
    const handle = setTimeout(() => setQ(search.trim()), 250);
    return () => clearTimeout(handle);
  }, [search]);

  const update = (key: string, value: string | undefined) => {
    const next = new URLSearchParams(params);
    if (value && value !== "all") next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const filters = { status: status === "all" ? undefined : status, domain, q: q || undefined };
  const decisions = useQuery({
    queryKey: ["decisions", workspace, filters],
    queryFn: () => api.decisions(workspace, filters),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader
        title="Decisions"
        subtitle="Every decision you've logged. Reasoning is locked at the moment you save it."
        action={
          <Link to="/new" className={clsx("inline-flex h-10 items-center gap-2 rounded-lg px-4 text-sm font-medium", buttonTone("primary"))}>
            <Plus className="size-4" aria-hidden /> Log a decision
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SegmentedControl<StatusFilter>
          label="Status"
          value={status}
          onChange={(v) => update("status", v)}
          options={[
            { value: "all", label: "All" },
            { value: "due", label: "Due" },
            { value: "open", label: "Open" },
            { value: "reviewed", label: "Reviewed" },
          ]}
        />
        <select
          aria-label="Domain"
          className={clsx(inputClass, "h-9 w-auto py-0")}
          value={domain ?? "all"}
          onChange={(e) => update("domain", e.target.value)}
        >
          <option value="all">All domains</option>
          {DOMAINS.map((d) => (
            <option key={d} value={d}>
              {DOMAIN_LABEL[d]}
            </option>
          ))}
        </select>
        <label className="relative min-w-[200px] flex-1 sm:max-w-xs">
          <span className="sr-only">Search titles</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
          <input
            className={clsx(inputClass, "h-9 pl-9")}
            placeholder="Search titles"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              update("q", e.target.value.trim() || undefined);
            }}
          />
        </label>
      </div>

      {decisions.isError ? (
        <ErrorState error={decisions.error} onRetry={() => decisions.refetch()} />
      ) : (
        <Card className={clsx("p-2 transition-opacity sm:p-3", decisions.isPlaceholderData && "opacity-60")}>
          {decisions.isPending ? (
            <Spinner />
          ) : decisions.data.length === 0 ? (
            <EmptyState
              title={status === "all" && !domain && !q ? "No decisions yet" : "Nothing matches these filters"}
              body={status === "all" && !domain && !q ? "Log your first decision to start building a track record." : undefined}
            />
          ) : (
            <>
              <p className="px-3 pb-1 pt-2 text-xs text-ink-3">{decisions.data.length} decisions</p>
              <ul>
                {decisions.data.map((d) => (
                  <DecisionRow key={d.id} decision={d} />
                ))}
              </ul>
            </>
          )}
        </Card>
      )}
    </>
  );
}
