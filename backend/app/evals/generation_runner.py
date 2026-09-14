"""
Generation evaluation runner and report generator for ExamGPT Phase 6B:
Real Ollama Generation Evaluation on the frozen 35-case benchmark corpus.

Reuses:
- Existing production RAG query rewriting (QueryProcessor.rewrite_query)
- Existing production hybrid retrieval + reranker via EvalRetrievalAdapter
- Existing production context formatting (RAGEngine._format_context structure)
- Existing Ollama AsyncOpenAI-compatible client with exact production settings (temperature=0.2, max_tokens=800)
- Phase 6A deterministic generation metrics (compute_generation_metrics)

Produces JSON and Markdown benchmark reports without altering production code.
"""

import argparse
import asyncio
import datetime
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any, Sequence, Callable

from openai import AsyncOpenAI

from app.core.config import settings
from app.evals.schemas import EvalDataset, EvalCase, FrozenCorpus
from app.evals.validator import load_eval_dataset, load_frozen_corpus
from app.evals.adapter import EvalRetrievalAdapter
from app.evals.generation_schemas import (
    PreservedRetrievedChunk,
    GenerationMetrics,
    GenerationEvalResult,
    SubjectGenerationSummary,
    AggregateGenerationMetrics,
    GenerationBenchmarkReport,
)
from app.evals.generation_metrics import compute_generation_metrics


# Production prompt template replicated identically from RAGEngine._generate_llm_response
SPPU_SYSTEM_PROMPT = (
    "You are an expert Savitribai Phule Pune University (SPPU) "
    "Exam Intelligence Assistant.\n\n"
    "Your task is to answer the student's question using ONLY "
    "the retrieved engineering study material provided below.\n\n"
    "IMPORTANT RULES:\n"
    "1. Do not use external knowledge when it is not supported by "
    "the retrieved context.\n"
    "2. If the context does not contain enough information, clearly "
    "state: 'Confidence: Low. Insufficient evidence in uploaded "
    "documents to answer.'\n"
    "3. Do not invent facts, examples, formulas, definitions, or "
    "citations.\n"
    "4. Cite supporting sources using the source numbers provided "
    "in the context, for example [Source 1, Page 4].\n"
    "5. Write in clear Markdown suitable for an engineering student.\n"
    "6. Prefer structured exam-oriented answers with headings, "
    "bullet points, numbered steps, tables, or formulas when "
    "appropriate.\n"
    "7. For short questions, be concise. For descriptive questions, "
    "provide a sufficiently detailed explanation.\n"
    "8. At the end, provide exactly one confidence line:\n"
    "Confidence: High\n"
    "or\n"
    "Confidence: Medium\n"
    "or\n"
    "Confidence: Low\n\n"
    "Retrieved study material:\n\n{context}"
)


def format_retrieval_context(chunks: Sequence[Dict[str, Any]]) -> str:
    """
    Format retrieved chunks into context string matching RAGEngine._format_context.
    """
    context_blocks = []
    for idx, item in enumerate(chunks):
        metadata = item.get("metadata", {})
        page = metadata.get("page")
        document_name = (
            metadata.get("document_name")
            or metadata.get("filename")
            or f"{item.get('category', 'study')} document"
        )
        page_str = f"Page {page}" if page else "Page Unknown"

        context_blocks.append(
            f"Source [{idx + 1}]: {document_name}, {page_str}\n"
            f"Category: {item.get('category', 'unknown')}\n"
            f"Chunk ID: {item.get('chunk_id', 'unknown')}\n"
            f"Content:\n{item.get('content', '')}\n"
        )

    return "\n---\n".join(context_blocks)


