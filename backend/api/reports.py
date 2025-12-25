"""Reports API endpoints for people, chronological, page/line, topic, and narrative reports."""
import logging
import json
from typing import List, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from openai import AsyncOpenAI

from api.auth import get_current_user, User
from services.db_service import db_service
from services.people_extraction_service import people_extraction_service
from config import settings

router = APIRouter(prefix="/api/documents", tags=["reports"])
logger = logging.getLogger(__name__)

# Initialize OpenAI client for narrative generation
openai_client = AsyncOpenAI(api_key=settings.openai_api_key_1 or settings.openai_api_key)


@router.get("/{document_id}/reports/people")
async def get_people_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get people report: all summaries mentioning each person.
    
    Returns a list of people with their associated Q&A items.
    """
    try:
        # Get all people mentioned in document
        people = await people_extraction_service.get_people_for_document(document_id)
        
        if not people:
            return {"people": []}
        
        # For each person, get their Q&A items
        result = []
        for person in people:
            person_id = UUID(person["id"])
            qa_items = await people_extraction_service.get_qa_items_for_person(
                document_id,
                person_id
            )
            
            result.append({
                "person": person,
                "qa_items": qa_items,
                "count": len(qa_items)
            })
        
        # Sort by count (most mentions first)
        result.sort(key=lambda x: x["count"], reverse=True)
        
        return {"people": result}
        
    except Exception as e:
        logger.error(f"Failed to get people report for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate people report: {str(e)}"
        )


@router.get("/{document_id}/reports/chronological")
async def get_chronological_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get chronological report: summaries with event dates, sorted chronologically.
    
    Returns Q&A items that have event dates, ordered by date.
    """
    try:
        rows = await db_service.fetch(
            """
            SELECT 
                id,
                page_number,
                line_number,
                question,
                answer,
                summary,
                topics,
                event_date
            FROM final_qa_items
            WHERE document_id = $1 AND event_date IS NOT NULL AND event_date != ''
            ORDER BY event_date, page_number, line_number
            """,
            document_id
        )
        
        items = [
            {
                "id": str(row["id"]),
                "page": row["page_number"],
                "line": row["line_number"],
                "question": row["question"],
                "answer": row["answer"],
                "summary": row["summary"],
                "topics": row["topics"] or ["Other"],
                "event_date": row["event_date"]
            }
            for row in rows
        ]
        
        return {"items": items, "total": len(items)}
        
    except Exception as e:
        logger.error(f"Failed to get chronological report for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate chronological report: {str(e)}"
        )


@router.get("/{document_id}/reports/page-line")
async def get_page_line_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get page/line report: three-column format (page/line, summary, topics).
    
    Returns all Q&A items ordered by page and line number.
    """
    try:
        rows = await db_service.fetch(
            """
            SELECT 
                id,
                page_number,
                line_number,
                answer_end_page,
                answer_end_line,
                question,
                answer,
                summary,
                topics,
                event_date
            FROM final_qa_items
            WHERE document_id = $1
            ORDER BY page_number, line_number
            """,
            document_id
        )
        
        items = [
            {
                "id": str(row["id"]),
                "page": row["page_number"],
                "line": row["line_number"],
                "answer_end_page": row["answer_end_page"],
                "answer_end_line": row["answer_end_line"],
                "page_line_ref": format_page_line_reference(
                    row["page_number"],
                    row["line_number"],
                    row["answer_end_page"],
                    row["answer_end_line"]
                ),
                "question": row["question"],
                "answer": row["answer"],
                "summary": row["summary"],
                "topics": row["topics"] or ["Other"],
                "event_date": row["event_date"]
            }
            for row in rows
        ]
        
        return {"items": items, "total": len(items)}
        
    except Exception as e:
        logger.error(f"Failed to get page/line report for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate page/line report: {str(e)}"
        )


@router.get("/{document_id}/reports/topics")
async def get_topics_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get topics report: Q&A items grouped by topic.
    
    Returns topics with their associated Q&A items and counts.
    Since topics is now an array, Q&A items can appear under multiple topics.
    """
    try:
        # Get all Q&A items with their topics arrays
        qa_rows = await db_service.fetch(
            """
            SELECT 
                id,
                page_number,
                line_number,
                answer_end_page,
                answer_end_line,
                question,
                answer,
                summary,
                topics,
                event_date
            FROM final_qa_items
            WHERE document_id = $1
            ORDER BY page_number, line_number
            """,
            document_id
        )
        
        # Group Q&A items by topic (each item can appear in multiple topics)
        topics_map = {}
        for qa_row in qa_rows:
            topics = qa_row.get("topics", ["Other"])
            if not topics:
                topics = ["Other"]
            
            qa_item_data = {
                "id": str(qa_row["id"]),
                "page": qa_row["page_number"],
                "line": qa_row["line_number"],
                "answer_end_page": qa_row["answer_end_page"],
                "answer_end_line": qa_row["answer_end_line"],
                "page_line_ref": format_page_line_reference(
                    qa_row["page_number"],
                    qa_row["line_number"],
                    qa_row["answer_end_page"],
                    qa_row["answer_end_line"]
                ),
                "question": qa_row["question"],
                "answer": qa_row["answer"],
                "summary": qa_row["summary"],
                "event_date": qa_row["event_date"]
            }
            
            # Add this Q&A to each topic it belongs to
            for topic in topics:
                if topic not in topics_map:
                    topics_map[topic] = []
                topics_map[topic].append(qa_item_data)
        
        # Convert to list and sort by count
        topics_list = []
        for topic, qa_items in topics_map.items():
            topics_list.append({
                "topic": topic,
                "count": len(qa_items),
                "qa_items": qa_items
            })
        
        # Sort by count (most items first), then by topic name
        topics_list.sort(key=lambda x: (-x["count"], x["topic"]))
        
        return {"topics": topics_list, "total": len(topics_list)}
        
    except Exception as e:
        logger.error(f"Failed to get topics report for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate topics report: {str(e)}"
        )


