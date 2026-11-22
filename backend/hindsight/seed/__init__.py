"""The demo journal: 36 decisions over about six months, with hand-labeled audits and reviews.

It gives anyone who opens the app a populated dashboard, and the same file is the gold set the
evals score against. Dates are stored as "days ago", so the demo never looks stale.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..ai import Auditor, Tracer
from ..db import utcnow
from ..models import Assumption, Decision, Outcome
from ..services.audit import reembed_stale
from ..services.review import is_grounded

JOURNAL_PATH = Path(__file__).with_name("demo_journal.json")
DEMO = "demo"
SEED_PROVIDER = "seed:hand-labeled"


@lru_cache
def load_journal() -> dict:
    return json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))


def demo_is_empty(db: Session) -> bool:
    count = db.scalar(select(func.count()).select_from(Decision).where(Decision.workspace == DEMO))
    return not count


def seed_demo(db: Session, auditor: Auditor, tracer: Tracer, now: datetime | None = None) -> int:
    now = now or utcnow()
    db.execute(delete(Decision).where(Decision.workspace == DEMO))  # FK cascades clear children
    db.commit()

    by_key: dict[str, tuple[Decision, dict]] = {}
    for item in load_journal()["decisions"]:
        created = now - timedelta(days=item["created_days_ago"])
        reviewed_at = created + timedelta(days=item["review_after_days"])
        outcome = item.get("outcome")

        decision = Decision(
            workspace=DEMO,
            title=item["title"],
            reasoning=item["reasoning"],
            alternatives=item.get("alternatives"),
            expected_outcome=item["expected_outcome"],
            confidence=item["confidence"],
            domain=item["domain"],
            review_at=reviewed_at.date(),
            created_at=created,
            audit_status="done",
            audit_provider=SEED_PROVIDER,
            premortem=item.get("premortem"),
            missing_considerations=item.get("missing_considerations", []),
            repeat_warnings=[],
            theme=item.get("theme"),
        )
        for position, a in enumerate(item["assumptions"]):
            evidence = (a.get("evidence") or None) if outcome else None
            decision.assumptions.append(
                Assumption(
                    position=position,
                    text=a["text"],
                    category=a["category"],
                    risk=a["risk"],
                    verdict=a.get("verdict") if outcome else None,
                    evidence=evidence,
                    evidence_grounded=(
                        is_grounded(evidence, outcome["what_happened"]) if evidence else None
                    ),
                )
            )
        if outcome:
            decision.outcome = Outcome(
                happened=outcome["happened"],
                what_happened=outcome["what_happened"],
                lesson=outcome.get("lesson"),
                review_status="done",
                created_at=reviewed_at,
            )
        db.add(decision)
        by_key[item["key"]] = (decision, item)

    db.flush()  # assign ids so repeat warnings can cite them
    for decision, item in by_key.values():
        decision.repeat_warnings = [
            {
                "assumption": w["assumption"],
                "past_decision_id": by_key[w["past_key"]][0].id,
                "note": w["note"],
            }
            for w in item.get("repeat_warnings", [])
            if w["past_key"] in by_key
        ]
    db.commit()

    reembed_stale(db, auditor, tracer, workspace=DEMO)
    return len(by_key)
