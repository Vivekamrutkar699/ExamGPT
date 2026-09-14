# ExamGPT Phase 6C: Controlled Generation Reliability Improvement Report

- **Evaluation Scope**: Comparison of controlled generation reliability strategies on the frozen 35-case benchmark corpus
- **Dataset**: SPPU Engineering Core Evaluation Dataset (35 frozen cases)
- **Corpus Version**: 1.0.0
- **Model**: `llama3.2:3b` (Ollama local inference)
- **Parameters**: Temperature `0.2` | Max Tokens `800`
- **Timestamp**: `2026-09-14T15:14:43.051917+00:00`

---

## 1. Baseline Performance (Phase 6B Historical Baseline)

The baseline generation metrics measured in Phase 6B on the frozen 35-case SPPU Engineering corpus:

| Metric | Baseline Score | Evaluation Notes |
| :--- | :---: | :--- |
| **Generation Success Rate** | **100.0%** | 35/35 cases generated valid responses without runtime failure |
| **Mean Concept Coverage** | **0.9429** | Robust domain topic coverage across all 4 engineering subjects |
| **Mean Grounded Concept Coverage** | **0.9314** | Strong overlap with retrieved corpus study material |
| **Mean Citation Validity** | **0.0857** (8.6%) | Primary weakness: model rarely generated explicit source citations |
| **Mean Citation Source Match** | **0.0857** (8.6%) | Valid citations correctly referenced source pages |
| **Confidence Compliance Rate** | **14.3%** (14.3%) | Primary weakness: model frequently styled confidence with markdown bolding |

---

## 2. Failure Diagnosis of Baseline Outputs

Categorization of all 35 answers from `generation_benchmark_report.json` across failure categories A through G:

| Category | Failure Description | Count | Percentage | Detailed Diagnosis |
| :---: | :--- | :---: | :---: | :--- |
| **A** | **Citation completely missing** | **31** | **88.6%** | Model answered thoroughly but omitted inline citation tokens in body text. |
| **B** | **Citation present but malformed** | **1** | **2.9%** | Case `eval_spos_008` had `[Source [1]]` due to bracket nesting. |
| **C** | **Citation has invalid source index** | **0** | **0.0%** | Zero hallucinations of invalid source indices (> k or < 1). |
| **D** | **Citation has incorrect page** | **0** | **0.0%** | Zero hallucinated page numbers; cited pages matched chunk metadata. |
| **E** | **Confidence completely missing** | **4** | **11.4%** | 4 cases omitted the `Confidence:` statement entirely. |
| **F** | **Confidence formatting differs** | **26** | **74.3%** | 26 cases used markdown bolding (e.g., `**Confidence:** High`, `**Confidence: High**`). |
| **G** | **Answer quality failure (<50% concepts)** | **0** | **0.0%** | Zero semantic quality failures; concept coverage is high across the board. |

---

## 3. Evaluated Candidates & Configurations

1. **Baseline (Phase 6B)**: Production prompt without post-processing or JSON constraints.
2. **Experiment C (Deterministic Normalizer on Baseline)**: Deterministic regex normalization applied to baseline outputs. Strips markdown bolding from confidence lines and standardizes bracket/colon citation syntax. Strict non-fabrication guarantee: never invents citations.
3. **Experiment A (Enhanced Prompt Contract)**: Concise explicit inline citation contract (`[Source X, Page Y]`) and unbolded confidence requirement in system prompt.
4. **Experiment A + C (Enhanced Prompt Contract + Deterministic Normalizer)**: Synergy of explicit prompt output contract with deterministic cleanup of markdown styling and bracket syntax.
5. **Experiment B (Structured JSON Mode)**: OpenAI-compatible `response_format={'type': 'json_object'}` requesting `{"answer": "...", "confidence": "..."}`.

---

## 4. Complete Comparison Table

| Configuration | Success | Concept | Grounded | Citation Validity | Citation Match | Confidence | Δ Cit. Validity | Δ Confidence | Cases Improved | Cases Regressed | Cases Unchanged |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline (Phase 6B)** | 100.0% | 0.9429 | 0.9314 | **0.0857** | **0.0857** | **14.3%** | 0.0% | 0.0% | 0 | 0 | 35 |
| **Experiment C (Normalizer on Baseline)** | 100.0% | 0.9429 | 0.9314 | **0.0857** | **0.0857** | **88.6%** | +0.0% | +74.3% | 26 | 0 | 9 |
| **Experiment A (Enhanced Prompt Contract)** | 100.0% | 0.9429 | 0.9314 | **0.0857** | **0.0857** | **11.4%** | +0.0% | -2.9% | 6 | 9 | 20 |
| **Experiment A + C (Prompt Contract + Normalizer)** | 100.0% | 0.9429 | 0.9314 | **0.2000** | **0.2000** | **88.6%** | +11.4% | +74.3% | 27 | 2 | 6 |
| **Experiment B (Structured JSON Mode)** | 100.0% | 0.9429 | 0.9371 | **0.8000** | **0.7857** | **100.0%** | +71.4% | +85.7% | 34 | 0 | 1 |

---

## 5. Acceptance Criteria Evaluation

According to the defined acceptance criteria:
1. **Generation Success Rate = 100%**: Satisfied by all configurations (35/35 cases).
2. **Citation Validity Improves Meaningfully**: Satisfied by Experiment A+C (+11.4 pp) and Experiment B (+71.4 pp).
3. **Citation Source Match Does Not Regress**: Satisfied (0 regressions across valid citations; 100% of parsed citations in Exp A+C matched source pages).
4. **Concept Coverage Does Not Materially Regress**: Satisfied (Concept coverage remained 0.9429 across all configurations).
5. **Grounded Concept Coverage Does Not Materially Regress**: Satisfied (0.9314 in A+C, 0.9371 in B).

---

## 6. Selected Strategy & Architectural Recommendation

### Primary Production Recommendation: **Experiment A + C (Prompt Contract + Deterministic Normalizer)**
- **Rationale**: Experiment A + C provides the ideal balance for production RAG: it preserves natural streaming Markdown generation, requires zero JSON serialization overhead, and increases citation validity to **0.2000** and confidence compliance to **88.6%** with zero regressions on concept coverage.
- **Safety & Non-Fabrication**: The deterministic normalizer strictly normalizes formatting syntax (`**Confidence:** High` → `Confidence: High`, `[Source [1], Page 4]` → `[Source 1, Page 4]`) and NEVER fabricates citations or alters technical facts.

### High-Reliability Alternative: **Experiment B (Structured JSON Mode)**
- **Performance**: Achieved **80.0%** Citation Validity, **78.6%** Citation Match, and **100.0%** Confidence Compliance across all 35 cases with **0 regressions**.
- **Applicability**: Recommended for non-streaming batch evaluations, automated quiz grading, and structured API responses where structured JSON schemas are required.

---

## 7. Key Limitations & Future Work

1. **Small Model Instruction Following**: The 3B parameter local model (`llama3.2:3b`) occasionally treats inline citations as paragraph-level summaries rather than sentence-level citations in freeform Markdown.
2. **Format Normalization Boundary**: Format normalization cannot inject citations for claims the model left uncited. Citation frequency is fundamentally bounded by the model's generation behavior.
3. **JSON Streaming Latency**: While Experiment B achieves 80% citation compliance, JSON mode requires completing the JSON block before parsing, precluding token-by-token Markdown streaming in chat UI.

