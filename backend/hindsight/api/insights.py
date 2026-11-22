"""Dashboard numbers, always computed from the rows themselves (nothing cached to go stale)."""

from datetime import date

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..deps import DbDep, WorkspaceDep
from ..models import Decision
from ..schemas import Counts, Insights
from ..services.calibration import Forecast, calibration_report
from ..services.patterns import JudgedAssumption, failure_patterns
from .decisions import decision_status

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=Insights)
def get_insights(db: DbDep, workspace: WorkspaceDep) -> Insights:
    decisions = db.scalars(
        select(Decision)
        .where(Decision.workspace == workspace)
        .options(selectinload(Decision.assumptions), selectinload(Decision.outcome))
    ).all()

    today = date.today()
    statuses = [decision_status(d, today) for d in decisions]
    counts = Counts(
        total=len(decisions),
        open=statuses.count("open"),
        due=statuses.count("due"),
        reviewed=statuses.count("reviewed"),
    )

    reviewed = [d for d in decisions if d.outcome is not None]
    forecasts = [
        Forecast(p=d.confidence, hit=d.outcome.happened, created_at=d.created_at, domain=d.domain)
        for d in reviewed
    ]
    judged = [
        JudgedAssumption(
            category=a.category,
            verdict=a.verdict,
            decision_id=d.id,
            decision_title=d.title,
            text=a.text,
            created_at=d.created_at,
        )
        for d in reviewed
        for a in d.assumptions
        if a.verdict
    ]
    return Insights(
        counts=counts,
        calibration=calibration_report(forecasts),
        patterns=failure_patterns(judged),
    )