class GenerationEvalRunner:
    """
    Orchestrates the evaluation of generated answers across the evaluation dataset.
    Can be run against local Ollama or an injected mock generator for unit tests.
    """

    def __init__(
        self,
        adapter: EvalRetrievalAdapter,
        llm_client: Optional[AsyncOpenAI] = None,
        llm_model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 800,
        generation_fn: Optional[Callable[[str, str], Any]] = None,
    ):
        self.adapter = adapter
        self.llm_model = llm_model or settings.LLM_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.generation_fn = generation_fn

        # Default Ollama client matching RAGEngine
        if llm_client is not None:
            self.client = llm_client
        else:
            self.client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY or "ollama",
                base_url=settings.OPENAI_API_BASE or "http://localhost:11434/v1",
            )

    async def _call_llm(self, query: str, context: str) -> str:
        """Call Ollama via AsyncOpenAI client matching RAGEngine._generate_llm_response."""
        if self.generation_fn is not None:
            res = self.generation_fn(query, context)
            if asyncio.iscoroutine(res):
                return await res
            return res

        system_prompt = SPPU_SYSTEM_PROMPT.format(context=context)
        response = await self.client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("The local LLM returned an empty response.")
        return content.strip()

    async def evaluate_single_case(
        self,
        case: EvalCase,
        retrieval_limit: int = 4,
    ) -> GenerationEvalResult:
        """
        Execute retrieval + generation + deterministic evaluation for a single case.
        """
        errors: List[str] = []
        warnings: List[str] = []
        generated_answer = ""
        success = True

        # 1. Execute production retrieval via adapter (Hybrid + Reranked)
        # Sliced to 4 to match RAGEngine.get_grounded_answer(limit=4)
        retrieved_chunks = self.adapter.retrieve(
            configuration="hybrid_reranked",
            query=case.query,
            limit=retrieval_limit,
        )

        # Preserve retrieved chunks
        preserved: List[PreservedRetrievedChunk] = []
        for rank, chunk in enumerate(retrieved_chunks, start=1):
            meta = chunk.get("metadata", {})
            page_val = meta.get("page") if meta else 1
            preserved.append(PreservedRetrievedChunk(
                chunk_id=str(chunk.get("chunk_id", "")),
                document_name=str(meta.get("document_name", "Unknown")),
                page=int(page_val) if page_val is not None else 1,
                rank=rank,
                content=str(chunk.get("content", "")),
                score=chunk.get("score"),
            ))

        retrieved_ids = [p.chunk_id for p in preserved]

        # 2. If no chunks retrieved, production RAG returns fallback
        if not retrieved_chunks:
            generated_answer = "Confidence: Low. Insufficient evidence in uploaded documents to answer."
            warnings.append("No reference chunks retrieved from corpus.")
        else:
            # 3. Format context
            context_str = format_retrieval_context(retrieved_chunks)

            # 4. Generate answer via Ollama
            try:
                generated_answer = await self._call_llm(case.query, context_str)
            except Exception as exc:
                success = False
                err_msg = f"Generation failed: {type(exc).__name__}: {str(exc)}"
                errors.append(err_msg)
                generated_answer = f"[ERROR] {err_msg}"

        # 5. Evaluate deterministic metrics
        if success and generated_answer:
            metrics, citation_results = compute_generation_metrics(
                answer=generated_answer,
                expected_concepts=case.expected_concepts,
                retrieved_chunks=retrieved_chunks,
            )
        else:
            # On generation failure, all scores are zero
            metrics = GenerationMetrics(
                concept_coverage=0.0,
                grounded_concept_coverage=0.0,
                citation_validity=0.0,
                citation_source_match=0.0,
                confidence_format_compliance=0.0,
            )
            citation_results = []

        return GenerationEvalResult(
            eval_id=case.case_id,
            subject=case.subject,
            unit=case.unit,
            question=case.query,
            answer=generated_answer,
            expected_concepts=case.expected_concepts,
            retrieved_chunk_ids=retrieved_ids,
            retrieved_chunks=preserved,
            metrics=metrics,
            citation_results=citation_results,
            generation_success=success,
            errors=errors,
            warnings=warnings,
        )

    async def evaluate_dataset(
        self,
        dataset: EvalDataset,
        dataset_path: str = "app/evals/data/sppu_engineering_eval_dataset.json",
        subject_filter: Optional[str] = None,
        limit_cases: Optional[int] = None,
        retrieval_limit: int = 4,
    ) -> GenerationBenchmarkReport:
        """
        Run the complete generation evaluation across all dataset cases.
        """
        cases_to_eval = dataset.cases
        if subject_filter:
            cases_to_eval = [c for c in cases_to_eval if c.subject.lower() == subject_filter.lower()]
        if limit_cases and limit_cases > 0:
            cases_to_eval = cases_to_eval[:limit_cases]

        results: List[GenerationEvalResult] = []
        total_eval_cases = len(cases_to_eval)
        for idx, case in enumerate(cases_to_eval, start=1):
            print(f"[{idx}/{total_eval_cases}] Evaluating {case.case_id} ({case.subject})...", flush=True)
            res = await self.evaluate_single_case(case, retrieval_limit=retrieval_limit)
            results.append(res)

        # Compute aggregate metrics
        total = len(results)
        success_count = sum(1 for r in results if r.generation_success)
        fail_count = total - success_count
        success_rate = (success_count / total) if total > 0 else 0.0

        mean_cc = sum(r.metrics.concept_coverage for r in results) / total if total > 0 else 0.0
        mean_gcc = sum(r.metrics.grounded_concept_coverage for r in results) / total if total > 0 else 0.0
        mean_cv = sum(r.metrics.citation_validity for r in results) / total if total > 0 else 0.0
        mean_csm = sum(r.metrics.citation_source_match for r in results) / total if total > 0 else 0.0
        conf_rate = sum(r.metrics.confidence_format_compliance for r in results) / total if total > 0 else 0.0

        agg_metrics = AggregateGenerationMetrics(
            total_cases=total,
            successful_generation_count=success_count,
            failed_generation_count=fail_count,
            successful_generation_rate=round(success_rate, 4),
            mean_concept_coverage=round(mean_cc, 4),
            mean_grounded_concept_coverage=round(mean_gcc, 4),
            mean_citation_validity=round(mean_cv, 4),
            mean_citation_source_match=round(mean_csm, 4),
            confidence_compliance_rate=round(conf_rate, 4),
        )

        # Subject-level breakdowns
        subjects = sorted(list({r.subject for r in results if r.subject}))
        subject_summaries: Dict[str, SubjectGenerationSummary] = {}
        for s in subjects:
            s_res = [r for r in results if r.subject == s]
            s_tot = len(s_res)
            s_succ = sum(1 for r in s_res if r.generation_success)
            s_succ_rate = (s_succ / s_tot) if s_tot > 0 else 0.0
            s_cc = sum(r.metrics.concept_coverage for r in s_res) / s_tot if s_tot > 0 else 0.0
            s_gcc = sum(r.metrics.grounded_concept_coverage for r in s_res) / s_tot if s_tot > 0 else 0.0
            s_cv = sum(r.metrics.citation_validity for r in s_res) / s_tot if s_tot > 0 else 0.0
            s_csm = sum(r.metrics.citation_source_match for r in s_res) / s_tot if s_tot > 0 else 0.0
            s_conf = sum(r.metrics.confidence_format_compliance for r in s_res) / s_tot if s_tot > 0 else 0.0

            subject_summaries[s] = SubjectGenerationSummary(
                subject=s,
                total_cases=s_tot,
                mean_concept_coverage=round(s_cc, 4),
                mean_grounded_concept_coverage=round(s_gcc, 4),
                mean_citation_validity=round(s_cv, 4),
                mean_citation_source_match=round(s_csm, 4),
                confidence_compliance_rate=round(s_conf, 4),
                generation_success_rate=round(s_succ_rate, 4),
            )

        # Identify failure cases:
        # generation failure, concept cov < 0.5, grounded cov < 0.5, cit validity < 1.0, cit match < 1.0, or conf == 0
        failures: List[GenerationEvalResult] = []
        for r in results:
            m = r.metrics
            is_failure = (
                not r.generation_success
                or m.concept_coverage < 0.5
                or m.grounded_concept_coverage < 0.5
                or m.citation_validity < 1.0
                or m.citation_source_match < 1.0
                or m.confidence_format_compliance == 0.0
            )
            if is_failure:
                failures.append(r)

        return GenerationBenchmarkReport(
            evaluation_scope="Production RAG retrieval and Ollama generation evaluated on the frozen 35-case benchmark corpus.",
            dataset_name=dataset.dataset_name,
            dataset_version=dataset.version,
            dataset_path=dataset_path,
            corpus_version=dataset.corpus_version,
            model=self.llm_model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            total_cases=total,
            aggregate_metrics=agg_metrics,
            subject_metrics=subject_summaries,
            case_results=results,
            failures=failures,
        )


