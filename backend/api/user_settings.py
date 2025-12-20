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

