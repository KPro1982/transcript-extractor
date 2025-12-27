"""Fast page-by-page classification service for deposition transcripts."""
import logging
import re
from typing import Dict, List
import fitz  # PyMuPDF

from services.db_service import db_service

logger = logging.getLogger(__name__)


class PageClassifier:
    """
    Fast page-by-page classifier for transcript pages.
    
    Classifies each page as:
    - frontpages: Before examination (no Q. or no A.)
    - examination: Pages with BOTH Q. and A. patterns
    - backpages: After examination (no Q. or no A.)
    """
    
    def __init__(self):
        # Must include the period (.) for precision
        self.question_pattern = re.compile(r'\bQ\.', re.IGNORECASE)
        self.answer_pattern = re.compile(r'\bA\.', re.IGNORECASE)
    
    async def classify_document(
        self, 
        pdf_path: str, 
        document_id: str,
        verbose: bool = True
    ) -> Dict:
        """
        Classify each page of the PDF.
        
        Args:
            pdf_path: Path to PDF file
            document_id: Document UUID
            verbose: If True, create detailed log file
            
        Returns:
            Dict with keys:
                - total_pages: int
                - classifications: List[Dict] (one per page)
                - examination_first_page: int or None
                - examination_last_page: int or None
                - frontpages_count: int
                - examination_count: int
                - backpages_count: int
                - log_file: str or None (if verbose)
        """
        try:
            logger.info(f"Starting page classification for document {document_id[:8]}...")
            
            doc = fitz.open(pdf_path)
            classifications = []
            log_lines = [] if verbose else None
            
            # Pass 1: Check each page for Q. and A. patterns
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                
                # Check for patterns (must include period)
                has_q = bool(self.question_pattern.search(text))
                has_a = bool(self.answer_pattern.search(text))
                
                # Page is examination if BOTH Q. and A. are present
                is_exam = has_q and has_a
                
                classifications.append({
                    'page_number': page_num + 1,  # 1-based
                    'has_question': has_q,
                    'has_answer': has_a,
                    'is_examination': is_exam
                })
                
                if verbose:
                    log_lines.append(
                        f"Page {page_num + 1}: Q={'Yes' if has_q else 'No'}, "
                        f"A={'Yes' if has_a else 'No'}"
                    )
            
            doc.close()
            
            # Pass 2: Determine frontpages/examination/backpages boundaries
            first_exam_idx = next(
                (i for i, c in enumerate(classifications) if c['is_examination']), 
                None
            )
            last_exam_idx = next(
                (i for i in range(len(classifications) - 1, -1, -1) 
                 if classifications[i]['is_examination']), 
                None
            )
            
            # Assign final classifications
            for i, c in enumerate(classifications):
                if first_exam_idx is None:
                    # No examination found at all
                    c['classification'] = 'frontpages'
                elif i < first_exam_idx:
                    c['classification'] = 'frontpages'
                elif i <= last_exam_idx:
                    # Within examination bounds
                    c['classification'] = 'examination'
                else:
                    c['classification'] = 'backpages'
            
            # Calculate counts
            frontpages_count = sum(1 for c in classifications if c['classification'] == 'frontpages')
            examination_count = sum(1 for c in classifications if c['classification'] == 'examination')
            backpages_count = sum(1 for c in classifications if c['classification'] == 'backpages')
            
            # Save verbose log if requested
            log_file = None
            if verbose and log_lines:
                log_file = f"/tmp/page_classification_{document_id[:8]}.log"
                try:
                    with open(log_file, 'w') as f:
                        f.write("Page Classification Log\n")
                        f.write(f"Document ID: {document_id}\n")
                        f.write(f"Total Pages: {len(classifications)}\n")
                        f.write("=" * 60 + "\n\n")
                        
                        # Write per-page details
                        for line in log_lines:
                            f.write(line + "\n")
                        
                        # Write summary
                        f.write("\n" + "=" * 60 + "\n")
                        f.write("Summary:\n")
                        if first_exam_idx is not None:
                            f.write(f"- Frontpages: {frontpages_count} pages (1-{first_exam_idx})\n")
                            f.write(f"- Examination: {examination_count} pages ({first_exam_idx + 1}-{last_exam_idx + 1})\n")
                            f.write(f"- Backpages: {backpages_count} pages ({last_exam_idx + 2}-{len(classifications)})\n")
                        else:
                            f.write(f"- No examination section found (all {len(classifications)} pages classified as frontpages)\n")
                    
                    logger.info(f"Verbose log saved to {log_file}")
                except Exception as e:
                    logger.error(f"Failed to write verbose log: {e}")
                    log_file = None
            
            result = {
                'total_pages': len(classifications),
                'classifications': classifications,
                'examination_first_page': first_exam_idx + 1 if first_exam_idx is not None else None,
                'examination_last_page': last_exam_idx + 1 if last_exam_idx is not None else None,
                'frontpages_count': frontpages_count,
                'examination_count': examination_count,
                'backpages_count': backpages_count,
                'log_file': log_file
            }
            
            logger.info(
                f"Classification complete: {frontpages_count} frontpages, "
                f"{examination_count} examination, {backpages_count} backpages"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to classify document: {e}", exc_info=True)
            raise
    
    async def store_classifications(self, document_id: str, classification_result: Dict):
        """
        Store page classifications in database.
        
        Args:
            document_id: Document UUID
            classification_result: Result from classify_document()
        """
        try:
            classifications = classification_result['classifications']
            
            # Prepare data for batch insert
            records = [
                (
                    document_id,
                    c['page_number'],
                    c['classification'],
                    c['has_question'],
                    c['has_answer']
                )
                for c in classifications
            ]
            
            # Batch insert with conflict resolution
            await db_service.executemany(
                """
                INSERT INTO page_classifications 
                    (document_id, page_number, classification, has_question, has_answer)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (document_id, page_number) DO UPDATE SET
                    classification = EXCLUDED.classification,
                    has_question = EXCLUDED.has_question,
                    has_answer = EXCLUDED.has_answer
                """,
                records
            )
            
            logger.info(f"Stored {len(records)} page classifications for document {document_id[:8]}")
            
        except Exception as e:
            logger.error(f"Failed to store classifications: {e}", exc_info=True)
            raise


# Singleton instance
page_classifier = PageClassifier()

