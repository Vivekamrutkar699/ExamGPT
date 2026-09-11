import re


class QueryProcessor:
    """
    Handles preprocessing of student queries: intent classification 
    and expansion of casual terms into formal engineering terminology.
    """

    def detect_intent(self, query: str) -> str:
        """
        Classify queries into distinct categories to direct agent tasks:
        MCQ, Short, Long, Viva, Concept, Numerical, or Code.
        """
        query_lower = query.lower()
        
        # Heuristics keywords checks
        if any(w in query_lower for w in ["viva", "oral", "examiner", "question for viva"]):
            return "viva"
        elif any(w in query_lower for w in ["code", "program", "function", "java", "python", "c++", "algorithm"]):
            return "code"
        elif any(w in query_lower for w in ["solve", "calculate", "numerical", "equation", "formula", "value"]):
            return "numerical"
        elif any(w in query_lower for w in ["mcq", "multiple choice", "option", "quiz"]):
            return "mcq"
        elif any(w in query_lower for w in ["explain", "describe", "what is", "define", "concept"]):
            return "concept"
        
        # Default
        return "general"

    def rewrite_query(self, query: str) -> str:
        """
        Expand acronyms and engineering slangs to align with standard reference textbooks.
        """
        expanded = query.strip()
        
        # Engineering mapping rules
        abbreviations = {
            r'\bdma\b': 'Direct Memory Access (DMA)',
            r'\bcn\b': 'Computer Networks',
            r'\bos\b': 'Operating System',
            r'\bdbms\b': 'Database Management System (DBMS)',
            r'\bse\b': 'Software Engineering',
            r'\btoc\b': 'Theory of Computation',
            r'\bspos\b': 'System Programming and Operating System',
            r'\bds\b': 'Data Structures',
            r'\bda\b': 'Design and Analysis of Algorithms',
            r'\bco\b': 'Computer Organization',
            r'\bcoa\b': 'Computer Organization and Architecture',
            r'\bpyq\b': 'Previous Year Question',
            r'\bpyqs\b': 'Previous Year Questions',
            r'\bsppu\b': 'Savitribai Phule Pune University',
        }
        
        for abbreviation, replacement in abbreviations.items():
            expanded = re.sub(abbreviation, replacement, expanded, flags=re.IGNORECASE)
            
        return expanded


# Singleton instance
query_processor = QueryProcessor()
