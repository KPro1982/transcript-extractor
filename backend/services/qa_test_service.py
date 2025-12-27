"""Q/A extraction test service for document validation."""
import logging
import re
from typing import Dict, List, Tuple
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class QATestService:
    """
    Tests Q/A extraction from PDF before processing.
    
    Extracts a sample of Q/A pairs to verify parsing logic
    and generates a detailed log file for review.
    """
    
    def __init__(self):
        # Q/A detection patterns (same as main pdf_service)
        self.question_patterns = [
            re.compile(r'^[·\s]*Q\.[·\s]*', re.IGNORECASE),
            re.compile(r'^\s*Q\.\s*', re.IGNORECASE),
            re.compile(r'^\s*Q:\s*', re.IGNORECASE),
            re.compile(r'^Q\s+[A-Z]', re.IGNORECASE),
            re.compile(r'^\s*QUESTION[:\s]+', re.IGNORECASE),
            re.compile(r'^BY\s+M[RS]\.\s+\w+:', re.IGNORECASE),
        ]
        
        self.answer_patterns = [
            re.compile(r'^[·\s]*A\.[·\s]*', re.IGNORECASE),
            re.compile(r'^\s*A\.\s*', re.IGNORECASE),
            re.compile(r'^\s*A:\s*', re.IGNORECASE),
            re.compile(r'^A\s+[A-Z]', re.IGNORECASE),
            re.compile(r'^\s*ANSWER[:\s]+', re.IGNORECASE),
            re.compile(r'^[·\s]*THE\s+WITNESS:[·\s]*', re.IGNORECASE),
        ]
    
    def _matches_question_pattern(self, line: str) -> bool:
        """Check if line matches a question pattern."""
        line = line.strip()
        if not line:
            return False
        
        for pattern in self.question_patterns:
            if pattern.match(line):
                return True
        return False
    
    def _matches_answer_pattern(self, line: str) -> bool:
        """Check if line matches an answer pattern."""
        line = line.strip()
        if not line:
            return False
        
        for pattern in self.answer_patterns:
            if pattern.match(line):
                return True
        return False
    
    def _extract_qa_pairs(
        self, 
        pdf_path: str, 
        start_page: int, 
        end_page: int,
        max_pairs: int = 10
    ) -> List[Dict]:
        """
        Extract Q/A pairs from a page range.
        
        Args:
            pdf_path: Path to PDF file
            start_page: First page to extract from (1-based)
            end_page: Last page to extract from (1-based)
            max_pairs: Maximum number of pairs to extract
            
        Returns:
            List of Q/A pair dicts with page/line info
        """
        doc = fitz.open(pdf_path)
        qa_pairs = []
        current_question = None
        current_answer = None
        
        try:
            for page_num in range(start_page - 1, min(end_page, len(doc))):
                page = doc[page_num]
                text = page.get_text("text")
                lines = text.split('\n')
                
                for line_num, line in enumerate(lines, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check for question marker
                    if self._matches_question_pattern(line):
                        # Save previous Q/A pair if complete
                        if current_question and current_answer:
                            qa_pairs.append({
                                'question': current_question,
                                'answer': current_answer,
                                'page': current_question['page'],
                                'line': current_question['line']
                            })
                            
                            if len(qa_pairs) >= max_pairs:
                                return qa_pairs
                        
                        # Start new question
                        current_question = {
                            'text': line,
                            'page': page_num + 1,
                            'line': line_num
                        }
                        current_answer = None
                    
                    # Check for answer marker
                    elif self._matches_answer_pattern(line):
                        if current_question:
                            current_answer = {
                                'text': line,
                                'page': page_num + 1,
                                'line': line_num
                            }
                    
                    # Continue building question or answer
                    else:
                        if current_answer:
                            current_answer['text'] += ' ' + line
                        elif current_question:
                            current_question['text'] += ' ' + line
            
            # Add last pair if complete
            if current_question and current_answer:
                qa_pairs.append({
                    'question': current_question,
                    'answer': current_answer,
                    'page': current_question['page'],
                    'line': current_question['line']
                })
        
        finally:
            doc.close()
        
        return qa_pairs
    
    async def test_qa_extraction(
        self,
        pdf_path: str,
        document_id: str,
        examination_first_page: int,
        examination_last_page: int
    ) -> Dict:
        """
        Test Q/A extraction and generate log file.
        
        Args:
            pdf_path: Path to PDF file
            document_id: Document UUID (for log naming)
            examination_first_page: First page of examination section
            examination_last_page: Last page of examination section
            
        Returns:
            Dict with:
                - success: bool
                - qa_pairs_found: int
                - sample_pairs: List[Dict]
                - log_file: str (path to log file)
                - errors: List[str] (if any)
        """
        try:
            logger.info(f"Starting Q/A extraction test for document {document_id[:8]}...")
            
            # Extract sample Q/A pairs from examination section
            # Take first 10 pairs as test sample
            sample_pairs = self._extract_qa_pairs(
                pdf_path,
                examination_first_page,
                examination_last_page,
                max_pairs=10
            )
            
            # Generate detailed log file
            log_file = f"/tmp/qa_test_{document_id[:8]}.log"
            
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write("Q/A EXTRACTION TEST REPORT\n")
                f.write("="*80 + "\n\n")
                
                f.write(f"Document ID: {document_id}\n")
                f.write(f"Examination Pages: {examination_first_page} - {examination_last_page}\n")
                f.write(f"Sample Pairs Extracted: {len(sample_pairs)}\n")
                f.write("\n" + "="*80 + "\n\n")
                
                if len(sample_pairs) == 0:
                    f.write("⚠️  WARNING: No Q/A pairs found in examination section!\n")
                    f.write("This may indicate:\n")
                    f.write("  1. Incorrect examination page range detection\n")
                    f.write("  2. Non-standard Q/A formatting in transcript\n")
                    f.write("  3. PDF text extraction issues\n")
                else:
                    f.write(f"✅ Successfully extracted {len(sample_pairs)} sample Q/A pairs\n\n")
                    
                    for i, pair in enumerate(sample_pairs, 1):
                        f.write(f"\n{'='*80}\n")
                        f.write(f"PAIR {i} (Page {pair['page']}, Line {pair['line']})\n")
                        f.write(f"{'='*80}\n\n")
                        
                        f.write(f"QUESTION:\n")
                        f.write(f"{pair['question']['text']}\n\n")
                        
                        f.write(f"ANSWER:\n")
                        f.write(f"{pair['answer']['text']}\n")
                
                f.write("\n" + "="*80 + "\n")
                f.write("TEST COMPLETE\n")
                f.write("="*80 + "\n")
            
            success = len(sample_pairs) > 0
            errors = []
            
            if not success:
                errors.append("No Q/A pairs found in examination section")
            
            logger.info(
                f"Q/A extraction test complete: {len(sample_pairs)} pairs found, "
                f"log saved to {log_file}"
            )
            
            return {
                'success': success,
                'qa_pairs_found': len(sample_pairs),
                'sample_pairs': sample_pairs,
                'log_file': log_file,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Q/A extraction test failed: {e}", exc_info=True)
            return {
                'success': False,
                'qa_pairs_found': 0,
                'sample_pairs': [],
                'log_file': None,
                'errors': [str(e)]
            }


# Singleton instance
qa_test_service = QATestService()

