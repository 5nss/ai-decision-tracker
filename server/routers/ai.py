# server/routers/ai.py
"""FastAPI router for AI analysis endpoints.

Now powered by Google Gemini (gemini-1.5-flash).
Falls back gracefully to rule-based analysis if the API key is missing
or the call fails — the app never returns a 500 for AI errors.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import asyncio
import datetime
import functools

from .. import models, database
from ..ai_service import analyse_user_habits_with_gemini

router = APIRouter()


# ── Shared helpers (same as before — used for rule-based fallback + context) ───

_BEHAVIOR_LABELS: dict[str, str] = {
    "ignores_constraints":       "Tends to ignore or skip constraint specification",
    "poor_outcome_track_record": "Has a pattern of outcomes falling short of expectations",
    "good_outcome_track_record": "Consistently achieves outcomes close to expectations",
    "over_assumes":              "Makes multiple unverified assumptions before deciding",
    "makes_assumptions":         "Makes assumptions that influence their reasoning",
    "active_in_study":           "Frequently makes decisions in the study/learning domain",
    "active_in_work":            "Frequently makes decisions in the work/career domain",
    "active_in_habit":           "Frequently makes decisions in the habit/routine domain",
    "active_in_finance":         "Frequently makes decisions in the finance/money domain",
    "active_in_social":          "Frequently makes decisions in the social/relationship domain",
    "active_in_other":           "Makes decisions across various domains",
}


def _humanize_behavior(tag: str) -> str:
    return _BEHAVIOR_LABELS.get(tag, tag.replace("_", " ").capitalize())


def _gap_analysis(expected: str, actual: Optional[str]) -> dict:
    if not actual:
        return {
            "status": "pending",
            "message": "Outcome not yet recorded — analysis limited to decision structure only.",
            "gap_score": None,
        }
    exp_words = set(expected.lower().split())
    act_words = set(actual.lower().split())
    overlap = len(exp_words & act_words) / max(len(exp_words), 1)
    neg_signals = ["fail", "didn't", "could not", "worse", "bad", "wrong",
                   "mistake", "not", "never", "miss", "disappoint"]
    neg_hit = any(s in actual.lower() for s in neg_signals)
    if neg_hit and overlap < 0.25:
        return {"status": "poor", "message": "Actual outcome significantly diverged from expectations.", "overlap_score": round(overlap, 2)}
    elif overlap >= 0.45 and not neg_hit:
        return {"status": "good", "message": "Actual outcome closely matched expectations.", "overlap_score": round(overlap, 2)}
    else:
        return {"status": "mixed", "message": "Partial alignment between expected and actual outcome.", "overlap_score": round(overlap, 2)}


def _find_similar(target: models.Decision, db: Session, top_k: int = 3) -> list[dict]:
    target_feature = db.query(models.Feature).filter(models.Feature.decision_id == target.id).first()
    target_domain = target_feature.domain if target_feature else None
    query = db.query(models.Decision).filter(models.Decision.id != target.id)
    if target_domain:
        matching_features = db.query(models.Feature).filter(
            models.Feature.domain == target_domain,
            models.Feature.decision_id != target.id,
        ).limit(top_k).all()
        matching_ids = [f.decision_id for f in matching_features]
        if matching_ids:
            query = query.filter(models.Decision.id.in_(matching_ids))
        else:
            query = query.order_by(models.Decision.timestamp.desc())
    else:
        query = query.order_by(models.Decision.timestamp.desc())
    similar = query.limit(top_k).all()
    results = []
    for d in similar:
        outcome = db.query(models.Outcome).filter(models.Outcome.decision_id == d.id).first()
        feature = db.query(models.Feature).filter(models.Feature.decision_id == d.id).first()
        results.append({
            "id": d.id,
            "decision_text": d.decision_text,
            "outcome_quality": feature.outcome_quality if feature else "unknown",
            "actual_outcome_snippet": (outcome.actual_outcome[:120] + "…") if outcome else None,
        })
    return results


def _rule_based_recommendations(
    decision: models.Decision,
    feature: Optional[models.Feature],
    behaviors: list[models.Behavior],
    gap: dict,
) -> list[str]:
    recs: list[str] = []
    if feature and feature.constraints_ignored:
        recs.append("📌 You skipped constraints for this decision. Listing constraints explicitly tends to improve outcome quality.")
    if feature and feature.assumptions:
        count = len(feature.assumptions.split(";"))
        if count >= 3:
            recs.append(f"⚠️ {count} assumptions detected. Consider validating the most critical ones before acting.")
    if gap.get("status") == "poor":
        recs.append("🔄 This outcome underperformed. Reflect on which assumptions proved false.")
    for beh in [b for b in behaviors if b.confidence >= 0.5]:
        if beh.behavior == "ignores_constraints":
            recs.append("🔁 Pattern: you consistently skip constraints. Dedicate 2 minutes to listing them before deciding.")
        if beh.behavior == "over_assumes" :
            recs.append("🔁 Pattern: you tend to over-assume. Try assumption mapping — list each assumption and its risk level.")
        if beh.behavior == "poor_outcome_track_record" and beh.frequency >= 3:
            recs.append(f"📊 {beh.frequency} past decisions underperformed. Consider a pre-mortem before major decisions.")
    if not recs:
        recs.append("✅ No major risk patterns detected. Keep logging to build a richer profile.")
    return recs


@router.post("/analyze_user", status_code=status.HTTP_200_OK)
async def analyze_user_habits(user_id: int = 1, db: Session = Depends(database.get_db)):
    """
    AI-powered macro analysis of a user's decision-making habits.
    """
    # 1. Load decisions
    decisions = db.query(models.Decision).filter(models.Decision.user_id == user_id).order_by(models.Decision.timestamp.desc()).limit(15).all()
    if len(decisions) < 3:
        raise HTTPException(status_code=400, detail="Need at least 3 decisions to analyze habits.")

    # 2. Build decision history context
    decision_history = []
    for d in decisions:
        outcome = db.query(models.Outcome).filter(models.Outcome.decision_id == d.id).first()
        feature = db.query(models.Feature).filter(models.Feature.decision_id == d.id).first()
        decision_history.append({
            "id": d.id,
            "decision_text": d.decision_text,
            "reasoning": d.reasoning,
            "expected_outcome": d.expected_outcome,
            "actual_outcome": outcome.actual_outcome if outcome else None,
            "domain": feature.domain if feature else "unknown",
        })

    # 3. Behavior memory
    behaviors = (
        db.query(models.Behavior)
        .filter(models.Behavior.user_id == user_id)
        .order_by(models.Behavior.confidence.desc())
        .all()
    )

    behavior_snapshot = [
        {
            "behavior": b.behavior,
            "label": _humanize_behavior(b.behavior),
            "frequency": b.frequency,
            "confidence": b.confidence,
            "last_seen": b.last_seen.isoformat() if b.last_seen else None,
        }
        for b in behaviors[:10]
    ]

    # 4. ── Call Gemini ──────────────────────────────────────────────────────────
    loop = asyncio.get_event_loop()
    ai_result = await loop.run_in_executor(
        None,
        functools.partial(
            _call_gemini_sync_user,
            decision_history=decision_history,
            behavior_snapshot=behavior_snapshot,
        )
    )

    # 5. Return result
    ai_source = "gemini" if not ai_result.get("fallback") else "rule_based"

    return {
        "user_id": user_id,
        "analyzed_at": datetime.datetime.utcnow().isoformat(),
        "analysis_source": ai_source,
        "ai_insight": None if ai_result.get("fallback") else {
            "overall_reasoning_score": ai_result.get("overall_reasoning_score"),
            "habitual_patterns":       ai_result.get("habitual_patterns", []),
            "common_blind_spots":      ai_result.get("common_blind_spots", []),
            "strengths":               ai_result.get("strengths", []),
            "macro_recommendations":   ai_result.get("macro_recommendations", []),
            "summary":                 ai_result.get("summary"),
            "model":                   ai_result.get("_model", _MODEL_NAME_FALLBACK),
        },
        "behavior_memory": behavior_snapshot,
        "ai_error": ai_result.get("error") if ai_result.get("fallback") else None,
    }


# ── Sync wrapper (runs inside executor) ────────────────────────────────────────
_MODEL_NAME_FALLBACK = "gemini-1.5-flash"

def _call_gemini_sync_user(
    decision_history: list[dict],
    behavior_snapshot: list[dict],
) -> dict:
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            analyse_user_habits_with_gemini(
                decision_history=decision_history,
                behavior_snapshot=behavior_snapshot,
            )
        )
    finally:
        loop.close()


# ── Legacy endpoint stub ───────────────────────────────────────────────────────
@router.get("/result/{job_id}")
def get_analysis_result(job_id: str):
    return {"job_id": job_id, "status": "deprecated", "message": "Use POST /api/ai/analyze instead."}
