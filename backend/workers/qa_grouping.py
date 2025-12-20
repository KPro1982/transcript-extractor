"""Q&A grouping logic for related sequential Q&As."""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def group_related_qas(qa_items: List[Dict], should_group: bool = False) -> List[Dict]:
    """
    Group closely related sequential Q&As into combined items.
    
    This is used when users enable the "group_related" setting.
    Only groups SEQUENTIAL Q&As that are clearly about the same topic.
    
    Args:
        qa_items: List of Q&A dictionaries with 'question' and 'answer'
        should_group: Whether to actually perform grouping
    
    Returns:
        List of Q&A dictionaries, with related sequential ones combined
    
    Example:
        Input:
        1. Q: What is your birth date? A: April 19, 1968
        2. Q: So you are 57 years old? A: Yes
        3. Q: Where do you live? A: Chicago
        
        Output (grouped):
        1. Q: What is your birth date? So you are 57 years old?
           A: April 19, 1968. Yes.
        2. Q: Where do you live? A: Chicago
    """
    if not should_group or not qa_items:
        return qa_items
    
    logger.info(f"Grouping related Q&As from {len(qa_items)} items")
    
    grouped = []
    i = 0
    
    while i < len(qa_items):
        current = qa_items[i].copy()
        
        # Look ahead to see if next Q&As are related
        j = i + 1
        group_size = 1
        
        while j < len(qa_items) and should_merge(current, qa_items[j], qa_items[i:j+1]):
            # Merge the next Q&A into current
            next_qa = qa_items[j]
            current = merge_qas(current, next_qa)
            j += 1
            group_size += 1
            
            # Limit group size to prevent overly long summaries (max 5 sequential)
            if group_size >= 5:
                break
        
        grouped.append(current)
        i = j
    
    logger.info(f"Grouped {len(qa_items)} Q&As into {len(grouped)} items ({len(qa_items) - len(grouped)} groups formed)")
    return grouped


def should_merge(current: Dict, next_qa: Dict, all_in_group: List[Dict]) -> bool:
    """
    Determine if two sequential Q&As should be merged.
    
    Criteria:
    - Questions are very short (< 20 words) - suggests follow-up
    - Answer references previous context (pronouns like "Yes", "No", "That", "It")
    - Same speaker pattern
    - Not too many already grouped (max 5)
    """
    current_q = current.get('question', '').strip()
    current_a = current.get('answer', '').strip()
    next_q = next_qa.get('question', '').strip()
    next_a = next_qa.get('answer', '').strip()
    
    # Don't merge if either is very long (probably substantial topics)
    if len(current_q.split()) > 30 or len(next_q.split()) > 30:
        return False
    
    if len(current_a.split()) > 50 or len(next_a.split()) > 50:
        return False
    
    # Check if next answer is a simple confirmation/follow-up
    confirmation_words = {
        'yes', 'no', 'correct', 'right', 'that', 'it', 'true', 'false',
        'indeed', 'exactly', 'sure', 'okay', 'ok', 'yeah', 'yep', 'nope',
        'that\'s right', 'that\'s correct', 'i believe so', 'i think so'
    }
    
    next_a_lower = next_a.lower().strip('.')
    if next_a_lower in confirmation_words or len(next_a.split()) <= 3:
        return True
    
    # Check if next question is a clarification/follow-up
    follow_up_words = ['so', 'and', 'then', 'therefore', 'thus', 'meaning', 'right?', 'correct?']
    next_q_lower = next_q.lower()
    
    for word in follow_up_words:
        if next_q_lower.startswith(word):
            return True
    
    return False


def merge_qas(qa1: Dict, qa2: Dict) -> Dict:
    """
    Merge two Q&A dictionaries into one.
    
    Combines questions and answers, maintains location info from first Q&A,
    and marks the end location from second Q&A.
    """
    merged = qa1.copy()
    
    # Combine questions (separated by space)
    merged['question'] = f"{qa1.get('question', '').strip()} {qa2.get('question', '').strip()}".strip()
    
    # Combine answers (separated by space)
    merged['answer'] = f"{qa1.get('answer', '').strip()} {qa2.get('answer', '').strip()}".strip()
    
    # Update end location to second Q&A's end
    if 'answer_end_page' in qa2:
        merged['answer_end_page'] = qa2['answer_end_page']
    if 'answer_end_line' in qa2:
        merged['answer_end_line'] = qa2['answer_end_line']
    
    # Mark as grouped for tracking
    merged['is_grouped'] = True
    merged['group_count'] = qa1.get('group_count', 1) + 1
    
    return merged

