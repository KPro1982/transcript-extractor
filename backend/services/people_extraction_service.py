"""Service for extracting and normalizing people from Q&A pairs."""
import logging
import re
from typing import List, Dict, Optional
from uuid import UUID

from services.db_service import db_service

logger = logging.getLogger(__name__)


class PeopleExtractionService:
    """Service for extracting and normalizing people mentioned in depositions."""
    
    def __init__(self):
        self.name_variations = {}  # Cache for normalized names
    
    def normalize_name(self, name: str, witness_name: Optional[str] = None) -> str:
        """
        Normalize person name to handle variations.
        
        Examples:
        - "Hannah" -> "Hannah Craven" (if witness_name is "Hannah Craven")
        - "Ms. Craven" -> "Hannah Craven"
        - "John Smith" -> "John Smith"
        
        Args:
            name: Name as it appears in text
            witness_name: Full witness name from document metadata
            
        Returns:
            Normalized full name
        """
        if not name or not name.strip():
            return name
        
        name = name.strip()
        
        # If it's already a full name (First Last), return as is
        if " " in name and not name.startswith(("Mr.", "Mrs.", "Ms.", "Dr.")):
            return name
        
        # Handle titles: "Ms. Craven" -> extract last name
        title_pattern = r'^(Mr\.|Mrs\.|Ms\.|Dr\.)\s+([A-Za-z]+)$'
        title_match = re.match(title_pattern, name)
        if title_match:
            last_name = title_match.group(2)
            # Try to match with witness last name
            if witness_name and last_name in witness_name:
                return witness_name
            return name  # Return as is if we can't match
        
        # Handle first name only: "Hannah" -> match with witness
        if witness_name and " " in witness_name:
            first_name = witness_name.split()[0]
            if name.lower() == first_name.lower():
                return witness_name
        
        return name
    
    async def extract_and_store_people(
        self,
        document_id: UUID,
        qa_item_id: UUID,
        people_data: List[Dict],
        witness_name: Optional[str] = None
    ):
        """
        Extract people from AI response and store in database.
        
        Args:
            document_id: Document UUID
            qa_item_id: Q&A item UUID
            people_data: List of people dicts from AI response
                        Format: [{"name": "...", "role": "...", "context": "..."}]
            witness_name: Full witness name from document metadata
        """
        if not people_data:
            return
        
        for person in people_data:
            try:
                display_name = person.get("name", "").strip()
                if not display_name:
                    continue
                
                # Normalize the name
                normalized_name = self.normalize_name(display_name, witness_name)
                role = person.get("role", "other")
                context = person.get("context", "")
                
                # Insert or update person in people_mentioned table
                person_id = await db_service.fetchval(
                    """
                    INSERT INTO people_mentioned (document_id, normalized_name, display_name, role, context)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (document_id, normalized_name) 
                    DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        role = EXCLUDED.role,
                        context = EXCLUDED.context
                    RETURNING id
                    """,
                    document_id,
                    normalized_name,
                    display_name,
                    role,
                    context
                )
                
                # Link person to Q&A item in junction table
                await db_service.execute(
                    """
                    INSERT INTO qa_people (qa_item_id, people_id, mention_context)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (qa_item_id, people_id) DO NOTHING
                    """,
                    qa_item_id,
                    person_id,
                    context
                )
                
                logger.debug(f"Stored person: {normalized_name} (role: {role}) for Q&A {qa_item_id}")
                
            except Exception as e:
                logger.error(f"Failed to store person {person}: {e}", exc_info=True)
                # Continue processing other people even if one fails
    
    async def get_people_for_document(self, document_id: UUID) -> List[Dict]:
        """
        Get all people mentioned in a document.
        
        Args:
            document_id: Document UUID
            
        Returns:
            List of people dicts with normalized_name, display_name, role, context
        """
        rows = await db_service.fetch(
            """
            SELECT id, normalized_name, display_name, role, context
            FROM people_mentioned
            WHERE document_id = $1
            ORDER BY normalized_name
            """,
            document_id
        )
        
        return [
            {
                "id": str(row["id"]),
                "normalized_name": row["normalized_name"],
                "display_name": row["display_name"],
                "role": row["role"],
                "context": row["context"]
            }
            for row in rows
        ]
    
    async def get_qa_items_for_person(
        self,
        document_id: UUID,
        person_id: UUID
    ) -> List[Dict]:
        """
        Get all Q&A items mentioning a specific person.
        
        Args:
            document_id: Document UUID
            person_id: Person UUID from people_mentioned table
            
        Returns:
            List of Q&A item dicts with summaries
        """
        rows = await db_service.fetch(
            """
            SELECT 
                f.id,
                f.page_number,
                f.line_number,
                f.question,
                f.answer,
                f.summary,
                f.topics,
                f.event_date,
                qp.mention_context
            FROM final_qa_items f
            JOIN qa_people qp ON f.id = qp.qa_item_id
            WHERE f.document_id = $1 AND qp.people_id = $2
            ORDER BY f.page_number, f.line_number
            """,
            document_id,
            person_id
        )
        
        return [
            {
                "id": str(row["id"]),
                "page": row["page_number"],
                "line": row["line_number"],
                "question": row["question"],
                "answer": row["answer"],
                "summary": row["summary"],
                "topic": row["topic"],
                "event_date": row["event_date"],
                "mention_context": row["mention_context"]
            }
            for row in rows
        ]


# Global instance
people_extraction_service = PeopleExtractionService()

