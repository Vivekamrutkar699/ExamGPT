import re
from typing import Optional


class MetadataExtractor:
    """
    Analyzes raw chunk content using regex heuristics to extract SPPU syllabus metadata:
    Units (Unit 1 to 6), chapter names, and syllabus subject topics.
    """

    def extract_unit_tag(self, text: str) -> Optional[str]:
        """
        Scan text to match syllabus unit notations:
        e.g., 'Unit 1', 'Unit I', 'UNIT - II', 'UNIT 3'
        """
        # Match "unit" followed by spaces, dashes, roman numerals or normal numbers
        unit_pattern = re.compile(
            r'\b(?:UNIT|Unit)\s*[-:]?\s*([0-9]+|[IVXLCDM]+)\b',
            re.IGNORECASE
        )
        match = unit_pattern.search(text)
        if match:
            unit_val = match.group(1).upper()
            
            # Map Roman numerals to digits for uniformity
            roman_to_digit = {
                "I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6"
            }
            digit = roman_to_digit.get(unit_val, unit_val)
            return f"Unit {digit}"
            
        return None

    def extract_chapter_title(self, text: str) -> Optional[str]:
        """
        Identify headings by checking capitalized text runs 
        or lines demarcated by numeric syllabus titles (e.g. '1.1 Introduction').
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return None

        # Check top lines in chunk
        for line in lines[:3]:
            # Matches format "1.2 Introduction" or "Chapter 1: Neural Networks"
            if re.match(r'^(?:[0-9]+\.[0-9]+|[A-Za-z]+\s+[0-9]+)\s+[A-Z]', line) or \
               (len(line) < 60 and line.isupper() and not line.endswith(".")):
                return line
                
        return None

    def extract_metadata(self, text: str) -> dict:
        """
        Parse details and compile metadata schema.
        """
        unit = self.extract_unit_tag(text)
        chapter = self.extract_chapter_title(text)
        
        return {
            "unit_tag": unit,
            "section_title": chapter
        }


# Singleton instance
metadata_extractor = MetadataExtractor()
