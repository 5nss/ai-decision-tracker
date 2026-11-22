import type {
  DecisionCreate,
  DecisionDetail,
  DecisionSummary,
  Domain,
  EvalReport,
  Health,
  Insights,
  Status,
  Traces,
  Workspace,
} from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function describe(body: unknown): string | null {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: (string | number)[]; msg?: string }) => {
        const field = d.loc?.[d.loc.length - 1];
        return field ? `${String(field).replaceAll("_", " ")}: ${d.msg}` : d.msg;
      })
      .join("; ");
  }
  return null;
}

async function request<T>(path: string, workspace: Workspace | null, init: RequestInit = {}) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (workspace) headers["X-Workspace"] = workspace;
  const response = await fetch(`/api${path}`, { ...init, headers });
  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, describe(body) ?? response.statusText);
  return body as T;
}

export interface DecisionFilters {
  status?: Status;
  domain?: Domain;
  q?: string;
}

export const api = {
  health: () => request<Health>("/health", null),
  insights: (ws: Workspace) => request<Insights>("/insights", ws),
  decisions: (ws: Workspace, filters: DecisionFilters = {}) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value);
    const query = params.toString();
    return request<DecisionSummary[]>(`/decisions${query ? `?${query}` : ""}`, ws);
  },
  decision: (ws: Workspace, id: number) => request<DecisionDetail>(`/decisions/${id}`, ws),
  createDecision: (ws: Workspace, body: DecisionCreate) =>
    request<DecisionDetail>("/decisions", ws, { method: "POST", body: JSON.stringify(body) }),
  recordOutcome: (ws: Workspace, id: number, body: { happened: boolean; what_happened: string }) =>
    request<DecisionDetail>(`/decisions/${id}/outcome`, ws, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  retryAudit: (ws: Workspace, id: number) =>
    request<DecisionDetail>(`/decisions/${id}/audit`, ws, { method: "POST" }),
  retryReview: (ws: Workspace, id: number) =>
    request<DecisionDetail>(`/decisions/${id}/review`, ws, { method: "POST" }),
  deleteDecision: (ws: Workspace, id: number) =>
    request<void>(`/decisions/${id}`, ws, { method: "DELETE" }),
  resetDemo: () => request<void>("/demo/reset", "demo", { method: "POST" }),
  traces: () => request<Traces>("/traces?limit=100", null),
  evals: () => request<EvalReport>("/evals", null),
};
