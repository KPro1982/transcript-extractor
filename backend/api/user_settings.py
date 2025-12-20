"""User prompt settings API endpoints."""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from api.auth import get_current_user, User
from services.db_service import persistent_db_service

logger = logging.getLogger(__name__)

router = APIRouter()


class UserPromptSettingsUpdate(BaseModel):
    """User prompt settings update model."""
    preset_options: Optional[Dict[str, bool]] = None
    custom_instructions: Optional[str] = None


class UserPromptSettings(BaseModel):
    """User prompt settings model."""
    user_id: str
    preset_options: Dict[str, bool]
    custom_instructions: Optional[str]
    updated_at: str


class PromptPreview(BaseModel):
    """Preview of the generated prompt with user settings."""
    system_prompt: str
    user_settings_applied: Dict


@router.get("/user-settings/prompts", response_model=UserPromptSettings)
async def get_user_prompt_settings(user: User = Depends(get_current_user)):
    """Get user's prompt settings."""
    try:
        settings = await persistent_db_service.fetchrow(
            """
            SELECT user_id, preset_options, custom_instructions, updated_at
            FROM user_prompt_settings
            WHERE user_id = $1
            """,
            user.id
        )
        
        if not settings:
            # Return default settings
            return UserPromptSettings(
                user_id=user.id,
                preset_options={},
                custom_instructions=None,
                updated_at=""
            )
        
        return UserPromptSettings(
            user_id=str(settings['user_id']),
            preset_options=settings['preset_options'] or {},
            custom_instructions=settings['custom_instructions'],
            updated_at=str(settings['updated_at'])
        )
    
    except Exception as e:
        logger.error(f"Failed to get user prompt settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get settings")


@router.put("/user-settings/prompts", response_model=UserPromptSettings)
async def update_user_prompt_settings(
    settings_update: UserPromptSettingsUpdate,
    user: User = Depends(get_current_user)
):
    """Update user's prompt settings."""
    try:
        # Check if settings exist
        existing = await persistent_db_service.fetchrow(
            "SELECT id FROM user_prompt_settings WHERE user_id = $1",
            user.id
        )
        
        if existing:
            # Update existing settings
            result = await persistent_db_service.fetchrow(
                """
                UPDATE user_prompt_settings
                SET preset_options = $2, custom_instructions = $3, updated_at = NOW()
                WHERE user_id = $1
                RETURNING user_id, preset_options, custom_instructions, updated_at
                """,
                user.id,
                settings_update.preset_options or {},
                settings_update.custom_instructions
            )
        else:
            # Create new settings
            result = await persistent_db_service.fetchrow(
                """
                INSERT INTO user_prompt_settings (user_id, preset_options, custom_instructions)
                VALUES ($1, $2, $3)
                RETURNING user_id, preset_options, custom_instructions, updated_at
                """,
                user.id,
                settings_update.preset_options or {},
                settings_update.custom_instructions
            )
        
        logger.info(f"User prompt settings updated for {user.email}")
        
        return UserPromptSettings(
            user_id=str(result['user_id']),
            preset_options=result['preset_options'] or {},
            custom_instructions=result['custom_instructions'],
            updated_at=str(result['updated_at'])
        )
    
    except Exception as e:
        logger.error(f"Failed to update user prompt settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update settings")


@router.get("/user-settings/prompt-preview", response_model=PromptPreview)
async def get_prompt_preview(user: User = Depends(get_current_user)):
    """
    Get a preview of the system prompt with user's settings applied.
    Shows what prompt will be sent to the AI for summarization.
    """
    try:
        # Get user's settings
        settings = await persistent_db_service.fetchrow(
            """
            SELECT preset_options, custom_instructions
            FROM user_prompt_settings
            WHERE user_id = $1
            """,
            user.id
        )
        
        preset_options = settings['preset_options'] if settings else {}
        custom_instructions = settings['custom_instructions'] if settings else None
        
        # Build the prompt preview (same logic as OpenAI provider)
        additional_instructions = ""
        if preset_options:
            additional_instructions += "\n\nUser preferences:"
            if preset_options.get("witness_last_name"):
                additional_instructions += "\n- Refer to witnesses by last name only"
            if preset_options.get("exclude_colloquy"):
                additional_instructions += "\n- Exclude non-substantive colloquy and attorney dialogue"
            if preset_options.get("factual_only"):
                additional_instructions += "\n- Focus exclusively on factual testimony, not opinions or speculation"
            if preset_options.get("include_objections"):
                additional_instructions += "\n- Include context about objections and their outcomes"
            if preset_options.get("chronological_order"):
                additional_instructions += "\n- Maintain strict chronological order of events"
            if preset_options.get("highlight_inconsistencies"):
                additional_instructions += "\n- Note any contradictions or changes in testimony"
        
        if custom_instructions:
            additional_instructions += f"\n\nAdditional custom instructions from user:\n{custom_instructions}"
        
        # Base system prompt
        base_prompt = """You are a legal assistant analyzing deposition testimony.

You will receive NUMBERED Q&A exchanges. You MUST provide a SEPARATE summary for EACH numbered item.

CRITICAL REQUIREMENTS:
1. You will receive numbered Q&A pairs (numbered 1 through N)
2. You MUST return EXACTLY N summaries - one for each numbered input
3. The "results" array MUST contain EXACTLY N objects - NO MORE, NO LESS
4. DO NOT skip any numbered items
5. DO NOT combine multiple Q&A into one summary
6. Each object must have: {"summary": "...", "topic": "..."}

Summary rules:
- Transform each Q&A into a narrative statement (DO NOT repeat the question)
- Use third person: "The witness testified that..."
- Be concise: 1-2 sentences per summary
- Each summary must be unique and specific to its Q&A pair"""
        
        full_prompt = base_prompt + additional_instructions
        
        full_prompt += "\n\nTopics (pick one per Q&A): Background & Education, Employment History, Incident Description, Medical Treatment, Damages & Injuries, Timeline & Chronology, Documents & Evidence, Witness Statements, Expert Opinions, Other"
        
        return PromptPreview(
            system_prompt=full_prompt,
            user_settings_applied={
                "preset_options": preset_options or {},
                "custom_instructions": custom_instructions
            }
        )
    
    except Exception as e:
        logger.error(f"Failed to generate prompt preview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate prompt preview")


