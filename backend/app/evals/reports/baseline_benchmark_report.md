# RAG Retrieval Architecture Benchmark Comparison

- **Dataset**: SPPU Engineering Core Evaluation Dataset (v1.0.0)
- **Corpus Version**: 1.0.0
- **Total Cases**: 35

## Configuration Comparison

| Configuration | Recall@3 | Recall@5 | MRR | Context Relevance | Zero MRR Cases |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **dense** | **1.0000** | **1.0000** | **1.0000** | **0.5086** | 0 |
| **lexical** | **0.9714** | **1.0000** | **0.9771** | **0.4881** | 0 |
| **hybrid** | **1.0000** | **1.0000** | **0.9857** | **0.4686** | 0 |
| **hybrid_reranked** | **0.9714** | **1.0000** | **0.9786** | **0.4686** | 0 |

> [!NOTE]
> - **Evaluation Scope**: Production retrieval algorithms evaluated on a frozen benchmark corpus.
> - **Recall@k**: Fraction of golden relevant chunks present in the top-k retrieved candidates.
> - **MRR (Mean Reciprocal Rank)**: 1 / rank of the first golden chunk retrieved (or 0.0 if not found).
> - **Context Relevance**: Deterministic keyword and metadata proxy metric, NOT an LLM judge.

## Per-Subject Breakdown Across Configurations

| Subject | Configuration | Mean Recall@3 | Mean Recall@5 | Mean MRR | Mean Context Relevance |
| :--- | :--- | :---: | :---: | :---: | :---: |
| CN | dense | 1.0000 | 1.0000 | 1.0000 | 0.4750 |
| CN | lexical | 0.8750 | 1.0000 | 0.9000 | 0.4396 |
| CN | hybrid | 1.0000 | 1.0000 | 0.9375 | 0.4000 |
| CN | hybrid_reranked | 0.8750 | 1.0000 | 0.9062 | 0.4000 |
| DBMS | dense | 1.0000 | 1.0000 | 1.0000 | 0.5000 |
| DBMS | lexical | 1.0000 | 1.0000 | 1.0000 | 0.6111 |
| DBMS | hybrid | 1.0000 | 1.0000 | 1.0000 | 0.5000 |
| DBMS | hybrid_reranked | 1.0000 | 1.0000 | 1.0000 | 0.5000 |
| SPOS | dense | 1.0000 | 1.0000 | 1.0000 | 0.5750 |
| SPOS | lexical | 1.0000 | 1.0000 | 1.0000 | 0.4875 |
| SPOS | hybrid | 1.0000 | 1.0000 | 1.0000 | 0.5000 |
| SPOS | hybrid_reranked | 1.0000 | 1.0000 | 1.0000 | 0.5000 |
| TOC | dense | 1.0000 | 1.0000 | 1.0000 | 0.3600 |
| TOC | lexical | 1.0000 | 1.0000 | 1.0000 | 0.4200 |
| TOC | hybrid | 1.0000 | 1.0000 | 1.0000 | 0.4400 |
| TOC | hybrid_reranked | 1.0000 | 1.0000 | 1.0000 | 0.4400 |

## Per-Configuration Retrieval Failures & Rankings

### dense (Failures: 0)
No failures recorded for this configuration.

### lexical (Failures: 0)
No failures recorded for this configuration.

### hybrid (Failures: 0)
No failures recorded for this configuration.

### hybrid_reranked (Failures: 0)
No failures recorded for this configuration.

