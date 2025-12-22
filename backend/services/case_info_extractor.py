"""Case information extraction from deposition transcripts."""
import re
import logging
from typing import Dict, List, Optional
from datetime import datetime
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class CaseInfoExtractor:
    """Extract case metadata from first 10 pages of transcript."""
    
    def __init__(self):
        # Case name patterns
        self.case_name_single_line = [
            re.compile(r'([A-Z][A-Za-z\s,\.&]+)\s+(?:v\.|vs\.|vs|v)\s+([A-Z][A-Za-z\s,\.&]+)', re.IGNORECASE),
            re.compile(r'In\s+re:?\s+([A-Z][A-Za-z\s,\.&]+)', re.IGNORECASE),
            re.compile(r'In\s+the\s+matter\s+of:?\s+([A-Z][A-Za-z\s,\.&]+)', re.IGNORECASE),
        ]
        
        # Case number patterns
        self.case_number_patterns = [
            re.compile(r'Case\s+(?:No\.|Number)[:\s]+([A-Z0-9\-]+)', re.IGNORECASE),
            re.compile(r'Case\s+#[:\s]*([A-Z0-9\-]+)', re.IGNORECASE),
            re.compile(r'Civil\s+(?:Action|Case)\s+(?:No\.|Number)[:\s]+([A-Z0-9\-]+)', re.IGNORECASE),
        ]
        
        # Date patterns
        self.date_patterns = [
            re.compile(r'(?:Date|Taken\s+on|Deposition\s+Date)[:\s]+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})', re.IGNORECASE),
            re.compile(r'(?:Date|Taken\s+on|Deposition\s+Date)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})', re.IGNORECASE),
            re.compile(r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})'),  # Any date format
            re.compile(r'(\d{1,2}/\d{1,2}/\d{2,4})'),  # MM/DD/YYYY or MM/DD/YY
        ]
        
        # Attorney patterns (signature blocks)
        self.attorney_signature_patterns = [
            re.compile(r'(?:Attorney|Counsel)\s+for\s+(?:Plaintiff|Defendant|Petitioner|Respondent)[s]?[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', re.IGNORECASE),
            re.compile(r'([A-Z][A-Z\s\.]+)\s*\n\s*(?:Attorney|Counsel)\s+for', re.IGNORECASE),
        ]
        
        # Attorney patterns (BY statements in Q&A)
        self.attorney_by_patterns = [
            re.compile(r'BY\s+M[RS]\.\s+([A-Z][a-z]+)', re.IGNORECASE),
        ]
        
        # Witness patterns
        self.witness_patterns = [
            re.compile(r'Deposition\s+of\s+([A-Z][A-Z\s\.]+)', re.IGNORECASE),
            re.compile(r'(?:Witness|Deponent)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', re.IGNORECASE),
        ]
    
    def extract_case_info(self, pdf_path: str, max_pages: int = 10) -> Dict:
        """
        Extract case information from the first N pages.
        
        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum pages to scan (default 10)
        
        Returns:
            Dict with case_name, case_number, deposition_date, attorneys, witness_name
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = min(max_pages, len(doc))
            
            # Collect text from first N pages
            all_text = ""
            for page_num in range(total_pages):
                page = doc[page_num]
                all_text += page.get_text() + "\n\n"
            
            doc.close()
            
            # Extract each field
            result = {
                'case_name': self._extract_case_name(all_text),
                'case_number': self._extract_case_number(all_text),
                'deposition_date': self._extract_deposition_date(all_text),
                'attorneys': self._extract_attorneys(all_text),
                'witness_name': self._extract_witness(all_text),
            }
            
            logger.info(f"Extracted case info: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract case info: {e}", exc_info=True)
            return {
                'case_name': None,
                'case_number': None,
                'deposition_date': None,
                'attorneys': [],
                'witness_name': None,
            }
    
    def _extract_case_name(self, text: str) -> Optional[str]:
        """Extract case name from single-line or multi-line formats."""
        # Try single-line patterns first
        for pattern in self.case_name_single_line:
            match = pattern.search(text)
            if match:
                if 'in re' in match.group(0).lower() or 'matter of' in match.group(0).lower():
                    return match.group(1).strip()
                else:
                    # v./vs. format - combine both parties
                    party1 = match.group(1).strip()
                    party2 = match.group(2).strip()
                    return f"{party1} v. {party2}"
        
        # Try multi-line format (Plaintiff ... v. ... Defendant)
        plaintiff_match = re.search(
            r'([A-Z][A-Za-z\s,\.&]+?),?\s*\n+\s*Plaintiff[s]?\s*(?:\(s\))?',
            text,
            re.IGNORECASE | re.MULTILINE
        )
        
        if plaintiff_match:
            defendant_match = re.search(
                r'(?:v\.|vs\.|vs|v)\s*\n+\s*([A-Z][A-Za-z\s,\.&]+?),?\s*\n+\s*Defendant[s]?\s*(?:\(s\))?',
                text[plaintiff_match.end():plaintiff_match.end() + 500],
                re.IGNORECASE | re.MULTILINE
            )
            
            if defendant_match:
                plaintiff = plaintiff_match.group(1).strip()
                defendant = defendant_match.group(1).strip()
                return f"{plaintiff} v. {defendant}"
        
        return None
    
    def _extract_case_number(self, text: str) -> Optional[str]:
        """Extract case number."""
        for pattern in self.case_number_patterns:
            match = pattern.search(text)
            if match:
                case_num = match.group(1).strip()
                # Validate it looks like a case number (has letters and numbers or hyphens)
                if re.match(r'^[A-Z0-9\-]+$', case_num, re.IGNORECASE):
                    return case_num
        
        return None
    
    def _extract_deposition_date(self, text: str) -> Optional[str]:
        """Extract deposition date."""
        # Try keyword-based patterns first (more reliable)
        for pattern in self.date_patterns[:2]:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        
        # Fall back to any date in first 1000 chars (likely on cover page)
        first_section = text[:1000]
        for pattern in self.date_patterns[2:]:
            match = pattern.search(first_section)
            if match:
                date_str = match.group(1).strip()
                # Try to validate it's a reasonable date
                try:
                    # Just check if year is reasonable (2000-2099)
                    if re.search(r'20\d{2}', date_str):
                        return date_str
                except:
                    pass
        
        return None
    
    def _extract_attorneys(self, text: str) -> List[str]:
        """Extract attorney names from signature blocks and BY statements."""
        attorneys = set()
        
        # Extract from signature blocks
        for pattern in self.attorney_signature_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                name = match.group(1).strip()
                # Clean up name
                name = re.sub(r'\s+', ' ', name)
                if len(name) > 3 and len(name) < 50:  # Reasonable name length
                    attorneys.add(name)
        
        # Extract from BY statements
        for pattern in self.attorney_by_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                name = match.group(1).strip()
                if len(name) > 2:
                    attorneys.add(f"Mr./Ms. {name}")
        
        return sorted(list(attorneys))
    
    def _extract_witness(self, text: str) -> Optional[str]:
        """Extract witness name."""
        # Try "Deposition of" format (most reliable)
        for pattern in self.witness_patterns:
            match = pattern.search(text[:2000])  # Look in first section
            if match:
                name = match.group(1).strip()
                # Clean up name (remove extra spaces, convert to title case)
                name = re.sub(r'\s+', ' ', name)
                name = ' '.join(word.capitalize() for word in name.split())
                
                if len(name) > 3 and len(name) < 100:
                    return name
        
        return None


# Global instance
case_info_extractor = CaseInfoExtractor()

