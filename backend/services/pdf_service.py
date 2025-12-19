"""PDF extraction service using PyMuPDF for 10x speed improvement."""
import asyncio
import logging
import re
from typing import List, Dict, Optional, AsyncGenerator, Tuple
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PDFService:
    """High-performance PDF extraction using PyMuPDF."""
    
    def __init__(self):
        self.lines_per_page = 25  # Legal transcript standard
        
        # Page number patterns to look for in headers/footers
        # Ordered by specificity - more specific patterns first
        self.page_number_patterns = [
            # "Page: X" or "PAGE: X" or "page: X" (with colon)
            re.compile(r'\bPage\s*:\s*(\d+)\b', re.IGNORECASE),
            # "Page X" or "PAGE X" or "page X"
            re.compile(r'\bPage\s+(\d+)\b', re.IGNORECASE),
            # "Page X of Y"
            re.compile(r'\bPage\s+(\d+)\s+of\s+\d+\b', re.IGNORECASE),
            # "- X -" centered page numbers
            re.compile(r'[-–—]\s*(\d+)\s*[-–—]'),
            # "X of Y"
            re.compile(r'\b(\d+)\s+of\s+\d+\b', re.IGNORECASE),
            # Standalone number (must be careful - only use if it's the primary content)
            re.compile(r'^[\s\-–—]*(\d+)[\s\-–—]*$'),
        ]
    
    async def detect_printed_page_number(
        self, 
        text_items: List[Dict], 
        page_height: float,
        page_width: float
    ) -> Optional[int]:
        """
        Detect the printed page number from header or footer of a transcript page.
        
        Legal transcripts have page numbers in headers or footers. This function:
        1. Looks at the top 12% (header) and bottom 12% (footer) of the page
        2. Excludes the left margin (where line numbers are located)
        3. Prioritizes the right side of footer/header for page numbers
        4. Searches for common page number patterns
        5. Returns the detected page number or None if not found
        
        Args:
            text_items: List of text items with x, y, text properties
            page_height: Height of the page in points
            page_width: Width of the page in points
            
        Returns:
            Detected page number as int, or None if not detected
        """
        # Define header and footer regions (12% of page height each)
        header_threshold = page_height * 0.12
        footer_threshold = page_height * 0.88
        
        # Exclude left margin where line numbers are (same threshold as line number extraction)
        left_margin_threshold = page_width * 0.15
        
        # Collect text from header and footer regions, excluding left margin
        header_items = []
        footer_items = []
        
        for item in text_items:
            y = item.get("y", 0)
            x = item.get("x", 0)
            text = item.get("text", "").strip()
            
            if not text:
                continue
            
            # Skip items in the left margin - those are line numbers, not page numbers
            if x < left_margin_threshold:
                continue
                
            if y < header_threshold:
                header_items.append(item)
            elif y > footer_threshold:
                footer_items.append(item)
        
        # Try to find page number in footer first (most common), then header
        # Also prioritize right side of footer/header
        for region_name, items in [("footer", footer_items), ("header", header_items)]:
            if not items:
                continue
                
            # Sort items by x position (right to left) and y position to combine into lines
            # Prioritize right side items first
            items_sorted = sorted(items, key=lambda x: (x.get("y", 0), -x.get("x", 0)))
            
            # Combine items on same line
            lines = []
            current_line = []
            current_y = None
            
            for item in items_sorted:
                item_y = item.get("y", 0)
                if current_y is None or abs(item_y - current_y) < 5:
                    current_line.append(item.get("text", ""))
                    current_y = item_y if current_y is None else current_y
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [item.get("text", "")]
                    current_y = item_y
            
            if current_line:
                lines.append(" ".join(current_line))
            
            # Search each line for page number patterns
            # Check rightmost lines first (where page numbers typically are)
            for line in lines:
                page_num = self._extract_page_number_from_text(line)
                if page_num is not None:
                    logger.debug(f"Detected page number {page_num} from {region_name}: '{line}'")
                    return page_num
        
        # No page number found
        return None
    
    def _extract_page_number_from_text(self, text: str) -> Optional[int]:
        """
        Extract a page number from a text string using various patterns.
        
        Returns the page number if found, None otherwise.
        """
        text = text.strip()
        
        if not text:
            return None
        
        # Try each pattern
        for pattern in self.page_number_patterns:
            match = pattern.search(text)
            if match:
                try:
                    page_num = int(match.group(1))
                    # Sanity check - page numbers should be reasonable
                    if 1 <= page_num <= 9999:
                        return page_num
                except (ValueError, IndexError):
                    continue
        
        # Special case: if the text is ONLY a number (possibly with spaces/dashes)
        # This catches simple footer numbers like "15" or " 15 "
        cleaned = re.sub(r'[\s\-–—]', '', text)
        if cleaned.isdigit():
            page_num = int(cleaned)
            if 1 <= page_num <= 9999:
                return page_num
        
        return None
    
    async def detect_all_page_numbers(self, pdf_path: str) -> Dict[int, Optional[int]]:
        """
        Detect printed page numbers for all pages in a PDF.
        
        Returns a mapping of PDF page index (1-based) to printed page number.
        Pages without detected numbers will have None.
        
        This function also validates the detected numbers for consistency:
        - If sequential pages are found, fills in gaps
        - Detects cover sheets (pages before page 1)
        - Handles partial uploads (e.g., pages 10-25, 50-75)
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # First pass: detect page numbers from each page
            raw_detections = {}
            
            for pdf_idx in range(total_pages):
                page = doc[pdf_idx]
                rect = page.rect
                text_dict = page.get_text("dict")
                
                # Extract text items
                text_items = []
                for block in text_dict.get("blocks", []):
                    if block.get("type") == 0:  # Text block
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                text = span.get("text", "").strip()
                                if text:
                                    bbox = span.get("bbox", [0, 0, 0, 0])
                                    text_items.append({
                                        "text": text,
                                        "x": bbox[0],
                                        "y": bbox[1],
                                    })
                
                # Detect printed page number
                detected = await self.detect_printed_page_number(
                    text_items, 
                    rect.height, 
                    rect.width
                )
                
                raw_detections[pdf_idx + 1] = detected
                
                if detected:
                    logger.debug(f"PDF page {pdf_idx + 1} -> Printed page {detected}")
                else:
                    logger.debug(f"PDF page {pdf_idx + 1} -> No page number detected (cover/index page?)")
            
            doc.close()
            
            # Second pass: validate and fill gaps
            validated = self._validate_page_number_sequence(raw_detections)
            
            # Log the mapping for debugging
            logger.info(f"Page number mapping: {validated}")
            
            return validated
            
        except Exception as e:
            logger.error(f"Failed to detect page numbers: {e}", exc_info=True)
            raise
    
    def _validate_page_number_sequence(
        self, 
        detections: Dict[int, Optional[int]]
    ) -> Dict[int, Optional[int]]:
        """
        Validate and fill gaps in detected page numbers.
        
        Legal transcripts should have sequential page numbers.
        This function:
        1. Identifies cover/index pages (None before first numbered page)
        2. Fills in missing numbers if there's a clear sequence
        3. Handles gaps in partial uploads
        """
        if not detections:
            return {}
        
        # Get all detected page numbers with their PDF indices
        detected_pairs = [
            (pdf_idx, printed_num) 
            for pdf_idx, printed_num in detections.items() 
            if printed_num is not None
        ]
        
        if not detected_pairs:
            # No page numbers detected at all - fall back to PDF indices
            logger.warning("No printed page numbers detected - using PDF page indices")
            return {pdf_idx: pdf_idx for pdf_idx in detections.keys()}
        
        # Sort by PDF index
        detected_pairs.sort(key=lambda x: x[0])
        
        # Validate that detected numbers are roughly sequential
        # (allow for some noise in detection)
        validated = dict(detections)  # Start with raw detections
        
        # Try to fill in gaps based on detected sequence
        for i in range(len(detected_pairs) - 1):
            current_pdf_idx, current_printed = detected_pairs[i]
            next_pdf_idx, next_printed = detected_pairs[i + 1]
            
            pdf_gap = next_pdf_idx - current_pdf_idx
            printed_gap = next_printed - current_printed
            
            # If gaps match, we can infer missing page numbers
            if pdf_gap == printed_gap and pdf_gap > 1:
                for j in range(1, pdf_gap):
                    fill_idx = current_pdf_idx + j
                    fill_printed = current_printed + j
                    if validated.get(fill_idx) is None:
                        validated[fill_idx] = fill_printed
                        logger.debug(f"Inferred PDF page {fill_idx} -> Printed page {fill_printed}")
        
        # Handle pages before first detected number (cover sheets)
        first_detected_idx, first_detected_num = detected_pairs[0]
        for pdf_idx in range(1, first_detected_idx):
            if validated.get(pdf_idx) is None:
                # These are likely cover/index pages - mark as 0 or negative
                # to indicate they're not part of the transcript
                validated[pdf_idx] = None
                logger.debug(f"PDF page {pdf_idx} is likely a cover/index page (no number)")
        
        return validated
    
    async def get_pdf_info(self, pdf_path: str) -> Dict:
        """Get basic PDF information quickly."""
        try:
            doc = fitz.open(pdf_path)
            info = {
                "total_pages": len(doc),
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", "")
            }
            doc.close()
            return info
        except Exception as e:
            logger.error(f"Failed to get PDF info: {e}")
            raise
    
    async def extract_pages(self, pdf_path: str, first_page: int = 1, last_page: Optional[int] = None) -> List[Dict]:
        """
        Extract text from PDF pages with position data.
        Much faster than pdfjs - uses direct PDF parsing.
        
        IMPORTANT: This method now detects printed page numbers from headers/footers
        to correctly map PDF pages to transcript pages.
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            if last_page is None or last_page > total_pages:
                last_page = total_pages
            
            # Detect printed page numbers for all pages upfront
            page_number_map = await self.detect_all_page_numbers(pdf_path)
            
            pages = []
            
            for page_num in range(first_page - 1, last_page):
                page = doc[page_num]
                pdf_idx = page_num + 1  # 1-based PDF index
                
                # Get the detected printed page number
                printed_page = page_number_map.get(pdf_idx)
                
                page_data = await self._extract_page(page, pdf_idx, printed_page)
                pages.append(page_data)
            
            doc.close()
            
            logger.info(f"Extracted {len(pages)} pages from PDF")
            return pages
            
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}", exc_info=True)
            raise
    
    async def extract_pages_streaming(
        self,
        pdf_path: str,
        first_page: int = 1,
        last_page: Optional[int] = None,
        batch_size: int = 5
    ) -> AsyncGenerator[List[Dict], None]:
        """
        Stream PDF pages in batches for pipeline parallelization.
        
        This allows AI processing to start before all pages are extracted,
        resulting in 15-25% faster overall processing by overlapping I/O and computation.
        
        IMPORTANT: This method now detects printed page numbers from headers/footers
        to correctly map PDF pages to transcript pages. This handles:
        - Cover sheets (unnumbered pages at the beginning)
        - Partial uploads (e.g., pages 10-25, 50-75)
        - Index pages without numbers
        
        Args:
            pdf_path: Path to PDF file
            first_page: Starting page number (1-indexed) - refers to PDF index
            last_page: Ending page number (inclusive) - refers to PDF index
            batch_size: Number of pages to yield at once
        
        Yields:
            Batches of page dictionaries with extracted data
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            if last_page is None or last_page > total_pages:
                last_page = total_pages
            
            # STEP 1: Detect printed page numbers for all pages upfront
            # This is important for accurate gap-filling and validation
            logger.info(f"Detecting printed page numbers for {total_pages} pages...")
            page_number_map = await self.detect_all_page_numbers(pdf_path)
            
            # Log the mapping summary
            detected_count = sum(1 for v in page_number_map.values() if v is not None)
            logger.info(f"Detected printed page numbers for {detected_count}/{total_pages} pages")
            
            current_batch = []
            
            for page_num in range(first_page - 1, last_page):
                page = doc[page_num]
                pdf_idx = page_num + 1  # 1-based PDF index
                
                # Get the detected printed page number
                printed_page = page_number_map.get(pdf_idx)
                
                # Extract page with the correct printed page number
                page_data = await self._extract_page(page, pdf_idx, printed_page)
                current_batch.append(page_data)
                
                # Yield batch when full
                if len(current_batch) >= batch_size:
                    logger.debug(f"Streaming batch of {len(current_batch)} pages")
                    yield current_batch
                    current_batch = []
                    
                    # Allow other tasks to run
                    await asyncio.sleep(0)
            
            # Yield remaining pages
            if current_batch:
                logger.debug(f"Streaming final batch of {len(current_batch)} pages")
                yield current_batch
            
            doc.close()
            logger.info(f"Streamed {last_page - first_page + 1} pages from PDF")
            
        except Exception as e:
            logger.error(f"PDF streaming failed: {e}", exc_info=True)
            raise
    
    async def _extract_page(
        self, 
        page: fitz.Page, 
        pdf_page_index: int,
        printed_page_number: Optional[int] = None
    ) -> Dict:
        """
        Extract text and structure from a single page.
        
        Args:
            page: PyMuPDF page object
            pdf_page_index: 1-based index in the PDF file
            printed_page_number: The actual printed page number from the transcript.
                                 If None, will attempt to detect it.
        """
        # Get page dimensions
        rect = page.rect
        width = rect.width
        height = rect.height
        
        # Extract text with position data (dict mode is fastest)
        text_dict = page.get_text("dict")
        
        # Parse text blocks
        text_items = []
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            bbox = span.get("bbox", [0, 0, 0, 0])
                            text_items.append({
                                "text": text,
                                "x": bbox[0],
                                "y": bbox[1],
                                "width": bbox[2] - bbox[0],
                                "height": bbox[3] - bbox[1],
                                "font": span.get("font", ""),
                                "size": span.get("size", 12)
                            })
        
        # Detect printed page number if not provided
        if printed_page_number is None:
            detected = await self.detect_printed_page_number(text_items, height, width)
            printed_page_number = detected if detected else pdf_page_index
            
            if detected:
                logger.debug(f"PDF page {pdf_page_index} -> Printed page {detected}")
            else:
                logger.debug(f"PDF page {pdf_page_index} -> No printed number detected, using PDF index")
        
        # Extract line numbers from left margin
        line_numbers = await self._extract_line_numbers(text_items, width)
        
        # Parse Q&A pairs using the PRINTED page number, but also pass PDF index for rendering
        qa_pairs = await self._parse_qa_pairs(
            text_items, 
            printed_page_number, 
            width, 
            height, 
            line_numbers,
            pdf_page_index=pdf_page_index
        )
        
        return {
            "pdf_page_index": pdf_page_index,      # The index in the PDF file (1-based)
            "page_number": printed_page_number,    # The printed transcript page number
            "width": width,
            "height": height,
            "text_items": text_items,
            "line_numbers": line_numbers,
            "qa_pairs": qa_pairs
        }
    
    async def _extract_line_numbers(self, text_items: List[Dict], page_width: float) -> List[Dict]:
        """Extract line numbers from left margin."""
        left_margin_threshold = page_width * 0.15
        line_numbers = []
        
        for item in text_items:
            if item["x"] < left_margin_threshold:
                text = item["text"].strip()
                # Match numbers 1-25 (legal transcript line numbers)
                if re.match(r'^[1-9]$|^1[0-9]$|^2[0-5]$', text):
                    line_numbers.append({
                        "number": int(text),
                        "x": item["x"],
                        "y": item["y"],
                        "height": item["height"]
                    })
        
        # Sort by Y position
        line_numbers.sort(key=lambda ln: ln["y"])
        
        return line_numbers
    
    async def _parse_qa_pairs(
        self,
        text_items: List[Dict],
        page_number: int,
        page_width: float,
        page_height: float,
        line_numbers: List[Dict],
        pdf_page_index: Optional[int] = None
    ) -> List[Dict]:
        """Parse Q&A pairs from text items using multiple patterns.
        
        Args:
            text_items: List of text items with position data
            page_number: The PRINTED transcript page number (for display/citation)
            page_width: Page width in points
            page_height: Page height in points
            line_numbers: List of detected line numbers
            pdf_page_index: The 1-based index in the PDF file (for rendering)
        
        Supports various deposition transcript formats:
        - Q. / A. format
        - Q: / A: format  
        - QUESTION: / ANSWER: format
        - BY MR./MS. NAME: format
        - THE WITNESS: for answers
        - Handles middle dots like "· · ·Q.· text"
        """
        # Filter out line numbers from left margin
        left_margin = page_width * 0.15
        content_items = [
            item for item in text_items
            if item["x"] >= left_margin
        ]
        
        # Combine into lines based on Y position
        lines = []
        current_line = []
        current_y = None
        y_threshold = 3  # Pixels
        
        for item in sorted(content_items, key=lambda x: (x["y"], x["x"])):
            if current_y is None or abs(item["y"] - current_y) <= y_threshold:
                current_line.append(item)
                current_y = item["y"] if current_y is None else current_y
            else:
                if current_line:
                    line_text = " ".join(i["text"] for i in current_line)
                    lines.append({
                        "text": line_text,
                        "y": current_y,
                        "items": current_line
                    })
                current_line = [item]
                current_y = item["y"]
        
        if current_line:
            line_text = " ".join(i["text"] for i in current_line)
            lines.append({
                "text": line_text,
                "y": current_y,
                "items": current_line
            })
        
        # Question patterns - expanded to match working implementation
        question_patterns = [
            re.compile(r'^[·\s]*Q\.[·\s]*', re.IGNORECASE),  # Q. with optional middle dots
            re.compile(r'^\s*Q\.\s*', re.IGNORECASE),        # Standard Q.
            re.compile(r'^\s*Q:\s*', re.IGNORECASE),         # Q: format
            re.compile(r'^Q\s+[A-Z]', re.IGNORECASE),        # Q followed by space and capital
            re.compile(r'^\s*QUESTION[:\s]+', re.IGNORECASE), # QUESTION: format
            re.compile(r'^BY\s+M[RS]\.\s+\w+:', re.IGNORECASE), # BY MR./MS. NAME: format
        ]
        
        # Answer patterns - expanded to match working implementation  
        answer_patterns = [
            re.compile(r'^[·\s]*A\.[·\s]*', re.IGNORECASE),  # A. with optional middle dots
            re.compile(r'^\s*A\.\s*', re.IGNORECASE),        # Standard A.
            re.compile(r'^\s*A:\s*', re.IGNORECASE),         # A: format
            re.compile(r'^A\s+[A-Z]', re.IGNORECASE),        # A followed by space and capital
            re.compile(r'^\s*ANSWER[:\s]+', re.IGNORECASE),  # ANSWER: format
            re.compile(r'^[·\s]*THE\s+WITNESS:[·\s]*', re.IGNORECASE), # THE WITNESS: format
        ]
        
        # Colloquy patterns (not Q&A, but attorney/court speaking)
        colloquy_patterns = [
            re.compile(r'^M[RS]\.\s+\w+:', re.IGNORECASE),   # MR./MS. NAME:
            re.compile(r'^THE\s+(REPORTER|COURT):', re.IGNORECASE), # THE REPORTER/COURT:
            re.compile(r'^\(.*\)$'),                          # Parenthetical notes
        ]
        
        # End markers (stop parsing here)
        end_patterns = [
            re.compile(r'^CERTIFICATE OF REPORTER', re.IGNORECASE),
            re.compile(r'^PENALTY OF PERJURY', re.IGNORECASE),
            re.compile(r'^CHANGES AND SIGNATURE', re.IGNORECASE),
        ]
        
        def is_question(text: str) -> bool:
            return any(p.match(text) for p in question_patterns)
        
        def is_answer(text: str) -> bool:
            return any(p.match(text) for p in answer_patterns)
        
        def is_colloquy(text: str) -> bool:
            # Colloquy but NOT "THE WITNESS:" which is an answer
            if re.match(r'^[·\s]*THE\s+WITNESS:', text, re.IGNORECASE):
                return False
            return any(p.match(text) for p in colloquy_patterns)
        
        def is_end_marker(text: str) -> bool:
            return any(p.match(text) for p in end_patterns)
        
        def clean_qa_text(text: str) -> str:
            """Remove Q/A prefixes and clean up middle dots."""
            cleaned = text
            # Remove Q/A prefixes with various formats
            cleaned = re.sub(r'^[·\s]*Q\.[·\s]*', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'^[·\s]*A\.[·\s]*', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'^\s*Q:\s*', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'^\s*A:\s*', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'^Q\s+', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'^A\s+', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'^\s*QUESTION[:\s]*', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'^\s*ANSWER[:\s]*', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'^[·\s]*THE\s+WITNESS:[·\s]*', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'^BY\s+M[RS]\.\s+\w+:\s*', '', cleaned, flags=re.IGNORECASE)
            # Clean middle dots
            cleaned = cleaned.replace('·', ' ')
            cleaned = re.sub(r'\s+', ' ', cleaned)
            return cleaned.strip()
        
        # Find Q&A pairs using state machine
        qa_pairs = []
        current_question = None
        current_question_y = None
        current_answer = []
        state = 'searching'  # searching, in_question, in_answer
        
        for i, line in enumerate(lines):
            text = line["text"]
            trimmed = text.strip()
            
            # Skip empty lines
            if not trimmed:
                continue
            
            # Use pdf_page_index if provided, otherwise default to page_number
            _pdf_idx = pdf_page_index if pdf_page_index is not None else page_number
            
            # Check for end markers
            if is_end_marker(trimmed):
                # Save current Q&A if complete
                if current_question and current_answer:
                    qa_pairs.append({
                        "question": current_question,
                        "answer": " ".join(current_answer),
                        "page": page_number,
                        "pdf_page_index": _pdf_idx,
                        "line": self._find_closest_line_number(current_question_y, line_numbers) if current_question_y else 1
                    })
                break
            
            # Check if this is a question (only if we're not already in a question, or if it's a new question)
            is_q = is_question(trimmed) or is_question(text)
            is_a = is_answer(trimmed) or is_answer(text)
            is_c = is_colloquy(trimmed)
            
            if is_q:
                # Save previous Q&A if complete
                if current_question and current_answer:
                    qa_pairs.append({
                        "question": current_question,
                        "answer": " ".join(current_answer),
                        "page": page_number,
                        "pdf_page_index": _pdf_idx,
                        "line": self._find_closest_line_number(current_question_y, line_numbers) if current_question_y else 1
                    })
                
                # Start new question (even if we were in a question state - this is a new Q)
                current_question = clean_qa_text(text)
                current_question_y = line["y"]
                current_answer = []
                state = 'in_question'
                
            elif is_a:
                if current_question:
                    # Start or continue answer
                    answer_text = clean_qa_text(text)
                    if state == 'in_answer':
                        # Another answer line (like another THE WITNESS:)
                        current_answer.append(answer_text)
                    else:
                        # Transition from question to answer
                        current_answer = [answer_text]
                    state = 'in_answer'
                # If no current question, ignore standalone answers (might be from previous page)
                    
            elif is_c:
                # Colloquy (objections, attorney statements, etc.) doesn't interrupt
                # the current question or answer - it's just skipped
                # The state remains unchanged so continuation continues on next line
                pass
                
            else:
                # Continuation of current element
                # This handles multi-line questions and answers
                if state == 'in_question' and current_question:
                    # Continue the question across multiple lines
                    # Only append if we have a question started
                    current_question += ' ' + trimmed
                elif state == 'in_answer' and current_answer:
                    # Continue the answer across multiple lines
                    current_answer.append(trimmed)
                # If state is 'searching', ignore text that doesn't match any pattern
                # (might be headers, footers, or other non-Q&A content)
        
        # Save last Q&A pair
        if current_question and current_answer:
            qa_pairs.append({
                "question": current_question,
                "answer": " ".join(current_answer),
                "page": page_number,
                "pdf_page_index": _pdf_idx,
                "line": self._find_closest_line_number(current_question_y, line_numbers) if current_question_y else 1
            })
        
        # Debug logging for pages with Q&A pairs
        if len(qa_pairs) > 0:
            logger.info(f"Page {page_number}: {len(lines)} lines, {len(qa_pairs)} Q&A pairs found")
            # Log first Q&A pair details for debugging
            if qa_pairs:
                first_qa = qa_pairs[0]
                q_preview = first_qa["question"][:100] + "..." if len(first_qa["question"]) > 100 else first_qa["question"]
                a_preview = first_qa["answer"][:100] + "..." if len(first_qa["answer"]) > 100 else first_qa["answer"]
                logger.debug(f"Page {page_number} first Q&A: line={first_qa['line']}, Q='{q_preview}', A='{a_preview}'")
        
        # Debug logging for page 7 specifically (where the issue was reported)
        if page_number == 7 and len(lines) > 0:
            logger.debug(f"Page 7 debug: {len(lines)} lines processed")
            # Show lines around where Q&A should be (lines 10-22)
            sample_lines = []
            for i, l in enumerate(lines[:25]):  # First 25 lines
                line_num = self._find_closest_line_number(l["y"], line_numbers)
                if 10 <= line_num <= 22:
                    sample_lines.append(f"Line {line_num}: '{l['text'][:60]}'")
            if sample_lines:
                logger.debug(f"Page 7 lines 10-22: {sample_lines}")
        
        return qa_pairs
    
    def _find_closest_line_number(self, y_position: float, line_numbers: List[Dict]) -> int:
        """Find the closest line number for a given Y position."""
        if not line_numbers:
            return 1
        
        closest = min(line_numbers, key=lambda ln: abs(ln["y"] - y_position))
        return closest["number"]
    
    async def render_page_as_image(
        self, 
        pdf_path: str, 
        page_num: int, 
        scale: float = 2.0
    ) -> Dict:
        """Render PDF page as PNG image for reading mode display.
        
        Args:
            pdf_path: Path to PDF file
            page_num: 1-indexed page number to render
            scale: Render scale (2.0 = 2x resolution for retina displays)
        
        Returns:
            Dict with 'image' (bytes), 'width', 'height', 'page_number'
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            if page_num < 1 or page_num > total_pages:
                raise ValueError(f"Page {page_num} out of range (1-{total_pages})")
            
            page = doc[page_num - 1]
            
            # Render at specified scale
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert to PNG bytes
            png_bytes = pix.tobytes("png")
            
            result = {
                "image": png_bytes,
                "width": pix.width,
                "height": pix.height,
                "page_number": page_num,
                "total_pages": total_pages,
                "scale": scale,
                "original_width": page.rect.width,
                "original_height": page.rect.height
            }
            
            doc.close()
            logger.info(f"Rendered page {page_num}/{total_pages} at {scale}x scale ({pix.width}x{pix.height})")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to render page {page_num}: {e}", exc_info=True)
            raise
    
    async def get_page_text_with_positions(
        self, 
        pdf_path: str, 
        page_num: int
    ) -> Dict:
        """Get text with line positions for a specific page.
        
        Used for reading mode to map line numbers to pixel coordinates.
        """
        try:
            doc = fitz.open(pdf_path)
            
            if page_num < 1 or page_num > len(doc):
                raise ValueError(f"Page {page_num} out of range")
            
            page = doc[page_num - 1]
            page_data = await self._extract_page(page, page_num)
            
            doc.close()
            
            return page_data
            
        except Exception as e:
            logger.error(f"Failed to get page text: {e}", exc_info=True)
            raise


# Global PDF service instance
pdf_service = PDFService()

