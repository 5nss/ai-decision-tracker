"""Prompt templates. Kept apart from the client so they can be read, diffed and evaluated alone."""

from .types import AssumptionToJudge, DecisionInput, PastCase

AUDIT_SYSTEM = (
    "You audit the reasoning behind someone's personal or professional decision. Your job is to "
    "surface the assumptions the decision quietly depends on, so the person can check them later "
    "against what actually happened. Be concrete and brief. Never moralize or give generic advice."
)

REVIEW_SYSTEM = (
    "You judge, after the fact, which assumptions behind a decision held up. Use only what the "
    "person wrote about the outcome and do not guess. If their notes don't settle an assumption, "
    "the verdict is unclear."
)


def _pct(p: float) -> str:
    return f"{round(p * 100)}%"


def _past_block(past: list[PastCase]) -> str:
    if not past:
        return "None yet."
    lines = []
    for case in past:
        status = "happened" if case.happened else "did NOT happen"
        failed = (
            "Failed assumptions: " + "; ".join(f'"{a}"' for a in case.failed_assumptions)
            if case.failed_assumptions
            else "No assumptions failed."
        )
        lines.append(
            f'- [id={case.decision_id}] "{case.title}" (expected outcome {status}). {failed}'
        )
    return "\n".join(lines)


def audit_prompt(d: DecisionInput, past: list[PastCase]) -> str:
    review_day = d.review_at or "review day"
    return f"""DECISION
Title: {d.title}
Domain: {d.domain}
They are {_pct(d.confidence)} confident that the expected outcome will happen.
Expected outcome: {d.expected_outcome}
Review date: {d.review_at or "not set"}

Reasoning, in their words:
\"\"\"
{d.reasoning}
\"\"\"

Alternatives they considered: {d.alternatives or "none written down"}

SIMILAR PAST DECISIONS BY THE SAME PERSON
{_past_block(past)}

TASK
1. assumptions: the 2 to 5 assumptions this decision depends on most, i.e. the ones that would
   break the expected outcome if false. Include unstated ones. Write each as one short
   first-person sentence ("I'll have free evenings", "The client will reply within a week").
   category: time = durations, schedules, free time; self = own skill, discipline, motivation,
   habits; people = what other people will do; money = costs, income, value for money;
   external = tools, markets, institutions, anything else outside their control; other = none.
   risk: high = likely wrong, or decisive if wrong; medium; low = safe.
2. missing_considerations: up to 3 short phrases for important things the reasoning ignores.
   Use an empty list if nothing important is missing.
3. premortem: one sentence that starts "It's {review_day} and this failed because".
4. repeat_warnings: only when one of your assumptions repeats a FAILED assumption from the past
   decisions above. Cite that decision's id. Otherwise return an empty list. Never cite an id
   that is not listed above."""


def review_prompt(
    d: DecisionInput, assumptions: list[AssumptionToJudge], happened: bool, what_happened: str
) -> str:
    listed = "\n".join(f"- [id={a.id}] ({a.category}) {a.text}" for a in assumptions)
    return f"""DECISION
Title: {d.title}
Expected outcome: {d.expected_outcome}
They were {_pct(d.confidence)} confident. Did the expected outcome happen? {"Yes" if happened else "No"}.

WHAT HAPPENED, in their words:
\"\"\"
{what_happened}
\"\"\"

ASSUMPTIONS TO JUDGE
{listed}

TASK
For every assumption id above, return a verdict:
- held: the notes show it turned out true
- failed: the notes show it turned out false
- unclear: the notes don't say enough either way
evidence: the exact words from the notes that support the verdict, copied verbatim
(an empty string when unclear).
Then lesson: one specific sentence they can apply to their next similar decision."""