def format_page_line_reference(
    page: int,
    line: int,
    answer_end_page: int = None,
    answer_end_line: int = None
) -> str:
    """
    Format page/line reference for display.
    
    Examples:
    - "Page 45, Line 12"
    - "Page 45, Lines 12-18"
    - "Page 45, Line 12 - Page 46, Line 5"
    """
    if answer_end_page and answer_end_page != page:
        return f"Page {page}, Line {line} - Page {answer_end_page}, Line {answer_end_line}"
    elif answer_end_line and answer_end_line != line:
        return f"Page {page}, Lines {line}-{answer_end_line}"
    else:
        return f"Page {page}, Line {line}"


@router.get("/{document_id}/reports/narrative")
async def get_narrative_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get narrative report: AI-generated narrative for each topic with inline citations.
    
    Returns topics with AI-generated narratives that include clickable [page:line-page:line] citations.
    """
    try:
        # Get all Q&A items with their topics arrays
        qa_rows = await db_service.fetch(
            """
            SELECT 
                id,
                page_number,
                line_number,
                answer_end_page,
                answer_end_line,
                summary,
                topics,
                event_date
            FROM final_qa_items
            WHERE document_id = $1
            ORDER BY page_number, line_number
            """,
            document_id
        )
        
        # Group Q&A items by topic (each item can appear in multiple topics)
        topics_map = {}
        for qa_row in qa_rows:
            topics = qa_row.get("topics", ["Other"])
            if not topics:
                topics = ["Other"]
            
            # Add this Q&A to each topic it belongs to
            for topic in topics:
                if topic not in topics_map:
                    topics_map[topic] = []
                topics_map[topic].append(qa_row)
        
        # Topic priority for ordering
        topic_priority = {
            'Background & Education': 1,
            'Employment History': 2,
            'Incident Description': 3,
            'Medical Treatment': 4,
            'Damages & Injuries': 5,
            'Timeline & Chronology': 6,
            'Documents & Evidence': 7,
            'Witness Statements': 8,
            'Expert Opinions': 9
        }
        
        narratives = []
        
        # Sort topics by priority
        sorted_topics = sorted(
            topics_map.items(),
            key=lambda x: (topic_priority.get(x[0], 10), -len(x[1]), x[0])
        )
        
        for topic, qa_items in sorted_topics:
            if not qa_items:
                continue
            
            # Format summaries with [page:line-page:line] citations for AI
            summaries_with_citations = []
            citation_map = {}  # Map citation IDs to full citation info
            
            for qa_row in qa_items:
                # Create citation in [page:line-page:line] format
                citation_id = f"[{qa_row['page_number']}:{qa_row['line_number']}"
                if qa_row['answer_end_page'] and qa_row['answer_end_page'] != qa_row['page_number']:
                    citation_id += f"-{qa_row['answer_end_page']}:{qa_row['answer_end_line']}"
                elif qa_row['answer_end_line'] and qa_row['answer_end_line'] != qa_row['line_number']:
                    citation_id += f"-{qa_row['answer_end_line']}"
                citation_id += "]"
                
                page_line_ref = format_page_line_reference(
                    qa_row["page_number"],
                    qa_row["line_number"],
                    qa_row["answer_end_page"],
                    qa_row["answer_end_line"]
                )
                
                summaries_with_citations.append(
                    f"{citation_id} {qa_row['summary']}"
                )
                
                citation_map[citation_id] = {
                    "id": str(qa_row["id"]),
                    "page": qa_row["page_number"],
                    "line": qa_row["line_number"],
                    "page_line_ref": page_line_ref,
                    "summary": qa_row["summary"]
                }
            
            # Generate narrative using AI
            narrative_text = await generate_narrative_for_topic(
                topic,
                summaries_with_citations
            )
            
            narratives.append({
                "topic": topic,
                "narrative": narrative_text,
                "citations": citation_map,
                "item_count": len(qa_items)
            })
        
        return {"narratives": narratives, "total": len(narratives)}
        
    except Exception as e:
        logger.error(f"Failed to generate narrative report for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate narrative report: {str(e)}"
        )


async def generate_narrative_for_topic(topic: str, summaries: List[str]) -> str:
    """
    Generate a narrative summary for a topic using AI.
    
    Args:
        topic: The topic name
        summaries: List of summaries with citation IDs (e.g., "[101:5-102:3] The witness testified...")
        
    Returns:
        Narrative text with inline citations in [page:line-page:line] format
    """
    try:
        summaries_text = "\n".join(summaries)
        
        system_prompt = f"""You are a legal assistant creating a narrative summary for the topic: {topic}.

