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
            previous_incomplete_state = None
            
            for page_num in range(first_page - 1, last_page):
                page = doc[page_num]
                pdf_idx = page_num + 1  # 1-based PDF index
                
                # Get the detected printed page number
                printed_page = page_number_map.get(pdf_idx)
                
                # Extract page with state continuation
                page_data = await self._extract_page_with_state(
                    page, pdf_idx, printed_page, previous_incomplete_state
                )
                pages.append(page_data)
                
                # Update state for next page
                previous_incomplete_state = page_data.get("incomplete_state")
            
            # Merge any remaining interim Q&A pairs
            pages = self._merge_interim_qa_pairs(pages)
            
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
            previous_incomplete_state = None
            
            for page_num in range(first_page - 1, last_page):
                page = doc[page_num]
                pdf_idx = page_num + 1  # 1-based PDF index
                
                # Get the detected printed page number
                printed_page = page_number_map.get(pdf_idx)
                
                # Extract page with state continuation
                page_data = await self._extract_page_with_state(
                    page, pdf_idx, printed_page, previous_incomplete_state
                )
                current_batch.append(page_data)
                
                # Update state for next page
                previous_incomplete_state = page_data.get("incomplete_state")
                
                # Yield batch when full
                if len(current_batch) >= batch_size:
                    # Merge interim pairs within batch
                    current_batch = self._merge_interim_qa_pairs(current_batch)
                    logger.debug(f"Streaming batch of {len(current_batch)} pages")
                    yield current_batch
                    current_batch = []
                    
                    # Allow other tasks to run
                    await asyncio.sleep(0)
            
            # Yield remaining pages
            if current_batch:
                # Merge interim pairs in final batch
                current_batch = self._merge_interim_qa_pairs(current_batch)
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
        # Note: previous_incomplete_state will be handled at the batch level
        qa_pairs, incomplete_state = await self._parse_qa_pairs(
            text_items, 
            printed_page_number, 
            width, 
            height, 
            line_numbers,
            pdf_page_index=pdf_page_index,
            previous_incomplete_state=None  # Will be set at batch processing level
        )
        
        return {
            "pdf_page_index": pdf_page_index,      # The index in the PDF file (1-based)
            "page_number": printed_page_number,    # The printed transcript page number
            "width": width,
            "height": height,
            "text_items": text_items,
            "line_numbers": line_numbers,
            "qa_pairs": qa_pairs,
            "incomplete_state": incomplete_state
        }
    
    async def _extract_page_with_state(
        self,
        page: fitz.Page,
        pdf_page_index: int,
        printed_page_number: Optional[int],
        previous_incomplete_state: Optional[Dict]
    ) -> Dict:
        """Extract page with Q&A state continuation from previous page."""
        # Get page dimensions
        rect = page.rect
        width = rect.width
        height = rect.height
        
        # Extract text with position data
        text_dict = page.get_text("dict")
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
        
        # Extract line numbers
        line_numbers = await self._extract_line_numbers(text_items, width)
        
        # Parse Q&A pairs with state continuation
        qa_pairs, incomplete_state = await self._parse_qa_pairs(
            text_items,
            printed_page_number,
            width,
            height,
            line_numbers,
            pdf_page_index=pdf_page_index,
            previous_incomplete_state=previous_incomplete_state
        )
        
        return {
            "pdf_page_index": pdf_page_index,
            "page_number": printed_page_number,
            "width": width,
            "height": height,
            "text_items": text_items,
            "line_numbers": line_numbers,
            "qa_pairs": qa_pairs,
            "incomplete_state": incomplete_state
        }
    
    def _merge_interim_qa_pairs(self, pages: List[Dict]) -> List[Dict]:
        """
        Merge interim Q&A pairs that span across pages.
        
        This ensures cross-page Q&A pairs are properly combined into final pairs.
        Handles cases where:
        - Question starts on one page, answer on next page
        - Question spans multiple pages
        - Answer spans multiple pages
        """
        all_qa_pairs = []
        interim_pairs = []
        
        for page in pages:
            qa_pairs = page.get("qa_pairs", [])
            for qa in qa_pairs:
                if qa.get("is_final", True):
                    # Final pair - check if it should merge with previous interim
                    if interim_pairs:
                        # Try to merge with last interim pair
                        last_interim = interim_pairs[-1]
                        last_page = last_interim.get("page")
                        last_end_page = last_interim.get("answer_end_page", last_page)
                        current_page = qa.get("page")
                        
                        # Merge if:
                        # 1. Sequential pages (current page is next after last end page)
                        # 2. Same page (continuation within page)
                        # 3. Last interim has incomplete answer (empty or just question)
                        should_merge = (
                            current_page == last_end_page + 1 or
                            current_page == last_page or
                            (not last_interim.get("answer") or last_interim.get("answer", "").strip() == "")
                        )
                        
                        if should_merge:
                            # Merge: combine question and answer
                            # If last interim has no answer, it's likely a question continuation
                            last_answer = last_interim.get("answer", "").strip()
                            if not last_answer:
                                # Last was incomplete question - merge questions and use current answer
                                merged_qa = {
                                    **last_interim,
                                    "question": last_interim.get("question", "") + " " + qa.get("question", ""),
                                    "answer": qa.get("answer", ""),
                                    "answer_end_page": qa.get("answer_end_page", qa.get("page")),
                                    "answer_end_line": qa.get("answer_end_line", qa.get("line")),
                                    "is_final": True
                                }
                            else:
                                # Both have content - combine both
                                merged_qa = {
                                    **last_interim,
                                    "question": last_interim.get("question", "") + " " + qa.get("question", ""),
                                    "answer": last_interim.get("answer", "") + " " + qa.get("answer", ""),
                                    "answer_end_page": qa.get("answer_end_page", qa.get("page")),
                                    "answer_end_line": qa.get("answer_end_line", qa.get("line")),
                                    "is_final": True
                                }
                            interim_pairs.pop()
                            all_qa_pairs.append(merged_qa)
                        else:
                            # Can't merge - save interim as final and add new final
                            all_qa_pairs.extend([{**p, "is_final": True} for p in interim_pairs])
                            interim_pairs = []
                            all_qa_pairs.append(qa)
                    else:
                        all_qa_pairs.append(qa)
                else:
                    # Interim pair - collect for potential merging
                    interim_pairs.append(qa)
        
        # Convert any remaining interim pairs to final
        if interim_pairs:
            all_qa_pairs.extend([{**p, "is_final": True} for p in interim_pairs])
        
        # Update pages with merged Q&A pairs
        # Distribute merged pairs back to pages based on their start page
        page_qa_map = {}
        for qa in all_qa_pairs:
            page_num = qa.get("page")
            if page_num not in page_qa_map:
                page_qa_map[page_num] = []
            page_qa_map[page_num].append(qa)
        
        for page in pages:
            page_num = page.get("page_number")
            page["qa_pairs"] = page_qa_map.get(page_num, [])
        
        return pages
    
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
        pdf_page_index: Optional[int] = None,
        previous_incomplete_state: Optional[Dict] = None
    ) -> Tuple[List[Dict], Dict]:
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
        # CRITICAL: Only save Q&A pairs once when complete (question + answer)
        # Do NOT save during processing - only save when:
        # 1. A new question starts (save previous complete Q&A)
        # 2. End marker encountered (save current complete Q&A)
        # 3. End of page (save current complete Q&A as interim if incomplete)
        
        # Continue from previous page's incomplete state if provided
        original_qa_page = page_number  # Track original page for Q&A that spans pages
        original_qa_line = None
        if previous_incomplete_state:
            current_question = previous_incomplete_state.get("current_question")
            current_question_y = previous_incomplete_state.get("current_question_y")
            current_answer = previous_incomplete_state.get("current_answer", [])
            current_answer_end_line = previous_incomplete_state.get("current_answer_end_line")
            current_answer_end_y = previous_incomplete_state.get("current_answer_end_y")
            state = previous_incomplete_state.get("state", "searching")
            # Preserve original page and line from where Q&A started
            original_qa_page = previous_incomplete_state.get("page_number", page_number)
            if current_question_y:
                # Try to get original line number from previous state if available
                original_qa_line = previous_incomplete_state.get("original_qa_line")
            logger.debug(f"Continuing Q&A from page {original_qa_page} to page {page_number}")
        else:
            current_question = None
            current_question_y = None
            current_answer = []
            current_answer_end_line = None
            current_answer_end_y = None
            state = 'searching'
        
        qa_pairs = []
        seen_qa_keys = set()  # Track saved Q&A pairs to prevent duplicates
        
        def save_current_qa_if_complete(is_final: bool = True, allow_incomplete: bool = False):
            """Helper to save current Q&A pair.
            
            By default, only saves complete Q&A pairs (question + answer).
            If allow_incomplete=True, also saves incomplete pairs (question without answer).
            
            Args:
                is_final: True if this is a final Q&A pair (complete), False if interim
                allow_incomplete: If True, save even if incomplete (e.g., question without answer)
            """
            nonlocal qa_pairs, seen_qa_keys
            
            # Check if we have something to save
            has_question = current_question is not None
            has_answer = current_answer and len(current_answer) > 0
            
            if not (has_question or has_answer):
                return  # Nothing to save
            
            # Only save complete pairs unless allow_incomplete is True
            if not (has_question and has_answer) and not allow_incomplete:
                return
            
            if has_question and has_answer:
                # Create unique key to prevent duplicates
                qa_key = (
                    current_question.strip(),
                    " ".join(current_answer).strip(),
                    page_number,
                    self._find_closest_line_number(current_question_y, line_numbers) if current_question_y else 1
                )
                
                # Only save if we haven't seen this exact Q&A pair before
                if qa_key not in seen_qa_keys:
                    seen_qa_keys.add(qa_key)
                    
                    # Calculate answer end line
                    answer_end_line_num = None
                    if current_answer_end_line is not None:
                        answer_end_line_num = current_answer_end_line
                    elif current_answer_end_y is not None:
                        answer_end_line_num = self._find_closest_line_number(current_answer_end_y, line_numbers)
                    
                    # If answer end line not found, use question start line as fallback
                    question_start_line = self._find_closest_line_number(current_question_y, line_numbers) if current_question_y else 1
                    if answer_end_line_num is None:
                        answer_end_line_num = question_start_line
                    
                    # Use original page/line if continuing from previous page
                    qa_start_page = original_qa_page if previous_incomplete_state else page_number
                    qa_start_line = original_qa_line if (original_qa_line and previous_incomplete_state) else question_start_line
                    
                    qa_pairs.append({
                        "question": current_question,
                        "answer": " ".join(current_answer),
                        "page": qa_start_page,  # Use original start page
                        "pdf_page_index": _pdf_idx,
                        "line": qa_start_line,  # Use original start line
                        "answer_end_page": page_number,  # Answer ends on current page
                        "answer_end_line": answer_end_line_num,
                        "is_final": is_final
                    })
                else:
                    logger.warning(f"Skipping duplicate Q&A pair at page {page_number}, line {self._find_closest_line_number(current_question_y, line_numbers) if current_question_y else 1}")
            elif allow_incomplete and has_question:
                # Save incomplete Q&A pair (question without answer)
                question_start_line = self._find_closest_line_number(current_question_y, line_numbers) if current_question_y else 1
                answer_end_line_num = current_answer_end_line if current_answer_end_line else question_start_line
                
                # Use original page/line if continuing from previous page
                qa_start_page = original_qa_page if previous_incomplete_state else page_number
                qa_start_line = original_qa_line if (original_qa_line and previous_incomplete_state) else question_start_line
                
                qa_pairs.append({
                    "question": current_question,
                    "answer": "",  # Empty answer for incomplete pair
                    "page": qa_start_page,  # Use original start page
                    "pdf_page_index": _pdf_idx,
                    "line": qa_start_line,  # Use original start line
                    "answer_end_page": page_number,  # Question ends on current page
                    "answer_end_line": answer_end_line_num,
                    "is_final": False  # Always interim if incomplete
                })
        
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
                save_current_qa_if_complete()
                break
            
            # Check if this line starts a new question (question markers only match at start)
            line_is_question = is_question(trimmed)
            # Check if this line starts a new answer (answer markers only match at start)
            line_is_answer = is_answer(trimmed)
            
            # Get current line number for tracking
            current_line_num = self._find_closest_line_number(line["y"], line_numbers)
            
            if line_is_question:
                # Save previous Q&A before starting new question
                # If complete, save as final; if incomplete, save as interim
                if current_question and current_answer:
                    # Complete Q&A - save as final
                    save_current_qa_if_complete(is_final=True)
                elif current_question:
                    # Incomplete Q&A (question without answer) - save as interim
                    save_current_qa_if_complete(is_final=False, allow_incomplete=True)
                
                # Clear and start new question
                current_question = clean_qa_text(text)
                current_question_y = line["y"]
                current_answer = []
                current_answer_end_line = None
                current_answer_end_y = None
                state = 'in_question'
                # Reset original page tracking for new Q&A
                original_qa_page = page_number
                original_qa_line = self._find_closest_line_number(line["y"], line_numbers)
                
            elif line_is_answer:
                if current_question:
                    # Start or continue answer
                    answer_text = clean_qa_text(text)
                    if state == 'in_answer':
                        # Another answer marker (like another THE WITNESS:)
                        # Append the new answer text - this is continuation, not a new Q&A
                        current_answer.append(answer_text)
                    else:
                        # Transition from question to answer
                        current_answer = [answer_text]
                    state = 'in_answer'
                    # Update answer end tracking
                    current_answer_end_line = current_line_num
                    current_answer_end_y = line["y"]
                else:
                    # Answer without a question - skip it (might be continuation from previous page)
                    pass
                    
            elif is_colloquy(trimmed):
                # Colloquy (objections, attorney statements, etc.) - include it if we're in Q&A
                if state == 'in_question' and current_question:
                    # Colloquy within question - include it as part of question
                    current_question += ' ' + trimmed
                elif state == 'in_answer' and current_answer:
                    # Colloquy within answer - include it as part of answer
                    current_answer.append(trimmed)
                    # Update answer end tracking
                    current_answer_end_line = current_line_num
                    current_answer_end_y = line["y"]
                # Otherwise skip colloquy (not part of any Q&A yet)
                
            else:
                # Continuation of current element (regular text, not a marker)
                # CRITICAL: ALL lines must be included in a Q&A pair - no skipped lines
                if state == 'in_question' and current_question:
                    # Continue question across multiple lines
                    current_question += ' ' + trimmed
                    # Update question end tracking
                    current_answer_end_line = current_line_num
                    current_answer_end_y = line["y"]
                elif state == 'in_answer' and current_answer:
                    # Continue answer across multiple lines
                    current_answer.append(trimmed)
                    # Update answer end tracking
                    current_answer_end_line = current_line_num
                    current_answer_end_y = line["y"]
                elif state == 'searching':
                    # If searching and we hit regular text, it might be:
                    # 1. Continuation from previous page (if we have incomplete state)
                    # 2. Start of content - treat as question continuation or start new Q&A
                    if previous_incomplete_state and current_question:
                        # Continuation from previous page - add to question
                        current_question += ' ' + trimmed
                        state = 'in_question'
                        current_answer_end_line = current_line_num
                        current_answer_end_y = line["y"]
                    elif previous_incomplete_state and current_answer:
                        # Continuation from previous page - add to answer
                        current_answer.append(trimmed)
                        state = 'in_answer'
                        current_answer_end_line = current_line_num
                        current_answer_end_y = line["y"]
                    else:
                        # No previous state - this might be content before first Q/A marker
                        # Start as question to ensure line is included
                        current_question = trimmed
                        current_question_y = line["y"]
                        state = 'in_question'
                        current_answer_end_line = current_line_num
                        current_answer_end_y = line["y"]
        
        # At end of page, check if we have incomplete Q&A pairs
        # If complete (has both question and answer), save as final
        # If incomplete and NOT continuing, save as interim (will be merged with next page)
        # If incomplete and continuing, don't save yet - will continue on next page
        has_complete_qa = current_question is not None and current_answer
        has_incomplete_qa = (current_question is not None) or (current_answer and not current_question)
        is_continuation = previous_incomplete_state is not None
        
        if has_complete_qa:
            # Complete Q&A - save as final (whether continuing or not)
            save_current_qa_if_complete(is_final=True)
        elif has_incomplete_qa and not is_continuation:
            # New incomplete Q&A started on this page - save as interim
            save_current_qa_if_complete(is_final=False)
        # If incomplete and continuing, don't save - will continue on next page
        
        # Return incomplete state for continuation on next page
        incomplete_state = {
            "current_question": current_question,
            "current_question_y": current_question_y,
            "current_answer": current_answer,
            "current_answer_end_line": current_answer_end_line,
            "current_answer_end_y": current_answer_end_y,
            "state": state,
            "page_number": original_qa_page,  # Preserve original start page
            "original_qa_line": original_qa_line,  # Preserve original start line
            "pdf_page_index": _pdf_idx
        }
        
        # Debug logging for first page
        if page_number == 1 and len(lines) > 0:
            logger.info(f"Page {page_number}: {len(lines)} lines, {len(qa_pairs)} Q&A pairs found")
            # Show first few lines to help debug parsing issues
            sample_lines = [l["text"][:80] for l in lines[:10]]
            logger.debug(f"Sample lines from page 1: {sample_lines}")
        
        return qa_pairs, incomplete_state
    
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

