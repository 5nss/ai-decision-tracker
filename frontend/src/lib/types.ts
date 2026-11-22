// Mirrors backend/hindsight/schemas.py.

export type Workspace = "demo" | "personal";
export type Status = "open" | "due" | "reviewed";
export type Verdict = "held" | "failed" | "unclear";
export type Category = "time" | "self" | "people" | "money" | "external" | "other";
export type Risk = "low" | "medium" | "high";

export const DOMAINS = [
  "career",
  "study",
  "projects",
  "health",
  "money",
  "relationships",
  "other",
] as const;
export type Domain = (typeof DOMAINS)[number];

export interface Assumption {
  id: number;
  text: string;
  category: Category;
  risk: Risk;
  verdict: Verdict | null;
  evidence: string | null;
  evidence_grounded: boolean | null;
}

export interface Outcome {
  happened: boolean;
  what_happened: string;
  lesson: string | null;
  review_status: "pending" | "done" | "failed";
  review_error: string | null;
  created_at: string;
}

export interface SimilarDecision {
  id: number;
  title: string;
  similarity: number;
  happened: boolean;
  failed_assumptions: string[];
}

export interface RepeatWarning {
  assumption: string;
  past_decision_id: number;
  note: string;
}

export interface DecisionSummary {
  id: number;
  title: string;
  domain: Domain;
  confidence: number;
  created_at: string;
  review_at: string;
  status: Status;
  audit_status: "pending" | "done" | "failed";
  happened: boolean | null;
  assumption_count: number;
  failed_count: number;
}

export interface DecisionDetail extends DecisionSummary {
  reasoning: string;
  alternatives: string | null;
  expected_outcome: string;
  premortem: string | null;
  missing_considerations: string[];
  repeat_warnings: RepeatWarning[];
  audit_error: string | null;
  audit_provider: string | null;
  assumptions: Assumption[];
  outcome: Outcome | null;
  similar: SimilarDecision[];
  brier: number | null;
}

export interface DecisionCreate {
  title: string;
  reasoning: string;
  alternatives?: string;
  expected_outcome: string;
  confidence: number;
  domain: Domain;
  review_at: string;
}

export interface CalibrationBin {
  lo: number;
  hi: number;
  n: number;
  mean_confidence: number | null;
  hit_rate: number | null;
}

export interface CalibrationGroup {
  n: number;
  brier: number | null;
  hit_rate: number;
  mean_confidence: number;
}

export interface TrendPoint extends CalibrationGroup {
  month: string;
}

export interface Calibration {
  n: number;
  brier: number | null;
  skill_score: number | null;
  base_rate: number | null;
  mean_confidence: number | null;
  overconfidence: number | null;
  bins: CalibrationBin[];
  trend: TrendPoint[];
  by_domain: (CalibrationGroup & { domain: string })[];
  small_sample: boolean;
}

export interface Pattern {
  category: Category;
  failed: number;
  held: number;
  unclear: number;
  judged: number;
  failure_rate: number | null;
  lower_bound: number;
  examples: { decision_id: number; decision_title: string; text: string }[];
}

export interface Insights {
  counts: { total: number; open: number; due: number; reviewed: number };
  calibration: Calibration;
  patterns: { patterns: Pattern[]; emerging: Pattern[]; min_judged: number };
}

export interface Health {
  status: "ok";
  version: string;
  provider: string;
  model: string;
  embed_model: string;
  offline: boolean;
}

export interface TraceCall {
  id: number;
  created_at: string;
  workspace: string | null;
  decision_id: number | null;
  operation: string;
  provider: string;
  model: string;
  model_version: string | null;
  latency_ms: number;
  attempts: number;
  input_tokens: number | null;
  output_tokens: number | null;
  ok: boolean;
  error: string | null;
}

export interface OperationStats {
  operation: string;
  provider: string;
  calls: number;
  errors: number;
  p50_ms: number | null;
  p95_ms: number | null;
  input_tokens: number;
  output_tokens: number;
}

export interface Traces {
  total_calls: number;
  error_rate: number | null;
  by_operation: OperationStats[];
  calls: TraceCall[];
}

// ── eval report (backend/evals/run.py) ─────────────────────────────────────────

export interface PRF {
  precision: number;
  recall: number;
  f1: number;
  matched: number;
  n_pred: number;
  n_gold: number;
}

export interface ExtractionResult extends PRF {
  system: string;
  label: string;
  category_accuracy: number | null;
  sensitivity: (PRF & { threshold: number })[];
  failures: number;
}

export interface VerdictResult {
  system: string;
  label: string;
  n: number;
  accuracy: number;
  macro_f1: number;
  labels: Verdict[];
  confusion: number[][];
  per_label: Record<Verdict, { precision: number; recall: number; f1: number; support: number }>;
  grounding_rate: number | null;
  errors: { key: string; assumption: string; gold: Verdict; predicted: Verdict; evidence: string }[];
}

export interface EvalReport {
  generated_at: string;
  dataset: {
    name: string;
    decisions: number;
    reviewed: number;
    assumptions: number;
    judged_assumptions: number;
    themes: number;
  };
  systems: { name: string; label: string; embed_model: string; model_versions: string[] }[];
  run: { seconds: number; api_calls: number; api_errors: number };
  extraction?: {
    n_cases: number;
    matcher: { kind: string; threshold: number };
    results: ExtractionResult[];
    examples: { key: string; title: string; gold: string[]; predictions: Record<string, string[]> }[];
  };
  verdicts?: { n: number; labels: Verdict[]; results: VerdictResult[] };
  retrieval?: {
    k: number;
    n_queries: number;
    results: { system: string; recall_at_k: number; mrr: number }[];
    thresholds: {
      embedding: string;
      relevant_mean: number;
      irrelevant_mean: number;
      threshold: number | null;
      f1: number;
    }[];
  };
}