You will receive numbered summaries from a deposition transcript with citations in [page:line-page:line] format. Your task is to:
1. Synthesize the information into a coherent narrative paragraph or section
2. Include the citation numbers [page:line-page:line] inline where the information appears
3. Write in third person past tense
4. Organize information logically (chronologically or thematically)
5. DO NOT add information not present in the summaries
6. Keep citations in the EXACT format [page:line-page:line] - DO NOT change or abbreviate them

Example:
Input summaries:
[101:5] The witness testified they worked at ABC Corp from 2020 to 2022.
[102:10-102:15] The witness stated they started on January 15, 2020.
[103:2] The witness mentioned their role was sales manager.

Output narrative:
The witness testified that they worked at ABC Corp from 2020 to 2022 [101:5], starting on January 15, 2020 [102:10-102:15]. During this time, they served as a sales manager [103:2].

Write a clear, professional narrative that incorporates all the provided information with proper citations."""

        user_prompt = f"Topic: {topic}\n\nSummaries:\n{summaries_text}\n\nCreate a narrative summary with inline citations:"
        
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        narrative = response.choices[0].message.content.strip()
        return narrative
        
    except Exception as e:
        logger.error(f"Failed to generate narrative for topic {topic}: {e}")
        # Fallback: return summaries as bullet points
        return "\n\n".join(summaries)


async def generate_people_narrative(person_name: str, role: str, qa_summaries_with_citations: List[str]) -> str:
    """
    Generate AI narrative for a person with inline citations.
    
    Args:
        person_name: The person's name
        role: Their role (witness, attorney, other)
        qa_summaries_with_citations: List of summaries with [page:line-page:line] citations
        
    Returns:
        Narrative text with inline citations in [page:line-page:line] format
    
    Example output:
    "John Smith, the questioning attorney, was involved in discussions about 
    the accident [101:5-102:3] and later addressed the witness's medical 
    treatment [105:2-105:8]. He also inquired about damages [108:1-108:12]."
    """
    try:
        summaries_text = "\n".join(qa_summaries_with_citations)
        
        role_description = {
            'witness': 'the witness/deponent',
            'attorney': 'an attorney',
            'other': 'a person mentioned in the deposition'
        }.get(role.lower(), 'a person mentioned')
        
        system_prompt = f"""You are creating a narrative summary about {person_name}, 
who is identified as {role_description} in a deposition.

You will receive summaries with citations in [page:line-page:line] format. Your task is to:
1. Create a coherent narrative paragraph about this person's involvement/mentions
2. Start by introducing the person and their role
3. Describe their involvement using flowing prose
4. Include inline citations [page:line-page:line] where information appears
5. Write in past tense, third person
6. DO NOT add information not in the summaries
7. Keep citations in the EXACT format [page:line-page:line] - DO NOT change them

Example:
Input summaries:
[101:5-102:3] The witness testified about the accident with John Smith present.
[105:2-105:8] John Smith, the questioning attorney, asked about medical treatment.
[108:1-108:12] John Smith inquired about damages.

Output narrative:
John Smith, the questioning attorney, was present during testimony about the accident [101:5-102:3]. He questioned the witness about medical treatment [105:2-105:8] and later inquired about damages [108:1-108:12].

