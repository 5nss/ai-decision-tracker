"""Gold cases, read from the same hand-labeled journal that seeds the demo workspace."""

from __future__ import annotations

from dataclasses import dataclass

from hindsight.ai.types import AssumptionToJudge, Category, DecisionInput
from hindsight.seed import load_journal


@dataclass(frozen=True)
class GoldAssumption:
    id: int
    text: str
    category: str
    verdict: str | None
    evidence: str | None


@dataclass(frozen=True)
class Case:
    key: str
    theme: str | None
    domain: str
    created_days_ago: int
    decision: DecisionInput
    assumptions: tuple[GoldAssumption, ...]
    happened: bool | None
    what_happened: str | None

    @property
    def reviewed(self) -> bool:
        return self.happened is not None

    def to_judge(self) -> list[AssumptionToJudge]:
        return [
            AssumptionToJudge(id=a.id, text=a.text, category=Category(a.category))
            for a in self.assumptions
        ]


def load_cases() -> list[Case]:
    cases = []
    for item in load_journal()["decisions"]:
        outcome = item.get("outcome")
        cases.append(
            Case(
                key=item["key"],
                theme=item.get("theme"),
                domain=item["domain"],
                created_days_ago=item["created_days_ago"],
                decision=DecisionInput(
                    title=item["title"],
                    reasoning=item["reasoning"],
                    alternatives=item.get("alternatives"),
                    expected_outcome=item["expected_outcome"],
                    confidence=item["confidence"],
                    domain=item["domain"],
                ),
                assumptions=tuple(
                    GoldAssumption(
                        id=i + 1,
                        text=a["text"],
                        category=a["category"],
                        verdict=a.get("verdict"),
                        evidence=a.get("evidence"),
                    )
                    for i, a in enumerate(item["assumptions"])
                ),
                happened=outcome["happened"] if outcome else None,
                what_happened=outcome["what_happened"] if outcome else None,
            )
        )
    return cases
