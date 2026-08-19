# 🧠 AI Decision Justification Tracker — Master Specification

---

# 1. Problem Definition

## Core Problem
People do not learn effectively from past decisions because they:
- Forget their original reasoning
- Do not compare expectations with actual outcomes
- Repeat flawed assumptions over time

## Refined Problem Statement
Users lack a system to **capture, revisit, and analyze their past reasoning**, leading to repeated mistakes and poor mental model evolution.

---

# 2. Objective

> Build a system that helps users **understand their mistakes** by comparing expected vs actual outcomes and extracting behavioral patterns over time.

### Success Criteria
- User logs ≥ 5 decisions
- User revisits ≥ 3 outcomes
- System identifies ≥ 2 recurring behavioral patterns
- User changes at least 1 behavior

---

# 3. Target Users

## Primary
- Students
- Early professionals
- Builders / learners

## User Traits
- Interested in self-improvement
- Willing to reflect (with low friction)

---

# 4. Core System Flow

```text
Decision Entry → Outcome Entry → AI Analysis → Pattern Extraction → Behavior Memory Update
```

---

# 5. Input & Output

## Input

### Decision Phase
- decision_text (short)
- reasoning (structured)
- expected_outcome
- constraints (optional)
- timestamp

### Outcome Phase
- actual_outcome
- context (what happened)
- timestamp

---

## Output

### Per Decision
- expectation vs reality comparison
- invalid assumptions
- reasoning gap
- lesson learned

### Over Time
- repeated patterns
- behavioral traits
- improvement suggestions

---

# 6. Memory Architecture

## Principle
AI does not remember — system must manage memory.

---

## Memory Layers

### 1. Active Memory (Short-Term)
- Full decision + outcome data
- Used for RAG
- Retention: limited (e.g., 30–60 days)

---

### 2. Feature Layer (Intermediate)
Extracted per decision:
- assumptions
- constraints ignored
- domain (habit, study, etc.)
- outcome quality

---

### 3. Behavior Layer (Long-Term)
Aggregated patterns:

```json
{
  "behavior": "overestimates_time",
  "frequency": 4,
  "confidence": 0.72,
  "last_seen": "timestamp"
}
```

---

## Memory Lifecycle

```text
Raw Data → Feature Extraction → Behavior Aggregation → Partial Retention → Raw Expiry
```

---

## Expiry Strategy

After expiry:
- Remove full raw text
- Keep:
  - short summary
  - extracted features
  - behavior contributions

---

### Example After Compression

```json
{
  "summary": "missed study goal due to distractions",
  "behaviors": ["overcommitment", "low_focus"],
  "weight": 0.6
}
```

---

# 7. AI System Design

## Core Functions

1. Structure extraction (from input)
2. Expectation vs reality comparison
3. Assumption detection
4. Multi-signal behavior extraction
5. Pattern aggregation (across decisions)
6. Lesson generation

---

## Prompt Input

- current decision
- reasoning
- expected outcome
- actual outcome
- retrieved past similar decisions (RAG)
- behavior memory snapshot

---

## Output Constraints

- Must be probabilistic (not absolute)
- Must reference evidence (“based on X past cases”)
- Must avoid vague statements

---

# 8. Retrieval System (RAG)

## Strategy
- Store embeddings per decision
- Retrieve top-k similar entries (k = 3–5)

---

## Retrieval Inputs
- reasoning similarity
- outcome similarity
- domain filtering

---

## Hybrid Retrieval
- vector similarity
- + metadata filters (time, category)

---

# 9. Data Storage Design

## Tables / Collections

### Decisions
- id
- user_id
- decision_text
- reasoning
- expected_outcome
- timestamp

---

### Outcomes
- decision_id
- actual_outcome
- context
- timestamp

---

### Features
- decision_id
- assumptions
- constraints
- domain
- signals

---

### Behavior Profile
- user_id
- behavior
- frequency
- confidence
- last_seen

---

# 10. Constraints

## Latency
- AI response < 5 seconds

## Cost
- limit retrieved items
- cache analysis
- compress old data

## Accuracy
- no ground truth
- outputs must be suggestive

## Data
- sparse initially (cold start)

## Privacy
- user isolation required
- encryption at scale

---

# 11. Cold Start vs Mature System

## Cold Start (0–3 decisions)
- no pattern detection
- generic + single decision analysis

## Growth Phase (5–10 decisions)
- early pattern hints

## Mature Phase (10+)
- strong behavioral insights

---

# 12. Solution Approaches

## RAG (Primary)
- dynamic retrieval
- scalable
- flexible

---

## ML Model (Future)
- deeper personalization
- requires large data

---

## Rule-Based (Support)
- validation checks
- fallback logic

---

## Hybrid (Recommended)
- RAG + rules + LLM

---

# 13. Key Design Decisions

- Strict structured input
- No editing past entries (consider annotation later)
- Store compressed + partial raw data
- Time-based memory decay
- Multi-signal behavior extraction (not single label)
- Behavior > raw history
- AI explains reasoning
- Goal: understanding mistakes (not prediction)

---

# 14. Risks

## User Behavior
- low engagement
- incomplete logging

## AI Risks
- wrong inference
- hallucinated patterns

## System Risks
- over-compression
- loss of nuance

---

# 15. Validation Experiments

1. RAG vs no RAG
2. Structured vs unstructured input
3. Retrieval size (k=2,5,10)
4. Compression impact
5. Behavior extraction accuracy

---

# 16. Open Questions (Require Human Decisions)

- behavior taxonomy design
- expiry timing strategy
- confidence calculation method
- user feedback loop (AI correction)
- pattern threshold (when to show)
- engagement mechanism (reminders)
- core metric definition

---

# 17. Final System Identity

> A system that reconstructs past thinking, compares it with reality, and distills long-term behavioral patterns to improve decision-making.

---

# 🔥 Core Insight

This is not a journaling tool.  
This is a **thinking audit system**.