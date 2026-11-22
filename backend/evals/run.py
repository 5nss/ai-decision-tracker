"""Score the auditors against the hand-labeled demo journal.

    python -m evals.run                       # heuristic, plus Gemini if GEMINI_API_KEY is set
    python -m evals.run --systems heuristic   # offline only
    python -m evals.run --tasks verdicts --limit 5

Gemini responses are cached in evals/.cache under a hash of the exact prompt, so re-runs cost
nothing and an interrupted run resumes where it stopped. Changing a prompt invalidates only the
affected entries. Results go to evals/results/latest.json (rendered by the Evals page) and
latest.md (pasted into the README).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean

import numpy as np

from hindsight.ai import AuditorError, prompts
from hindsight.ai.base import CallRecord
from hindsight.ai.gemini import GeminiAuditor
from hindsight.ai.heuristic import HeuristicAuditor
from hindsight.ai.text import overlap_coefficient
from hindsight.config import get_settings
from hindsight.services.retrieval import embedding_text
from hindsight.services.review import is_grounded

from .baselines import TfIdf, outcome_polarity_verdicts, rank_by_domain_recency
from .dataset import Case, load_cases
from .metrics import (
    best_threshold,
    classification_report,
    greedy_match,
    precision_recall_f1,
    recall_at_k,
    reciprocal_rank,
)

EVALS_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVALS_DIR / "results"
CACHE_DIR = EVALS_DIR / ".cache"
VERDICT_LABELS = ("held", "failed", "unclear")
K = 3
TASKS = ("extraction", "verdicts", "retrieval")


def _hash(*parts: str) -> str:
    return hashlib.sha1("\x1f".join(parts).encode()).hexdigest()[:16]


class Cache:
    """In-memory dict, mirrored to disk when enabled."""

    def __init__(self, path: Path, enabled: bool) -> None:
        self.path, self.enabled = path, enabled
        self.data: dict = {}
        if enabled and path.is_file():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    def get(self, key: str):
        return self.data.get(key)

    def put(self, key: str, value) -> None:
        self.data[key] = value
        self.save()

    def save(self) -> None:
        if self.enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data), encoding="utf-8")


class RateLimiter:
    def __init__(self, rpm: float) -> None:
        self.interval = 60.0 / rpm if rpm > 0 else 0.0
        self._last = float("-inf")

    def wait(self) -> None:
        delay = self._last + self.interval - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()


class VersionTracer:
    """Keeps the exact model versions the API reported, so results are attributable."""

    def __init__(self) -> None:
        self.versions: set[str] = set()
        self.calls = 0
        self.errors = 0

    def record(self, rec: CallRecord) -> None:
        self.calls += 1
        self.errors += not rec.ok
        if rec.model_version:
            self.versions.add(rec.model_version)


class Runner:
    def __init__(self, systems: dict, use_cache: bool, rpm: float) -> None:
        self.systems = systems
        self.gen = Cache(CACHE_DIR / "generations.json", use_cache)
        self.emb = Cache(CACHE_DIR / "embeddings.json", use_cache)
        self.limiter = RateLimiter(rpm)
        self.tracer = VersionTracer()

    @staticmethod
    def remote(auditor) -> bool:
        return auditor.provider == "gemini"

    def extract(self, auditor, case: Case) -> list[dict] | None:
        if not self.remote(auditor):
            result = auditor.audit(case.decision, [])
            return [{"text": a.text, "category": str(a.category)} for a in result.assumptions]
        key = _hash(
            "audit", auditor.label, prompts.AUDIT_SYSTEM, prompts.audit_prompt(case.decision, [])
        )
        cached = self.gen.get(key)
        if cached is None:
            self.limiter.wait()
            try:
                result = auditor.audit(case.decision, [], tracer=self.tracer)
            except AuditorError as exc:
                print(f"  ! extraction failed for {case.key}: {exc}", file=sys.stderr)
                return None
            cached = [{"text": a.text, "category": str(a.category)} for a in result.assumptions]
            self.gen.put(key, cached)
        return cached

    def review(self, auditor, case: Case) -> dict[int, tuple[str, str]] | None:
        judge = case.to_judge()
        if not self.remote(auditor):
            result = auditor.review(case.decision, judge, case.happened, case.what_happened)
            return {v.assumption_id: (str(v.verdict), v.evidence) for v in result.verdicts}
        prompt = prompts.review_prompt(case.decision, judge, case.happened, case.what_happened)
        key = _hash("review", auditor.label, prompts.REVIEW_SYSTEM, prompt)
        cached = self.gen.get(key)
        if cached is None:
            self.limiter.wait()
            try:
                result = auditor.review(
                    case.decision, judge, case.happened, case.what_happened, tracer=self.tracer
                )
            except AuditorError as exc:
                print(f"  ! review failed for {case.key}: {exc}", file=sys.stderr)
                return None
            cached = [[v.assumption_id, str(v.verdict), v.evidence] for v in result.verdicts]
            self.gen.put(key, cached)
        return {aid: (verdict, evidence) for aid, verdict, evidence in cached}

    def embed(self, auditor, texts: list[str]) -> np.ndarray:
        if not self.remote(auditor):
            return np.vstack(auditor.embed(texts))
        keys = [_hash(auditor.embed_model, t) for t in texts]
        missing = sorted({t for t, k in zip(texts, keys, strict=True) if self.emb.get(k) is None})
        if missing:
            self.limiter.wait()
            vectors = auditor.embed(missing, tracer=self.tracer)
            for text, vec in zip(missing, vectors, strict=True):
                self.emb.data[_hash(auditor.embed_model, text)] = [round(float(x), 6) for x in vec]
            self.emb.save()
        return np.vstack([np.asarray(self.emb.get(k), dtype=np.float32) for k in keys])


# ── matchers for extraction ─────────────────────────────────────────────────────


class LexicalMatcher:
    threshold = 0.5
    sweep = (0.4, 0.5, 0.6)

    def describe(self) -> dict:
        return {"kind": "lexical overlap coefficient", "threshold": self.threshold}

    def similarity(self, preds: list[str], golds: list[str]) -> np.ndarray:
        if not preds or not golds:
            return np.zeros((len(preds), len(golds)))
        return np.array([[overlap_coefficient(p, g) for g in golds] for p in preds])


class EmbeddingMatcher:
    threshold = 0.8
    sweep = (0.75, 0.8, 0.85)

    def __init__(self, runner: Runner, auditor: GeminiAuditor) -> None:
        self.runner, self.auditor = runner, auditor

    def describe(self) -> dict:
        return {"kind": f"cosine of {self.auditor.embed_model}", "threshold": self.threshold}

    def similarity(self, preds: list[str], golds: list[str]) -> np.ndarray:
        if not preds or not golds:
            return np.zeros((len(preds), len(golds)))
        return self.runner.embed(self.auditor, preds) @ self.runner.embed(self.auditor, golds).T


# ── tasks ──────────────────────────────────────────────────────────────────────


def run_extraction(runner: Runner, cases: list[Case], matcher) -> dict:
    results, examples = [], {}
    for name, auditor in runner.systems.items():
        totals = {t: [0, 0, 0] for t in matcher.sweep}  # matched, n_pred, n_gold
        category_hits = matched = failures = 0
        for case in cases:
            preds = runner.extract(auditor, case)
            if preds is None:
                failures += 1
                preds = []
            gold = [a.text for a in case.assumptions]
            sim = matcher.similarity([p["text"] for p in preds], gold)
            for t in matcher.sweep:
                pairs = greedy_match(sim, t)
                totals[t][0] += len(pairs)
                totals[t][1] += len(preds)
                totals[t][2] += len(gold)
            pairs = greedy_match(sim, matcher.threshold)
            matched += len(pairs)
            category_hits += sum(
                preds[i]["category"] == case.assumptions[j].category for i, j, _ in pairs
            )
            entry = examples.setdefault(
                case.key,
                {"key": case.key, "title": case.decision.title, "gold": gold, "predictions": {}},
            )
            entry["predictions"][name] = [p["text"] for p in preds]
        results.append(
            {
                "system": name,
                "label": auditor.label,
                **precision_recall_f1(*totals[matcher.threshold]),
                "category_accuracy": category_hits / matched if matched else None,
                "sensitivity": [
                    {"threshold": t, **precision_recall_f1(*totals[t])} for t in matcher.sweep
                ],
                "failures": failures,
            }
        )
    return {
        "n_cases": len(cases),
        "matcher": matcher.describe(),
        "results": results,
        "examples": list(examples.values())[:6],
    }


def run_verdicts(runner: Runner, reviewed: list[Case]) -> dict:
    gold = [a.verdict for c in reviewed for a in c.assumptions]
    baseline_pred = [v for c in reviewed for v in outcome_polarity_verdicts(c)]
    results = [
        {
            "system": "outcome-polarity",
            "label": "baseline: every assumption takes the outcome's polarity",
            **classification_report(gold, baseline_pred, VERDICT_LABELS),
            "grounding_rate": None,
            "errors": [],
        }
    ]
    for name, auditor in runner.systems.items():
        pred, errors = [], []
        quotes = grounded = failures = 0
        for case in reviewed:
            verdicts = runner.review(auditor, case)
            if verdicts is None:
                failures += 1
                verdicts = {}
            for a in case.assumptions:
                verdict, evidence = verdicts.get(a.id, ("unclear", ""))
                pred.append(verdict)
                if verdict != "unclear" and evidence:
                    quotes += 1
                    grounded += is_grounded(evidence, case.what_happened)
                if verdict != a.verdict and len(errors) < 8:
                    errors.append(
                        {
                            "key": case.key,
                            "assumption": a.text,
                            "gold": a.verdict,
                            "predicted": verdict,
                            "evidence": evidence,
                        }
                    )
        results.append(
            {
                "system": name,
                "label": auditor.label,
                **classification_report(gold, pred, VERDICT_LABELS),
                "grounding_rate": grounded / quotes if quotes else None,
                "errors": errors,
                "failures": failures,
            }
        )
    return {"n": len(gold), "labels": list(VERDICT_LABELS), "results": results}


def _ranking_scores(name: str, ranked: list[list[str]], reviewed: list[Case]) -> dict:
    relevant = [
        {o.key for o in reviewed if o.theme == c.theme and o.key != c.key} for c in reviewed
    ]
    return {
        "system": name,
        "recall_at_k": fmean(
            recall_at_k(r, rel, K) for r, rel in zip(ranked, relevant, strict=True)
        ),
        "mrr": fmean(reciprocal_rank(r, rel) for r, rel in zip(ranked, relevant, strict=True)),
    }


def run_retrieval(runner: Runner, reviewed: list[Case]) -> dict:
    keys = [c.key for c in reviewed]
    texts = [
        embedding_text(c.decision.title, c.decision.reasoning, c.decision.expected_outcome)
        for c in reviewed
    ]
    results = [
        _ranking_scores(
            "v1 rule: same domain, most recent",
            [rank_by_domain_recency(c, [o for o in reviewed if o.key != c.key]) for c in reviewed],
            reviewed,
        )
    ]

    tfidf = TfIdf(texts)
    similarity = {"TF-IDF (lexical)": tfidf.matrix @ tfidf.matrix.T}
    for auditor in runner.systems.values():
        matrix = runner.embed(auditor, texts)
        similarity[f"{auditor.embed_model} embeddings"] = matrix @ matrix.T

    thresholds = []
    for name, sims in similarity.items():
        ranked, positives, negatives = [], [], []
        for i, case in enumerate(reviewed):
            order = [j for j in np.argsort(-sims[i], kind="stable") if j != i]
            ranked.append([keys[j] for j in order])
            for j, other in enumerate(reviewed):
                if j != i:
                    bucket = positives if other.theme == case.theme else negatives
                    bucket.append(float(sims[i, j]))
        results.append(_ranking_scores(name, ranked, reviewed))
        if name.endswith("embeddings"):
            thresholds.append(
                {
                    "embedding": name,
                    "relevant_mean": fmean(positives),
                    "irrelevant_mean": fmean(negatives),
                    **best_threshold(positives, negatives),
                }
            )
    return {"k": K, "n_queries": len(reviewed), "results": results, "thresholds": thresholds}


# ── reporting ──────────────────────────────────────────────────────────────────


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def to_markdown(report: dict) -> str:
    lines = [f"_Generated {report['generated_at']} on {report['dataset']['name']}._", ""]
    if ex := report.get("extraction"):
        m = ex["matcher"]
        lines += [
            f"**Assumption extraction** ({ex['n_cases']} decisions; match = {m['kind']} ≥ {m['threshold']})",
            "",
            "| System | Precision | Recall | F1 | Category accuracy |",
            "|---|---|---|---|---|",
        ]
        for r in ex["results"]:
            lines.append(
                f"| {r['label']} | {_pct(r['precision'])} | {_pct(r['recall'])} | "
                f"{_pct(r['f1'])} | {_pct(r['category_accuracy'])} |"
            )
        lines.append("")
    if vd := report.get("verdicts"):
        lines += [
            f"**Assumption verdicts** ({vd['n']} assumptions: held / failed / unclear)",
            "",
            "| System | Accuracy | Macro-F1 | Evidence grounded |",
            "|---|---|---|---|",
        ]
        for r in vd["results"]:
            lines.append(
                f"| {r['label']} | {_pct(r['accuracy'])} | {_pct(r['macro_f1'])} | "
                f"{_pct(r['grounding_rate'])} |"
            )
        lines.append("")
    if rt := report.get("retrieval"):
        lines += [
            f"**Similar-decision retrieval** ({rt['n_queries']} queries; relevant = same theme)",
            "",
            f"| Method | Recall@{rt['k']} | MRR |",
            "|---|---|---|",
        ]
        for r in rt["results"]:
            lines.append(f"| {r['system']} | {_pct(r['recall_at_k'])} | {r['mrr']:.3f} |")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--systems", default="auto", help="auto, or a comma list of heuristic,gemini"
    )
    parser.add_argument("--tasks", default=",".join(TASKS))
    parser.add_argument("--limit", type=int, default=None, help="only the first N decisions")
    parser.add_argument("--rpm", type=float, default=8.0, help="max Gemini requests per minute")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "latest.json")
    args = parser.parse_args(argv)

    settings = get_settings()
    has_key = bool(settings.gemini_api_key and settings.gemini_api_key.strip())
    wanted = (
        (["heuristic", "gemini"] if has_key else ["heuristic"])
        if args.systems == "auto"
        else [s.strip() for s in args.systems.split(",") if s.strip()]
    )
    systems: dict = {}
    for name in wanted:
        if name == "heuristic":
            systems[name] = HeuristicAuditor()
        elif name == "gemini":
            if not has_key:
                parser.error("gemini requested but GEMINI_API_KEY is not set")
            systems[name] = GeminiAuditor(
                api_key=settings.gemini_api_key.strip(),
                model=settings.llm_model,
                embed_model=settings.embed_model,
                embed_dim=settings.embed_dim,
                timeout_s=settings.llm_timeout_s,
                retries=settings.llm_retries + 2,  # evals can afford to wait out rate limits
            )
        else:
            parser.error(f"unknown system {name!r}")

    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
    if unknown := set(tasks) - set(TASKS):
        parser.error(f"unknown task(s): {sorted(unknown)}")

    cases = load_cases()
    if args.limit:
        cases = cases[: args.limit]
    reviewed = [c for c in cases if c.reviewed]
    runner = Runner(systems, use_cache=not args.no_cache, rpm=args.rpm)
    matcher = (
        EmbeddingMatcher(runner, systems["gemini"]) if "gemini" in systems else LexicalMatcher()
    )

    report: dict = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": {
            "name": "demo journal v1 (hand-labeled, synthetic)",
            "decisions": len(cases),
            "reviewed": len(reviewed),
            "assumptions": sum(len(c.assumptions) for c in cases),
            "judged_assumptions": sum(len(c.assumptions) for c in reviewed),
            "themes": len({c.theme for c in reviewed}),
        },
    }
    started = time.perf_counter()
    for task in tasks:
        print(f"running {task} ...", file=sys.stderr)
        if task == "extraction":
            report["extraction"] = run_extraction(runner, cases, matcher)
        elif task == "verdicts":
            report["verdicts"] = run_verdicts(runner, reviewed)
        else:
            report["retrieval"] = run_retrieval(runner, reviewed)

    report["systems"] = [
        {
            "name": name,
            "label": a.label,
            "embed_model": a.embed_model,
            "model_versions": sorted(runner.tracer.versions) if a.provider == "gemini" else [],
        }
        for name, a in systems.items()
    ]
    report["run"] = {
        "seconds": round(time.perf_counter() - started, 1),
        "api_calls": runner.tracer.calls,
        "api_errors": runner.tracer.errors,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown = to_markdown(report)
    args.out.with_suffix(".md").write_text(markdown + "\n", encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