def generate_generation_markdown_report(report: GenerationBenchmarkReport) -> str:
    """
    Format a GenerationBenchmarkReport into clean Markdown.
    """
    agg = report.aggregate_metrics
    lines = [
        "# RAG Generation + Grounding Benchmark Report",
        "",
        f"- **Evaluation Scope**: {report.evaluation_scope}",
        f"- **Dataset**: {report.dataset_name} (v{report.dataset_version})",
        f"- **Corpus Version**: {report.corpus_version}",
        f"- **Model**: `{report.model}`",
        f"- **Temperature**: `{report.temperature}` | **Max Tokens**: `{report.max_tokens}`",
        f"- **Timestamp**: `{report.timestamp}`",
        f"- **Total Cases**: {agg.total_cases}",
        "",
        "## Aggregate Metrics",
        "",
        "| Metric | Score | Notes |",
        "| :--- | :---: | :--- |",
        f"| **Generation Success Rate** | **{agg.successful_generation_rate * 100:.1f}%** | {agg.successful_generation_count}/{agg.total_cases} completed without error |",
        f"| **Mean Concept Coverage** | **{agg.mean_concept_coverage:.4f}** | Proportion of syllabus concepts present in answer |",
        f"| **Mean Grounded Concept Coverage** | **{agg.mean_grounded_concept_coverage:.4f}** | Context-overlap proxy (concepts in both context & answer) |",
        f"| **Mean Citation Validity** | **{agg.mean_citation_validity:.4f}** | Parsed citations referencing valid source indices (1..k) |",
        f"| **Mean Citation Source Match** | **{agg.mean_citation_source_match:.4f}** | Cited page numbers matching chunk metadata |",
        f"| **Confidence Compliance Rate** | **{agg.confidence_compliance_rate * 100:.1f}%** | Answers containing valid `Confidence:` indicator |",
        "",
        "> [!NOTE]",
        "> **Grounded Concept Coverage** is a deterministic lexical/context overlap proxy and does NOT represent full semantic faithfulness.",
        "",
        "## Per-Subject Metrics",
        "",
        "| Subject | Cases | Success Rate | Concept Coverage | Grounded Coverage | Citation Validity | Citation Match | Confidence Compliance |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for subj, s in sorted(report.subject_metrics.items()):
        lines.append(
            f"| **{subj}** | {s.total_cases} | {s.generation_success_rate * 100:.1f}% | "
            f"{s.mean_concept_coverage:.4f} | {s.mean_grounded_concept_coverage:.4f} | "
            f"{s.mean_citation_validity:.4f} | {s.mean_citation_source_match:.4f} | "
            f"{s.confidence_compliance_rate * 100:.1f}% |"
        )

    lines.append("")

    # Failures & Low Compliance Cases
    lines.extend([
        f"## Failure Analysis ({len(report.failures)} cases with deficiencies)",
        "",
        "Criteria for flag: generation error, concept coverage < 0.5, grounded coverage < 0.5, citation validity < 1.0, citation page mismatch, or confidence compliance = 0.",
        "",
    ])

    if not report.failures:
        lines.append("No generation or grounding failures recorded across evaluated cases.\n")
    else:
        for idx, fail in enumerate(report.failures, start=1):
            m = fail.metrics
            q_short = fail.question[:75] + ("..." if len(fail.question) > 75 else "")
            lines.extend([
                f"### {idx}. [{fail.eval_id}] ({fail.subject} {fail.unit})",
                f"- **Question**: {q_short}",
                f"- **Metrics**: Concept Cov: `{m.concept_coverage:.2f}` | Grounded Cov: `{m.grounded_concept_coverage:.2f}` | Cit Validity: `{m.citation_validity:.2f}` | Cit Match: `{m.citation_source_match:.2f}` | Conf Compliance: `{m.confidence_format_compliance:.1f}`",
                f"- **Retrieved Chunks**: `{fail.retrieved_chunk_ids}`",
            ])
            if fail.errors:
                lines.append(f"- **Errors**: `{fail.errors}`")
            # Truncate answer for readability in report
            ans_snippet = fail.answer.strip().replace("\n", " ")
            if len(ans_snippet) > 200:
                ans_snippet = ans_snippet[:200] + "..."
            lines.append(f"- **Answer Snippet**: \"{ans_snippet}\"\n")

    return "\n".join(lines) + "\n"


async def run_generation_benchmark_cli():
    """
    CLI Entry point to execute the generation benchmark.
    Usage: python -m app.evals.generation_runner [--subject SPOS] [--limit 5]
    """
    parser = argparse.ArgumentParser(description="Run ExamGPT Generation & Grounding Benchmark")
    parser.add_argument("--dataset", type=str, default="app/evals/data/sppu_engineering_eval_dataset.json")
    parser.add_argument("--corpus", type=str, default="app/evals/data/frozen_eval_corpus.json")
    parser.add_argument("--output-dir", type=str, default="app/evals/reports")
    parser.add_argument("--subject", type=str, default=None, help="Filter to specific subject (SPOS, CN, DBMS, TOC)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases to evaluate")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    corpus_path = Path(args.corpus)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading frozen corpus from {corpus_path}...")
    corpus = load_frozen_corpus(corpus_path)
    print(f"Loading evaluation dataset from {dataset_path}...")
    dataset = load_eval_dataset(dataset_path)

    print("Initializing retrieval adapter with frozen corpus...")
    adapter = EvalRetrievalAdapter(corpus, precompute_embeddings=True)

    runner = GenerationEvalRunner(adapter=adapter)

    print(f"Executing Generation Benchmark on {dataset.dataset_name} using model {runner.llm_model}...")
    report = await runner.evaluate_dataset(
        dataset=dataset,
        dataset_path=str(dataset_path),
        subject_filter=args.subject,
        limit_cases=args.limit,
    )

    # Save JSON report
    json_path = output_dir / "generation_benchmark_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"Saved JSON report to {json_path}")

    # Save Markdown report
    md_report = generate_generation_markdown_report(report)
    md_path = output_dir / "generation_benchmark_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"Saved Markdown report to {md_path}")

    # Print summary
    agg = report.aggregate_metrics
    print("\nBenchmark Execution Complete:")
    print(f"  Total Cases: {agg.total_cases}")
    print(f"  Success Rate: {agg.successful_generation_rate * 100:.1f}%")
    print(f"  Mean Concept Coverage: {agg.mean_concept_coverage:.4f}")
    print(f"  Mean Grounded Concept Coverage: {agg.mean_grounded_concept_coverage:.4f}")
    print(f"  Mean Citation Validity: {agg.mean_citation_validity:.4f}")
    print(f"  Mean Citation Source Match: {agg.mean_citation_source_match:.4f}")
    print(f"  Confidence Compliance Rate: {agg.confidence_compliance_rate * 100:.1f}%")
    print(f"  Total Failures/Deficiencies: {len(report.failures)}")


if __name__ == "__main__":
    asyncio.run(run_generation_benchmark_cli())
