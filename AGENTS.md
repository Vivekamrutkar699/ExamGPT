# ExamGPT Engineering Instructions

## Project

ExamGPT is an AI-powered engineering exam intelligence and personalized learning platform for SPPU engineering students.

The goal is not to build a generic chatbot.

The core product loop is:

University Study Material
        +
Previous Year Questions
        +
Student Performance
        ↓
Exam Intelligence
        ↓
Topic Priority
        ↓
Personalized Learning
        ↓
New Student Performance
        ↓
Updated Mastery
        ↓
Updated Priority

## Current Stack

Backend:
- Python
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic
- JWT authentication
- SQLite for local development
- PostgreSQL-compatible architecture

AI:
- Ollama
- llama3.2:3b
- Sentence Transformers
- all-MiniLM-L6-v2
- RAG
- Dense retrieval
- Lexical retrieval
- Reciprocal Rank Fusion
- Reranking

Frontend:
- Next.js
- React
- TypeScript
- Tailwind CSS

Infrastructure:
- Docker Compose
- Git/GitHub

## Existing Architecture

Frontend
    ↓
FastAPI API
    ↓
Schema
    ↓
Service
    ↓
Repository
    ↓
SQLAlchemy Model
    ↓
Database

Do not bypass this architecture without a strong reason.

## Important Existing Features

Already working and tested:

1. Authentication
2. Document upload
3. PDF parsing
4. Semantic chunking
5. Sentence Transformer embeddings
6. Vector indexing
7. Hybrid RAG retrieval
8. RRF retrieval fusion
9. Reranking
10. Ollama grounded Q&A
11. Chat sessions
12. Chat citations
13. PYQ ingestion
14. Semantic PYQ duplicate detection
15. PYQ occurrence counting
16. PYQ analytics
17. Exam Priority Engine
18. Student answer evaluation using grounded Ollama evaluation
19. Student mastery calculation
20. Priority recalculation based on student weakness

## Important Current APIs

Document:
POST /api/v1/documents/upload

Chat:
POST /api/v1/chats/
POST /api/v1/chats/{session_id}/message

PYQ:
POST /api/v1/pyqs/subjects/{subject_id}/upload
GET /api/v1/pyqs/subjects/{subject_id}/analytics
GET /api/v1/pyqs/subjects/{subject_id}/list

Evaluation:
POST /api/v1/evaluations/
GET /api/v1/evaluations/subject/{subject_id}

Analytics:
GET /api/v1/analytics/subjects/{subject_id}
GET /api/v1/analytics/subjects/{subject_id}/exam-priority

## Current Exam Priority Formula

When student performance exists:

frequency_score = normalized PYQ frequency
marks_score = normalized marks weight
weakness_score = 1 - student mastery

priority_score =
    0.40 * frequency_score
  + 0.30 * marks_score
  + 0.30 * weakness_score

When student performance does not exist:

priority_score =
    0.60 * frequency_score
  + 0.40 * marks_score

This is called Exam Priority / Exam Focus.

Do NOT call it exam prediction or claim probability of appearing in the exam.

## Current Known Limitations

The current system still needs improvement:

1. PYQs are currently question-level rather than canonical topic-level.
2. Different wording of the same concept may remain separate.
3. PYQ occurrence history does not preserve each paper occurrence independently.
4. Marks history is currently simplified.
5. Unit extraction for PYQs is weak.
6. Quiz attempt history is incomplete.
7. Study planner still contains prototype behavior.
8. Frontend does not yet expose the full Exam Intelligence workflow.
9. RAG needs a formal evaluation harness.
10. Citation validation needs improvement.
11. Test coverage needs improvement.

## Development Philosophy

Do NOT blindly add features.

For every feature:

1. Inspect the existing architecture.
2. Understand existing models/services/repositories.
3. Design the change.
4. Explain important tradeoffs.
5. Implement.
6. Run tests.
7. Run compile/type checks where appropriate.
8. Test the API.
9. Inspect git diff.
10. Only then commit.

Prefer small, logically isolated commits.

Do not rewrite working systems unnecessarily.

Do not replace real functionality with mocks or hardcoded demo values.

Do not fabricate metrics.

Do not introduce paid APIs.

Ollama must remain the default LLM for local development.

## AI Quality Requirements

AI-generated answers must be grounded in retrieved study material.

The system must avoid:
- fabricated citations
- fabricated exam probabilities
- unrelated evaluation keywords
- hardcoded feedback
- hardcoded student performance
- hardcoded quiz performance
- fake analytics

If evidence is unavailable, explicitly represent that uncertainty.

## Data Integrity

Do not manually modify the SQLite database to make tests pass.

Use application code, APIs, migrations, or controlled test fixtures.

Do not silently delete existing user data.

If a schema change is required:
- create an Alembic migration
- preserve existing data where possible
- explain migration risks

## Testing Requirements

Every major backend feature should have tests.

Prefer:
- unit tests for scoring logic
- service tests
- API tests
- integration tests for RAG where practical

Important metrics should have deterministic test cases.

## RAG Evaluation

Eventually implement an evaluation harness measuring:

- retrieval recall@k
- context relevance
- answer relevance
- grounding/faithfulness
- citation validity

Compare retrieval configurations when appropriate:

- dense only
- lexical only
- hybrid
- hybrid + reranker

Do not claim improvements without measured results.

## Topic Intelligence

The desired future model is:

PYQ occurrence
    ↓
canonical topic
    ↓
topic frequency
    ↓
marks distribution
    ↓
student mastery
    ↓
exam priority

A topic should represent a concept, not merely one exact question wording.

## Git Rules

Before modifying code:

git status

After implementation:

git diff
git status

Run relevant tests.

Commit logically grouped changes.

Never commit:
- .env
- API keys
- local databases
- uploaded documents
- vector databases
- model weights

## Security

Never expose secrets.

Never commit backend/.env.

Use backend/.env.example for configuration examples.

Validate authenticated resource ownership.

Do not weaken authorization to make tests pass.

## Code Quality

Prefer:
- type hints
- clear names
- small functions
- explicit error handling
- reusable services
- repository pattern consistent with existing code

Avoid:
- giant functions
- duplicated logic
- unexplained magic numbers
- unnecessary dependencies
- premature abstractions

## Current Priority

The next major architectural task is:

Redesign PYQ intelligence from question-level records into canonical topic-level intelligence while preserving existing behavior.

Before coding, inspect:
- app/models/question.py
- app/services/pyq.py
- app/repositories/question.py
- app/schemas/question.py
- app/api/v1/endpoints/pyqs.py
- app/models/answers_evaluation.py
- app/repositories/evaluation.py
- app/services/analytics.py
- app/schemas/analytics.py

Do not implement until the architecture and migration plan are understood.