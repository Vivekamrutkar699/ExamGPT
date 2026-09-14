import re
import uuid
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question
from app.schemas.question import QuestionCreate, PYQAnalyticsOut
from app.repositories.question import question_repository
from app.document_processing.metadata import metadata_extractor
from app.services.pyq_topic_ingestion import pyq_topic_ingestion_service


class PYQService:
    """
    Parses past exam papers, extracts question strings and marks,
    maps syllabus units, calculates semantic repetition rates, and builds analytics.
    """

    def _parse_questions_from_text(self, text: str) -> List[dict]:
        """
        Parses text lines using regex to extract individual question lines 
        containing marks indicators, stripping standard prefixes.
        """
        lines = text.split("\n")
        parsed_questions = []

        # Matches bracketed weights like [10M], [5 Marks], [6M], (8 Marks)
        marks_pattern = re.compile(r'[\(\[]\s*([0-9]+)\s*(?:M|marks|Marks|Mark)\s*[\)\]]', re.IGNORECASE)
        # Prefixes to strip: e.g. "Q1. ", "a) ", "1. ", "Q.2 "
        prefix_pattern = re.compile(r'^(?P<number>(?:Q\d+|Q|\d+|[a-z]))[\.:\)]?\s*', re.IGNORECASE)

        for line in lines:
            line = line.strip()
            if not line:
                continue

            match = marks_pattern.search(line)
            if match:
                marks_val = int(match.group(1))
                
                # Remove the marks brackets
                clean_text = marks_pattern.sub("", line).strip()
                # Remove question number prefix
                prefix_match = prefix_pattern.match(clean_text)
                question_number = prefix_match.group("number") if prefix_match else None
                clean_text = prefix_pattern.sub("", clean_text).strip()
                
                if len(clean_text) >= 10:
                    parsed_questions.append({
                        "text": clean_text,
                        "marks_weight": marks_val,
                        "question_number": question_number,
                    })

        return parsed_questions

    async def ingest_pyq_text(
        self,
        db: AsyncSession,
        subject_id: uuid.UUID,
        text: str,
        paper_metadata: Dict[str, Any] | None = None,
    ) -> List[Question]:
        """
        Processes a real paper into topic-aware variants and occurrences while
        returning legacy-compatible Question records.
        """
        parsed_data = self._parse_questions_from_text(text)
        return await pyq_topic_ingestion_service.ingest(db, subject_id, parsed_data, text, paper_metadata)

    async def get_subject_analytics(
        self,
        db: AsyncSession,
        subject_id: uuid.UUID
    ) -> PYQAnalyticsOut:
        """
        Aggregates statistical metrics (unit distributions, marks frequencies,
        top repeated items) over all indexed subject questions.
        """
        questions = await question_repository.get_by_subject(db, subject_id=subject_id)
        
        unit_dist = {}
        marks_dist = {}
        
        for q in questions:
            unit = q.unit_tag or "General/Unmapped"
            unit_dist[unit] = unit_dist.get(unit, 0) + 1
            
            # Group marks weight to thresholds string representation
            mark_key = f"{q.marks_weight}M"
            marks_dist[mark_key] = marks_dist.get(mark_key, 0) + 1

        # Sort top repeated questions (sorting by occurrences desc, then marks weight desc)
        sorted_qs = sorted(questions, key=lambda x: (x.occurrences, x.marks_weight), reverse=True)

        return PYQAnalyticsOut(
            total_pyqs=len(questions),
            unit_distribution=unit_dist,
            marks_distribution=marks_dist,
            top_repeated=sorted_qs[:10]  # top 10 repeats
        )


# Singleton service instance
pyq_service = PYQService()
