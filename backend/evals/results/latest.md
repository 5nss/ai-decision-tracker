_Generated 2026-11-22T12:29:14+00:00 on demo journal v1 (hand-labeled, synthetic)._

**Assumption extraction** (36 decisions; match = lexical overlap coefficient ≥ 0.5)

| System | Precision | Recall | F1 | Category accuracy |
|---|---|---|---|---|
| heuristic:rules-v1 | 96.3% | 32.9% | 49.1% | 42.3% |

**Assumption verdicts** (64 assumptions: held / failed / unclear)

| System | Accuracy | Macro-F1 | Evidence grounded |
|---|---|---|---|
| baseline: every assumption takes the outcome's polarity | 79.7% | 55.7% | n/a |
| heuristic:rules-v1 | 34.4% | 30.3% | 100.0% |

**Similar-decision retrieval** (30 queries; relevant = same theme)

| Method | Recall@3 | MRR |
|---|---|---|
| v1 rule: same domain, most recent | 43.3% | 0.549 |
| TF-IDF (lexical) | 73.3% | 0.746 |
| hash-512 embeddings | 48.3% | 0.692 |