Write a clear, professional narrative."""

        user_prompt = f"Person: {person_name} ({role})\n\nSummaries:\n{summaries_text}\n\nCreate a narrative summary with inline citations:"
        
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        
        narrative = response.choices[0].message.content.strip()
        return narrative
        
    except Exception as e:
        logger.error(f"Failed to generate narrative for person {person_name}: {e}")
        # Fallback: return summaries as bullet points
        return "\n\n".join(qa_summaries_with_citations)


@router.get("/{document_id}/reports/people-narrative")
async def get_people_narrative_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get people report with AI-generated narratives for each person.
    
    Returns a list of people with AI-generated narrative summaries including inline citations.
    """
    try:
        # Get all people mentioned in document
        people = await people_extraction_service.get_people_for_document(document_id)
        
        if not people:
            return {"people": []}
        
        # For each person, get their Q&A items and generate narrative
        result = []
        for person in people:
            person_id = UUID(person["id"])
            qa_items = await people_extraction_service.get_qa_items_for_person(
                document_id,
                person_id
            )
            
            if not qa_items:
                continue
            
            # Format summaries with [page:line-page:line] citations
            summaries_with_citations = []
            citation_map = {}
            
            for qa in qa_items:
                # Create citation in [page:line-page:line] format
                citation_id = f"[{qa['page']}:{qa['line']}"
                if qa.get('answer_end_page') and qa['answer_end_page'] != qa['page']:
                    citation_id += f"-{qa['answer_end_page']}:{qa['answer_end_line']}"
                elif qa.get('answer_end_line') and qa['answer_end_line'] != qa['line']:
                    citation_id += f"-{qa['answer_end_line']}"
                citation_id += "]"
                
                summaries_with_citations.append(f"{citation_id} {qa['summary']}")
                
                citation_map[citation_id] = {
                    "id": qa['id'],
                    "page": qa['page'],
                    "line": qa['line'],
                    "page_line_ref": qa['page_line_ref'],
                    "summary": qa['summary']
                }
            
            # Generate AI narrative
            narrative = await generate_people_narrative(
                person["display_name"],
                person["role"],
                summaries_with_citations
            )
            
            result.append({
                "person": person,
                "narrative": narrative,
                "citations": citation_map,
                "count": len(qa_items)
            })
        
        # Sort by count (most mentions first)
        result.sort(key=lambda x: x["count"], reverse=True)
        
        return {"people": result}
        
    except Exception as e:
        logger.error(f"Failed to get people narrative report for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate people narrative report: {str(e)}"
        )


@router.get("/{document_id}/reports/combined")
async def get_combined_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get combined report with:
    A. Cover page (witness, date, case name)
    B. Table of contents
    C. Narrative report (topics with AI narratives)
    D. People report (AI-generated narratives per person)
    E. Page/Line report
    """
    try:
        # Fetch document metadata for cover page
        doc = await db_service.fetchrow(
            "SELECT witness_name, deposition_date, case_name, case_number, filename FROM documents WHERE id = $1",
            document_id
        )
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Generate cover page
        cover_page = {
            "witness_name": doc["witness_name"] or "Unknown Witness",
            "deposition_date": doc["deposition_date"] or "Date not specified",
            "case_name": doc["case_name"] or "Unknown Case",
            "case_number": doc["case_number"] or "N/A",
            "filename": doc["filename"]
        }
        
        # Get narrative report data
        narrative_response = await get_narrative_report(document_id, current_user)
        narrative_data = narrative_response if isinstance(narrative_response, dict) else {"narratives": []}
        
        # Get people narrative report data
        people_response = await get_people_narrative_report(document_id, current_user)
        people_data = people_response if isinstance(people_response, dict) else {"people": []}
        
        # Get page/line report data
        page_line_response = await get_page_line_report(document_id, current_user)
        page_line_data = page_line_response if isinstance(page_line_response, dict) else {"items": []}
        
        # Generate table of contents
        toc = []
        toc.append({"section": "Cover Page", "page": 1})
        toc.append({"section": "Table of Contents", "page": 2})
        
        current_page = 3
        if narrative_data.get("narratives"):
            toc.append({"section": "Narrative Report", "page": current_page})
            for idx, narrative in enumerate(narrative_data["narratives"]):
                toc.append({"section": f"  {narrative['topic']}", "page": current_page + idx})
            current_page += len(narrative_data["narratives"])
        
        if people_data.get("people"):
            toc.append({"section": "People Report", "page": current_page})
            for idx, person_data in enumerate(people_data["people"]):
                toc.append({"section": f"  {person_data['person']['display_name']}", "page": current_page + idx})
            current_page += len(people_data["people"])
        
        if page_line_data.get("items"):
            toc.append({"section": "Page/Line Report", "page": current_page})
        
        return {
            "cover_page": cover_page,
            "table_of_contents": toc,
            "narrative_report": narrative_data,
            "people_report": people_data,
            "page_line_report": page_line_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate combined report for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate combined report: {str(e)}"
        )

