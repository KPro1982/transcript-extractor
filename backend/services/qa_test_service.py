"""Q/A extraction test service for document validation."""
import logging
import re
from typing import Dict, List, Tuple, Optional
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class QATestService:
    """
    Tests Q/A extraction from PDF before processing.
    
    Extracts a sample of Q/A pairs to verify parsing logic
    and generates a detailed diagnostic log file for review.
    """
    
    def __init__(self):
        # Q/A detection patterns (same as main pdf_service)
        self.question_patterns = [
            (r'^[·\s]*Q\.[·\s]*', 'Q. (with optional middle dots)'),
            (r'^\s*Q\.\s*', 'Q. (standard)'),
            (r'^\s*Q:\s*', 'Q: (colon format)'),
            (r'^Q\s+[A-Z]', 'Q (space + capital)'),
            (r'^\s*QUESTION[:\s]+', 'QUESTION:'),
            (r'^BY\s+M[RS]\.\s+\w+:', 'BY MR./MS. NAME:'),
        ]
        
        self.answer_patterns = [
            (r'^[·\s]*A\.[·\s]*', 'A. (with optional middle dots)'),
            (r'^\s*A\.\s*', 'A. (standard)'),
            (r'^\s*A:\s*', 'A: (colon format)'),
            (r'^A\s+[A-Z]', 'A (space + capital)'),
            (r'^\s*ANSWER[:\s]+', 'ANSWER:'),
            (r'^[·\s]*THE\s+WITNESS:[·\s]*', 'THE WITNESS:'),
        ]
        
        # Compile patterns for matching
        self.compiled_question_patterns = [
            (re.compile(pattern, re.IGNORECASE), name) 
            for pattern, name in self.question_patterns
        ]
        self.compiled_answer_patterns = [
            (re.compile(pattern, re.IGNORECASE), name)
            for pattern, name in self.answer_patterns
        ]
    
    def _matches_question_pattern(self, line: str) -> Tuple[bool, Optional[str]]:
        """Check if line matches a question pattern. Returns (matched, pattern_name)."""
        line = line.strip()
        if not line:
            return False, None
        
        for pattern, name in self.compiled_question_patterns:
            if pattern.match(line):
                return True, name
        return False, None
    
    def _matches_answer_pattern(self, line: str) -> Tuple[bool, Optional[str]]:
        """Check if line matches an answer pattern. Returns (matched, pattern_name)."""
        line = line.strip()
        if not line:
            return False, None
        
        for pattern, name in self.compiled_answer_patterns:
            if pattern.match(line):
                return True, name
        return False, None
    
    def _extract_qa_pairs_with_diagnostics(
        self, 
        pdf_path: str, 
        start_page: int, 
        end_page: int,
        max_pairs: int = 10
    ) -> Tuple[List[Dict], Dict]:
        """
        Extract Q/A pairs from a page range with comprehensive diagnostics.
        
        Returns:
            Tuple of (qa_pairs, diagnostics)
        """
        doc = fitz.open(pdf_path)
        qa_pairs = []
        current_question = None
        current_answer = None
        state = 'searching'  # States: searching, in_question, in_answer
        
        # Diagnostic data collection
        diagnostics = {
            'text_extraction': {
                'pages_analyzed': [],
                'total_lines': 0,
                'non_empty_lines': 0,
                'avg_line_length': 0.0,
                'sample_pages': []
            },
            'pattern_matching': {
                'question_matches': [],
                'answer_matches': [],
                'no_matches': [],
                'pattern_counts': {
                    'question': {},
                    'answer': {}
                }
            },
            'line_analysis': [],
            'state_machine': {
                'transitions': [],
                'incomplete_pairs': []
            }
        }
        
        total_line_length = 0
        line_count_global = 0
        
        try:
            for page_num in range(start_page - 1, min(end_page, len(doc))):
                page = doc[page_num]
                text = page.get_text("text")
                lines = text.split('\n')
                
                page_info = {
                    'page_num': page_num + 1,
                    'total_lines': len(lines),
                    'non_empty_lines': 0,
                    'sample_text': []
                }
                
                for line_num, line in enumerate(lines, 1):
                    line_stripped = line.strip()
                    
                    # Text extraction stats
                    diagnostics['text_extraction']['total_lines'] += 1
                    if line_stripped:
                        diagnostics['text_extraction']['non_empty_lines'] += 1
                        total_line_length += len(line_stripped)
                        line_count_global += 1
                        page_info['non_empty_lines'] += 1
                    
                    # Store sample text from first 3 pages (first 30 lines each)
                    if len(diagnostics['text_extraction']['sample_pages']) < 3:
                        if len(page_info['sample_text']) < 30:
                            page_info['sample_text'].append(line)
                    
                    # Skip empty lines for processing
                    if not line_stripped:
                        # Record line analysis for first 100 lines
                        if len(diagnostics['line_analysis']) < 100:
                            diagnostics['line_analysis'].append({
                                'page': page_num + 1,
                                'line': line_num,
                                'text': line[:80],
                                'classification': 'EMPTY',
                                'pattern': None,
                                'state': state
                            })
                        continue
                    
                    # Check for question marker
                    is_question, q_pattern = self._matches_question_pattern(line_stripped)
                    is_answer, a_pattern = self._matches_answer_pattern(line_stripped)
                    
                    classification = 'UNKNOWN'
                    matched_pattern = None
                    
                    if is_question:
                        # Record pattern match
                        diagnostics['pattern_matching']['question_matches'].append({
                            'page': page_num + 1,
                            'line': line_num,
                            'text': line_stripped[:80],
                            'pattern': q_pattern
                        })
                        
                        # Count pattern usage
                        if q_pattern not in diagnostics['pattern_matching']['pattern_counts']['question']:
                            diagnostics['pattern_matching']['pattern_counts']['question'][q_pattern] = 0
                        diagnostics['pattern_matching']['pattern_counts']['question'][q_pattern] += 1
                        
                        classification = 'QUESTION'
                        matched_pattern = q_pattern
                        
                        # State machine transition
                        old_state = state
                        state = 'in_question'
                        diagnostics['state_machine']['transitions'].append({
                            'from': old_state,
                            'to': state,
                            'page': page_num + 1,
                            'line': line_num,
                            'reason': f'Question pattern matched: {q_pattern}'
                        })
                        
                        # Save previous Q/A pair if complete
                        if current_question and current_answer:
                            qa_pairs.append({
                                'question': current_question,
                                'answer': current_answer,
                                'page': current_question['page'],
                                'line': current_question['line']
                            })
                            
                            if len(qa_pairs) >= max_pairs:
                                break
                        elif current_question and not current_answer:
                            # Incomplete pair - question without answer
                            diagnostics['state_machine']['incomplete_pairs'].append({
                                'type': 'question_without_answer',
                                'page': current_question['page'],
                                'line': current_question['line'],
                                'text': current_question['text'][:80]
                            })
                        
                        # Start new question
                        current_question = {
                            'text': line_stripped,
                            'page': page_num + 1,
                            'line': line_num
                        }
                        current_answer = None
                    
                    # Check for answer marker
                    elif is_answer:
                        # Record pattern match
                        diagnostics['pattern_matching']['answer_matches'].append({
                            'page': page_num + 1,
                            'line': line_num,
                            'text': line_stripped[:80],
                            'pattern': a_pattern
                        })
                        
                        # Count pattern usage
                        if a_pattern not in diagnostics['pattern_matching']['pattern_counts']['answer']:
                            diagnostics['pattern_matching']['pattern_counts']['answer'][a_pattern] = 0
                        diagnostics['pattern_matching']['pattern_counts']['answer'][a_pattern] += 1
                        
                        classification = 'ANSWER'
                        matched_pattern = a_pattern
                        
                        if current_question:
                            # State machine transition
                            old_state = state
                            state = 'in_answer'
                            diagnostics['state_machine']['transitions'].append({
                                'from': old_state,
                                'to': state,
                                'page': page_num + 1,
                                'line': line_num,
                                'reason': f'Answer pattern matched: {a_pattern}'
                            })
                            
                            current_answer = {
                                'text': line_stripped,
                                'page': page_num + 1,
                                'line': line_num
                            }
                        else:
                            # Answer without question
                            diagnostics['state_machine']['incomplete_pairs'].append({
                                'type': 'answer_without_question',
                                'page': page_num + 1,
                                'line': line_num,
                                'text': line_stripped[:80]
                            })
                    
                    # Continue building question or answer
                    else:
                        if current_answer:
                            current_answer['text'] += ' ' + line_stripped
                            classification = 'CONTINUATION (answer)'
                        elif current_question:
                            current_question['text'] += ' ' + line_stripped
                            classification = 'CONTINUATION (question)'
                        else:
                            # No match and not continuing anything
                            if len(diagnostics['pattern_matching']['no_matches']) < 10:
                                diagnostics['pattern_matching']['no_matches'].append({
                                    'page': page_num + 1,
                                    'line': line_num,
                                    'text': line_stripped[:80]
                                })
                    
                    # Record line analysis for first 100 lines
                    if len(diagnostics['line_analysis']) < 100:
                        diagnostics['line_analysis'].append({
                            'page': page_num + 1,
                            'line': line_num,
                            'text': line_stripped[:80],
                            'classification': classification,
                            'pattern': matched_pattern,
                            'state': state
                        })
                
                # Store page info
                diagnostics['text_extraction']['pages_analyzed'].append(page_info)
                if len(page_info['sample_text']) > 0:
                    diagnostics['text_extraction']['sample_pages'].append(page_info)
                
                if len(qa_pairs) >= max_pairs:
                    break
            
            # Add last pair if complete
            if current_question and current_answer:
                qa_pairs.append({
                    'question': current_question,
                    'answer': current_answer,
                    'page': current_question['page'],
                    'line': current_question['line']
                })
            elif current_question and not current_answer:
                diagnostics['state_machine']['incomplete_pairs'].append({
                    'type': 'question_without_answer',
                    'page': current_question['page'],
                    'line': current_question['line'],
                    'text': current_question['text'][:80]
                })
            
            # Calculate average line length
            if line_count_global > 0:
                diagnostics['text_extraction']['avg_line_length'] = total_line_length / line_count_global
        
        finally:
            doc.close()
        
        return qa_pairs, diagnostics
    
    def _generate_diagnostic_conclusions(self, qa_pairs: List[Dict], diagnostics: Dict) -> List[str]:
        """Generate diagnostic conclusions based on extraction results."""
        conclusions = []
        recommendations = []
        
        # Check text extraction
        if diagnostics['text_extraction']['total_lines'] == 0:
            conclusions.append("CRITICAL: No text extracted from PDF")
            recommendations.append("Check if PDF is image-based (scanned) - requires OCR")
        elif diagnostics['text_extraction']['non_empty_lines'] == 0:
            conclusions.append("CRITICAL: All lines are empty")
            recommendations.append("PDF text extraction may be corrupted or malformed")
        
        # Check pattern matching
        q_matches = len(diagnostics['pattern_matching']['question_matches'])
        a_matches = len(diagnostics['pattern_matching']['answer_matches'])
        
        if q_matches == 0 and a_matches == 0:
            conclusions.append("CRITICAL: No Q/A patterns matched")
            recommendations.append("Transcript uses non-standard Q/A format - review sample text")
            recommendations.append("May need to add custom patterns to match this transcript format")
        elif q_matches == 0:
            conclusions.append("ERROR: No question patterns matched")
            recommendations.append("Check question format in sample text - may need new pattern")
        elif a_matches == 0:
            conclusions.append("ERROR: No answer patterns matched")
            recommendations.append("Check answer format in sample text - may need new pattern")
        elif q_matches > 0 and a_matches > 0 and len(qa_pairs) == 0:
            conclusions.append("ERROR: Patterns matched but no Q/A pairs formed")
            recommendations.append("State machine issue - questions and answers not pairing correctly")
            recommendations.append("Check if answers appear before questions or vice versa")
        
        # Check incomplete pairs
        incomplete = diagnostics['state_machine']['incomplete_pairs']
        if len(incomplete) > 0:
            q_without_a = sum(1 for p in incomplete if p['type'] == 'question_without_answer')
            a_without_q = sum(1 for p in incomplete if p['type'] == 'answer_without_question')
            
            if q_without_a > 0:
                conclusions.append(f"WARNING: {q_without_a} questions without answers")
                recommendations.append("Some questions may be followed by other questions without answers")
            if a_without_q > 0:
                conclusions.append(f"WARNING: {a_without_q} answers without questions")
                recommendations.append("Document may start mid-examination or have formatting issues")
        
        # Success case
        if len(qa_pairs) > 0:
            conclusions.append(f"SUCCESS: {len(qa_pairs)} Q/A pairs extracted successfully")
            
            # Pattern usage
            q_pattern_counts = diagnostics['pattern_matching']['pattern_counts']['question']
            a_pattern_counts = diagnostics['pattern_matching']['pattern_counts']['answer']
            
            if q_pattern_counts:
                most_common_q = max(q_pattern_counts.items(), key=lambda x: x[1])
                conclusions.append(f"Most common question pattern: {most_common_q[0]} ({most_common_q[1]} matches)")
            
            if a_pattern_counts:
                most_common_a = max(a_pattern_counts.items(), key=lambda x: x[1])
                conclusions.append(f"Most common answer pattern: {most_common_a[0]} ({most_common_a[1]} matches)")
        
        return conclusions, recommendations
    
    async def test_qa_extraction(
        self,
        pdf_path: str,
        document_id: str,
        examination_first_page: int,
        examination_last_page: int
    ) -> Dict:
        """
        Test Q/A extraction and generate comprehensive diagnostic log file.
        
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
            
            # Extract Q/A pairs with diagnostics
            sample_pairs, diagnostics = self._extract_qa_pairs_with_diagnostics(
                pdf_path,
                examination_first_page,
                examination_last_page,
                max_pairs=10
            )
            
            # Generate diagnostic conclusions
            conclusions, recommendations = self._generate_diagnostic_conclusions(sample_pairs, diagnostics)
            
            # Generate comprehensive diagnostic log file
            log_file = f"/tmp/qa_test_{document_id[:8]}.log"
            
            with open(log_file, 'w', encoding='utf-8') as f:
                # Header
                f.write("="*80 + "\n")
                f.write("Q/A EXTRACTION DIAGNOSTIC REPORT\n")
                f.write("="*80 + "\n\n")
                
                # SECTION 1: Test Configuration
                f.write("SECTION 1: TEST CONFIGURATION\n")
                f.write("-"*80 + "\n\n")
                f.write(f"Document ID: {document_id}\n")
                f.write(f"Test Range: Pages {examination_first_page} - {examination_last_page}\n")
                f.write(f"Max Q/A Pairs: 10\n\n")
                
                f.write("Question Patterns:\n")
                for pattern, name in self.question_patterns:
                    f.write(f"  - {name}: {pattern}\n")
                
                f.write("\nAnswer Patterns:\n")
                for pattern, name in self.answer_patterns:
                    f.write(f"  - {name}: {pattern}\n")
                
                f.write("\n" + "="*80 + "\n\n")
                
                # SECTION 2: Text Extraction Diagnostics
                f.write("SECTION 2: TEXT EXTRACTION DIAGNOSTICS\n")
                f.write("-"*80 + "\n\n")
                
                text_stats = diagnostics['text_extraction']
                f.write(f"Pages Analyzed: {len(text_stats['pages_analyzed'])}\n")
                f.write(f"Total Lines: {text_stats['total_lines']}\n")
                f.write(f"Non-Empty Lines: {text_stats['non_empty_lines']}\n")
                f.write(f"Average Line Length: {text_stats['avg_line_length']:.1f} characters\n\n")
                
                # Sample text from first 3 pages
                f.write("Sample Text (First 3 Pages, First 30 Lines):\n\n")
                for page_info in text_stats['sample_pages'][:3]:
                    f.write(f"--- PAGE {page_info['page_num']} ---\n")
                    for i, line in enumerate(page_info['sample_text'][:30], 1):
                        f.write(f"{i:3d}| {line}\n")
                    f.write("\n")
                
                f.write("="*80 + "\n\n")
                
                # SECTION 3: Pattern Matching Analysis
                f.write("SECTION 3: PATTERN MATCHING ANALYSIS\n")
                f.write("-"*80 + "\n\n")
                
                pattern_data = diagnostics['pattern_matching']
                f.write(f"Question Patterns Matched: {len(pattern_data['question_matches'])}\n")
                f.write(f"Answer Patterns Matched: {len(pattern_data['answer_matches'])}\n")
                f.write(f"Lines With No Match: {len(pattern_data['no_matches'])}\n\n")
                
                # Pattern counts
                f.write("Question Pattern Usage:\n")
                if pattern_data['pattern_counts']['question']:
                    for pattern, count in sorted(
                        pattern_data['pattern_counts']['question'].items(),
                        key=lambda x: x[1],
                        reverse=True
                    ):
                        f.write(f"  - {pattern}: {count} matches\n")
                else:
                    f.write("  (No question patterns matched)\n")
                
                f.write("\nAnswer Pattern Usage:\n")
                if pattern_data['pattern_counts']['answer']:
                    for pattern, count in sorted(
                        pattern_data['pattern_counts']['answer'].items(),
                        key=lambda x: x[1],
                        reverse=True
                    ):
                        f.write(f"  - {pattern}: {count} matches\n")
                else:
                    f.write("  (No answer patterns matched)\n")
                
                # Sample matches
                f.write("\nSample Question Matches (First 5):\n")
                for match in pattern_data['question_matches'][:5]:
                    f.write(f"  Page {match['page']}, Line {match['line']}: ")
                    f.write(f"[{match['pattern']}] {match['text']}\n")
                
                f.write("\nSample Answer Matches (First 5):\n")
                for match in pattern_data['answer_matches'][:5]:
                    f.write(f"  Page {match['page']}, Line {match['line']}: ")
                    f.write(f"[{match['pattern']}] {match['text']}\n")
                
                f.write("\nSample Lines With No Pattern Match (First 10):\n")
                for no_match in pattern_data['no_matches'][:10]:
                    f.write(f"  Page {no_match['page']}, Line {no_match['line']}: {no_match['text']}\n")
                
                f.write("\n" + "="*80 + "\n\n")
                
                # SECTION 4: Line-by-Line Analysis
                f.write("SECTION 4: LINE-BY-LINE ANALYSIS (First 100 Lines)\n")
                f.write("-"*80 + "\n\n")
                f.write(f"{'Page':<6} {'Line':<6} {'State':<12} {'Class':<20} {'Pattern':<30} Text\n")
                f.write("-"*80 + "\n")
                
                for analysis in diagnostics['line_analysis'][:100]:
                    pattern_str = analysis['pattern'] or ''
                    f.write(f"{analysis['page']:<6} {analysis['line']:<6} ")
                    f.write(f"{analysis['state']:<12} {analysis['classification']:<20} ")
                    f.write(f"{pattern_str:<30} {analysis['text']}\n")
                
                f.write("\n" + "="*80 + "\n\n")
                
                # SECTION 5: Extraction State Machine
                f.write("SECTION 5: EXTRACTION STATE MACHINE\n")
                f.write("-"*80 + "\n\n")
                
                state_data = diagnostics['state_machine']
                f.write(f"State Transitions: {len(state_data['transitions'])}\n")
                f.write(f"Incomplete Q/A Pairs: {len(state_data['incomplete_pairs'])}\n\n")
                
                if state_data['transitions']:
                    f.write("State Transitions (First 20):\n")
                    for trans in state_data['transitions'][:20]:
                        f.write(f"  Page {trans['page']}, Line {trans['line']}: ")
                        f.write(f"{trans['from']} -> {trans['to']} ({trans['reason']})\n")
                
                if state_data['incomplete_pairs']:
                    f.write("\nIncomplete Q/A Pairs:\n")
                    for incomplete in state_data['incomplete_pairs']:
                        f.write(f"  {incomplete['type']} - Page {incomplete['page']}, Line {incomplete['line']}\n")
                        f.write(f"    Text: {incomplete['text']}\n")
                
                f.write("\n" + "="*80 + "\n\n")
                
                # SECTION 6: Results Summary
                f.write("SECTION 6: RESULTS SUMMARY\n")
                f.write("-"*80 + "\n\n")
                
                f.write(f"Q/A Pairs Extracted: {len(sample_pairs)}\n\n")
                
                if len(sample_pairs) > 0:
                    f.write("SAMPLE Q/A PAIRS:\n\n")
                    for i, pair in enumerate(sample_pairs, 1):
                        f.write(f"PAIR {i} (Page {pair['page']}, Line {pair['line']})\n")
                        f.write(f"{'='*80}\n")
                        f.write(f"QUESTION: {pair['question']['text']}\n\n")
                        f.write(f"ANSWER: {pair['answer']['text']}\n")
                        f.write(f"{'-'*80}\n\n")
                
                f.write("DIAGNOSTIC CONCLUSIONS:\n")
                for conclusion in conclusions:
                    f.write(f"  - {conclusion}\n")
                
                if recommendations:
                    f.write("\nRECOMMENDATIONS:\n")
                    for recommendation in recommendations:
                        f.write(f"  - {recommendation}\n")
                
                f.write("\n" + "="*80 + "\n")
                f.write("DIAGNOSTIC REPORT COMPLETE\n")
                f.write("="*80 + "\n")
            
            success = len(sample_pairs) > 0
            errors = []
            
            if not success:
                errors.append("No Q/A pairs found - see diagnostic report for details")
            
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
            
            # Still create log file to document the error
            log_file = f"/tmp/qa_test_{document_id[:8]}.log"
            try:
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write("="*80 + "\n")
                    f.write("Q/A EXTRACTION DIAGNOSTIC REPORT\n")
                    f.write("="*80 + "\n\n")
                    f.write(f"Document ID: {document_id}\n")
                    f.write(f"Test Range: Pages {examination_first_page} - {examination_last_page}\n")
                    f.write(f"Status: CRITICAL ERROR\n\n")
                    f.write(f"Error: {str(e)}\n\n")
                    f.write("The Q/A extraction test encountered a critical error and could not complete.\n")
                    f.write("This typically indicates:\n")
                    f.write("  - PDF file is corrupted or unreadable\n")
                    f.write("  - File path is incorrect\n")
                    f.write("  - Insufficient memory or system resources\n")
                    f.write("\n" + "="*80 + "\n")
                    f.write("TEST FAILED\n")
                    f.write("="*80 + "\n")
            except Exception as log_error:
                logger.error(f"Failed to create error log file: {log_error}")
                log_file = None
            
            return {
                'success': False,
                'qa_pairs_found': 0,
                'sample_pairs': [],
                'log_file': log_file,
                'errors': [str(e)]
            }


# Singleton instance
qa_test_service = QATestService()
