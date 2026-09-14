"""
Report generator for Phase 5A and Phase 5B Retrieval Evaluation Benchmark.
Produces clean JSON and Markdown reports for individual runs and multi-configuration comparisons.
"""

import json
from pathlib import Path
from typing import Optional, Dict

from app.evals.schemas import EvalRunReport, MultiConfigBenchmarkReport


def generate_json_report(
    report: EvalRunReport,
    output_path: Optional[Path] = None,
) -> str:
    """
    Serialize evaluation run report to structured JSON string.
    Optionally writes to disk if output_path is provided.
    """
    json_str = report.model_dump_json(indent=2)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
    return json_str


def generate_markdown_report(
    report: EvalRunReport,
    output_path: Optional[Path] = None,
) -> str:
    """
    Generate clean, human-readable Markdown benchmark report for a single configuration.
    Includes summary metrics table, per-subject breakdown, failure analysis,
    and individual case results.
    """
    agg = report.aggregate_metrics
    config_name = report.configuration_name or "default"

    lines = [
        f"# RAG Retrieval Benchmark Report ({config_name})",
        f"",
        f"- **Configuration**: {config_name}",
        f"- **Dataset**: {report.dataset_name} (v{report.dataset_version})",
        f"- **Corpus Version**: {report.corpus_version}",
        f"- **Total Evaluation Cases**: {agg.total_cases}",
        f"- **Cases with Zero Relevant Chunks (MRR=0)**: {agg.zero_mrr_count}",
        f"",
        f"## Summary Metrics",
        f"",
        f"| Metric | Score | Note |",
        f"| :--- | :---: | :--- |",
        f"| **Recall@3** | **{agg.mean_recall_at_3:.4f}** | Golden chunks retrieved in top 3 |",
        f"| **Recall@5** | **{agg.mean_recall_at_5:.4f}** | Golden chunks retrieved in top 5 |",
        f"| **MRR** | **{agg.mean_mrr:.4f}** | Mean Reciprocal Rank (first match) |",
        f"| **Context Relevance** | **{agg.mean_context_relevance:.4f}** | Lexical/Metadata proxy match |",
        f"",
        f"> [!NOTE]",
        f"> Context Relevance is a deterministic keyword/metadata proxy, NOT an LLM judge and NOT semantic scoring.",
        f"",
    ]

    # Subject-level grouping
    subject_cases: Dict[str, list] = {}
    for cs in report.case_scores:
        subject_cases.setdefault(cs.subject, []).append(cs)

    lines.extend([
        f"## Subject Breakdown",
        f"",
        f"| Subject | Cases | Mean Recall@3 | Mean Recall@5 | Mean MRR | Mean Context Relevance |",
        f"| :--- | :---: | :---: | :---: | :---: | :---: |",
    ])

    for subj, cases in sorted(subject_cases.items()):
        n = len(cases)
        m_r3 = sum(c.recall_at_3 for c in cases) / n
        m_r5 = sum(c.recall_at_5 for c in cases) / n
        m_mrr = sum(c.mrr for c in cases) / n
        m_cr = sum(c.context_relevance for c in cases) / n
        lines.append(
            f"| {subj} | {n} | {m_r3:.4f} | {m_r5:.4f} | {m_mrr:.4f} | {m_cr:.4f} |"
        )

    lines.append("")

    # Failures / Missed Chunks section
    if report.failures:
        lines.extend([
            f"## Missed Cases / Retrieval Failures ({len(report.failures)})",
            f"",
            f"| Case ID | Subject | Unit | Query | Missed Golden Chunks | Retrieved Chunks |",
            f"| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for fail in report.failures:
            missed_str = ", ".join(fail.missed_golden_chunk_ids) if fail.missed_golden_chunk_ids else "None"
            retrieved_str = ", ".join(fail.retrieved_chunk_ids[:3]) if fail.retrieved_chunk_ids else "None"
            q_short = (fail.query[:50] + "...") if len(fail.query) > 50 else fail.query
            lines.append(
                f"| `{fail.case_id}` | {fail.subject} | {fail.unit} | {q_short} | `{missed_str}` | `{retrieved_str}` |"
            )
        lines.append("")
    else:
        lines.extend([
            f"## Missed Cases / Retrieval Failures",
            f"",
            f"No retrieval failures recorded. All evaluation cases retrieved at least one relevant golden chunk in top-5.",
            f"",
        ])

    # Per-case details table
    lines.extend([
        f"## Detailed Case Results",
        f"",
        f"| Case ID | Subj / Unit | Recall@3 | Recall@5 | MRR | Relevance | Retrieved Chunks |",
        f"| :--- | :--- | :---: | :---: | :---: | :---: | :--- |",
    ])

    for cs in report.case_scores:
        r_str = ", ".join(cs.retrieved_chunk_ids[:3]) if cs.retrieved_chunk_ids else "None"
        if len(cs.retrieved_chunk_ids) > 3:
            r_str += f" (+{len(cs.retrieved_chunk_ids) - 3} more)"
        lines.append(
            f"| `{cs.case_id}` | {cs.subject} {cs.unit} | {cs.recall_at_3:.2f} | {cs.recall_at_5:.2f} | {cs.mrr:.4f} | {cs.context_relevance:.2f} | `{r_str}` |"
        )

    markdown_str = "\n".join(lines) + "\n"

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_str)

    return markdown_str


def generate_multi_config_markdown_report(
    benchmark: MultiConfigBenchmarkReport,
    output_path: Optional[Path] = None,
) -> str:
    """
    Generate comparison Markdown benchmark report comparing multiple retrieval configurations:
    A. Dense retrieval
    B. Lexical retrieval
    C. Hybrid/RRF
    D. Hybrid + existing reranker
    """
    lines = [
        f"# RAG Retrieval Architecture Benchmark Comparison",
        f"",
        f"- **Dataset**: {benchmark.dataset_name} (v{benchmark.dataset_version})",
        f"- **Corpus Version**: {benchmark.corpus_version}",
        f"- **Total Cases**: {benchmark.total_cases}",
        f"",
        f"## Configuration Comparison",
        f"",
        f"| Configuration | Recall@3 | Recall@5 | MRR | Context Relevance | Zero MRR Cases |",
        f"| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    for config_key, rep in benchmark.configuration_reports.items():
        agg = rep.aggregate_metrics
        lines.append(
            f"| **{config_key}** | **{agg.mean_recall_at_3:.4f}** | **{agg.mean_recall_at_5:.4f}** | "
            f"**{agg.mean_mrr:.4f}** | **{agg.mean_context_relevance:.4f}** | {agg.zero_mrr_count} |"
        )

    lines.extend([
        f"",
        f"> [!NOTE]",
        f"> - **Evaluation Scope**: Production retrieval algorithms evaluated on a frozen benchmark corpus.",
        f"> - **Recall@k**: Fraction of golden relevant chunks present in the top-k retrieved candidates.",
        f"> - **MRR (Mean Reciprocal Rank)**: 1 / rank of the first golden chunk retrieved (or 0.0 if not found).",
        f"> - **Context Relevance**: Deterministic keyword and metadata proxy metric, NOT an LLM judge.",
        f"",
    ])

    # Per-subject breakdown comparison
    # Collect all subjects
    first_report = next(iter(benchmark.configuration_reports.values()))
    subjects = sorted(list({cs.subject for cs in first_report.case_scores}))

    lines.extend([
        f"## Per-Subject Breakdown Across Configurations",
        f"",
        f"| Subject | Configuration | Mean Recall@3 | Mean Recall@5 | Mean MRR | Mean Context Relevance |",
        f"| :--- | :--- | :---: | :---: | :---: | :---: |",
    ])

    for subj in subjects:
        for config_key, rep in benchmark.configuration_reports.items():
            s_cases = [cs for cs in rep.case_scores if cs.subject == subj]
            n = len(s_cases)
            if n > 0:
                m_r3 = sum(c.recall_at_3 for c in s_cases) / n
                m_r5 = sum(c.recall_at_5 for c in s_cases) / n
                m_mrr = sum(c.mrr for c in s_cases) / n
                m_cr = sum(c.context_relevance for c in s_cases) / n
                lines.append(
                    f"| {subj} | {config_key} | {m_r3:.4f} | {m_r5:.4f} | {m_mrr:.4f} | {m_cr:.4f} |"
                )

    lines.append("")

    # Retrieval Failures & Rankings for Failed Cases across configurations
    lines.extend([
        f"## Per-Configuration Retrieval Failures & Rankings",
        f"",
    ])

    for config_key, rep in benchmark.configuration_reports.items():
        lines.append(f"### {config_key} (Failures: {len(rep.failures)})")
        if not rep.failures:
            lines.append("No failures recorded for this configuration.\n")
            continue

        lines.extend([
            f"| Case ID | Subject | Query | Missed Golden Chunks | Retrieved Top-3 Chunks |",
            f"| :--- | :--- | :--- | :--- | :--- |",
        ])
        for fail in rep.failures:
            missed_str = ", ".join(fail.missed_golden_chunk_ids) if fail.missed_golden_chunk_ids else "None"
            retrieved_str = ", ".join(fail.retrieved_chunk_ids[:3]) if fail.retrieved_chunk_ids else "None"
            q_short = (fail.query[:50] + "...") if len(fail.query) > 50 else fail.query
            lines.append(
                f"| `{fail.case_id}` | {fail.subject} | {q_short} | `{missed_str}` | `{retrieved_str}` |"
            )
        lines.append("")

    markdown_str = "\n".join(lines) + "\n"

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_str)

    return markdown_str


def generate_multi_config_json_report(
    benchmark: MultiConfigBenchmarkReport,
    output_path: Optional[Path] = None,
) -> str:
    """Serialize MultiConfigBenchmarkReport to formatted JSON."""
    json_str = benchmark.model_dump_json(indent=2)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
    return json_str
