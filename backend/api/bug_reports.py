"""Bug reports and chat API endpoints."""
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from uuid import UUID

from api.auth import get_current_user, require_admin, User
from services.db_service import persistent_db_service
from services.email_service import email_service
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class BugReportCreate(BaseModel):
    """Bug report creation model."""
    title: str
    message: str
    type: str = "bug"  # 'bug' or 'feature'


class ChatMessageCreate(BaseModel):
    """Chat message creation model."""
    bug_report_id: str
    message: str


class ChatMessage(BaseModel):
    """Chat message model."""
    id: str
    bug_report_id: str
    sender_id: str
    sender_name: str
    sender_picture: Optional[str]
    message: str
    screenshot_url: Optional[str]
    is_admin_message: bool
    read_at: Optional[datetime]
    created_at: datetime


class BugReport(BaseModel):
    """Bug report model."""
    id: str
    user_id: str
    user_name: str
    user_email: str
    title: str
    type: str
    status: str
    created_at: datetime
    updated_at: datetime
    unread_count: int = 0
    last_message: Optional[str] = None


class BugReportDetail(BaseModel):
    """Bug report with messages."""
    id: str
    user_id: str
    user_name: str
    user_email: str
    title: str
    type: str
    status: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessage]


@router.post("/bug-reports", response_model=BugReport)
async def create_bug_report(
    report: BugReportCreate,
    user: User = Depends(get_current_user)
):
    """Create a new bug report."""
    try:
        # Create bug report
        bug_report = await persistent_db_service.fetchrow(
            """
            INSERT INTO bug_reports (user_id, title, type, status)
            VALUES ($1, $2, $3, 'open')
            RETURNING id, user_id, title, type, status, created_at, updated_at
            """,
            user.id, report.title, report.type
        )
        
        # Add first message
        await persistent_db_service.execute(
            """
            INSERT INTO chat_messages (bug_report_id, sender_id, message, is_admin_message)
            VALUES ($1, $2, $3, FALSE)
            """,
            str(bug_report['id']), user.id, report.message
        )
        
        # Send email notification to admin
        await email_service.send_bug_report_notification(
            admin_email=settings.admin_email,
            user_name=user.name or user.email,
            user_email=user.email,
            report_title=report.title,
            report_id=str(bug_report['id'])
        )
        
        logger.info(f"Bug report created: {bug_report['id']} by {user.email}")
        
        return BugReport(
            id=str(bug_report['id']),
            user_id=str(bug_report['user_id']),
            user_name=user.name or user.email,
            user_email=user.email,
            title=bug_report['title'],
            type=bug_report['type'],
            status=bug_report['status'],
            created_at=bug_report['created_at'],
            updated_at=bug_report['updated_at'],
            unread_count=0,
            last_message=report.message
        )
    
    except Exception as e:
        logger.error(f"Failed to create bug report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create bug report")


@router.get("/bug-reports", response_model=List[BugReport])
async def list_bug_reports(
    status: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    """List bug reports. Admin sees all, users see only their own."""
    try:
        if user.is_admin:
            # Admin sees all reports
            query = """
                SELECT 
                    br.id, br.user_id, br.title, br.type, br.status, br.created_at, br.updated_at,
                    u.name as user_name, u.email as user_email,
                    (SELECT COUNT(*) FROM chat_messages cm 
                     WHERE cm.bug_report_id = br.id AND cm.is_admin_message = FALSE AND cm.read_at IS NULL) as unread_count,
                    (SELECT message FROM chat_messages cm 
                     WHERE cm.bug_report_id = br.id ORDER BY created_at DESC LIMIT 1) as last_message
                FROM bug_reports br
                JOIN users u ON br.user_id = u.id
            """
            params = []
            if status:
                query += " WHERE br.status = $1"
                params.append(status)
            query += " ORDER BY br.updated_at DESC"
            
            reports = await persistent_db_service.fetch(query, *params)
        else:
            # Users see only their reports
            query = """
                SELECT 
                    br.id, br.user_id, br.title, br.type, br.status, br.created_at, br.updated_at,
                    u.name as user_name, u.email as user_email,
                    (SELECT COUNT(*) FROM chat_messages cm 
                     WHERE cm.bug_report_id = br.id AND cm.is_admin_message = TRUE AND cm.read_at IS NULL) as unread_count,
                    (SELECT message FROM chat_messages cm 
                     WHERE cm.bug_report_id = br.id ORDER BY created_at DESC LIMIT 1) as last_message
                FROM bug_reports br
                JOIN users u ON br.user_id = u.id
                WHERE br.user_id = $1
            """
            params = [user.id]
            if status:
                query += " AND br.status = $2"
                params.append(status)
            query += " ORDER BY br.updated_at DESC"
            
            reports = await persistent_db_service.fetch(query, *params)
        
        return [
            BugReport(
                id=str(r['id']),
                user_id=str(r['user_id']),
                user_name=r['user_name'] or r['user_email'],
                user_email=r['user_email'],
                title=r['title'],
                type=r['type'],
                status=r['status'],
                created_at=r['created_at'],
                updated_at=r['updated_at'],
                unread_count=r['unread_count'] or 0,
                last_message=r['last_message']
            )
            for r in reports
        ]
    
    except Exception as e:
        logger.error(f"Failed to list bug reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list bug reports")


@router.get("/bug-reports/{report_id}", response_model=BugReportDetail)
async def get_bug_report(
    report_id: str,
    user: User = Depends(get_current_user)
):
    """Get bug report with messages."""
    try:
        # Get bug report
        report = await persistent_db_service.fetchrow(
            """
            SELECT br.*, u.name as user_name, u.email as user_email
            FROM bug_reports br
            JOIN users u ON br.user_id = u.id
            WHERE br.id = $1
            """,
            report_id
        )
        
        if not report:
            raise HTTPException(status_code=404, detail="Bug report not found")
        
        # Check access permissions
        if not user.is_admin and str(report['user_id']) != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get messages
        messages = await persistent_db_service.fetch(
            """
            SELECT cm.*, u.name as sender_name, u.picture as sender_picture
            FROM chat_messages cm
            JOIN users u ON cm.sender_id = u.id
            WHERE cm.bug_report_id = $1
            ORDER BY cm.created_at ASC
            """,
            report_id
        )
        
        # Mark messages as read
        if user.is_admin:
            # Admin marks user messages as read
            await persistent_db_service.execute(
                """
                UPDATE chat_messages 
                SET read_at = NOW() 
                WHERE bug_report_id = $1 AND is_admin_message = FALSE AND read_at IS NULL
                """,
                report_id
            )
        else:
            # User marks admin messages as read
            await persistent_db_service.execute(
                """
                UPDATE chat_messages 
                SET read_at = NOW() 
                WHERE bug_report_id = $1 AND is_admin_message = TRUE AND read_at IS NULL
                """,
                report_id
            )
        
        return BugReportDetail(
            id=str(report['id']),
            user_id=str(report['user_id']),
            user_name=report['user_name'] or report['user_email'],
            user_email=report['user_email'],
            title=report['title'],
            type=report['type'],
            status=report['status'],
            created_at=report['created_at'],
            updated_at=report['updated_at'],
            messages=[
                ChatMessage(
                    id=str(m['id']),
                    bug_report_id=str(m['bug_report_id']),
                    sender_id=str(m['sender_id']),
                    sender_name=m['sender_name'] or 'Unknown',
                    sender_picture=m['sender_picture'],
                    message=m['message'],
                    screenshot_url=m['screenshot_url'],
                    is_admin_message=m['is_admin_message'],
                    read_at=m['read_at'],
                    created_at=m['created_at']
                )
                for m in messages
            ]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get bug report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get bug report")


@router.post("/bug-reports/{report_id}/messages", response_model=ChatMessage)
async def send_message(
    report_id: str,
    message: ChatMessageCreate,
    user: User = Depends(get_current_user)
):
    """Send a message in a bug report chat."""
    try:
        # Verify bug report exists and user has access
        report = await persistent_db_service.fetchrow(
            "SELECT user_id FROM bug_reports WHERE id = $1",
            report_id
        )
        
        if not report:
            raise HTTPException(status_code=404, detail="Bug report not found")
        
        if not user.is_admin and str(report['user_id']) != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Create message
        msg = await persistent_db_service.fetchrow(
            """
            INSERT INTO chat_messages (bug_report_id, sender_id, message, is_admin_message)
            VALUES ($1, $2, $3, $4)
            RETURNING id, bug_report_id, sender_id, message, screenshot_url, is_admin_message, read_at, created_at
            """,
            report_id, user.id, message.message, user.is_admin
        )
        
        # Update bug report updated_at
        await persistent_db_service.execute(
            "UPDATE bug_reports SET updated_at = NOW() WHERE id = $1",
            report_id
        )
        
        # Send email notification
        if user.is_admin:
            # Admin sent message, notify user
            report_user = await persistent_db_service.fetchrow(
                "SELECT u.email, u.name FROM users u JOIN bug_reports br ON u.id = br.user_id WHERE br.id = $1",
                report_id
            )
            if report_user:
                report_title = await persistent_db_service.fetchval(
                    "SELECT title FROM bug_reports WHERE id = $1",
                    report_id
                )
                await email_service.send_chat_response_notification(
                    user_email=report_user['email'],
                    user_name=report_user['name'] or report_user['email'],
                    report_title=report_title,
                    report_id=report_id,
                    admin_message=message.message
                )
        
        return ChatMessage(
            id=str(msg['id']),
            bug_report_id=str(msg['bug_report_id']),
            sender_id=str(msg['sender_id']),
            sender_name=user.name or user.email,
            sender_picture=user.picture,
            message=msg['message'],
            screenshot_url=msg['screenshot_url'],
            is_admin_message=msg['is_admin_message'],
            read_at=msg['read_at'],
            created_at=msg['created_at']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.post("/bug-reports/{report_id}/screenshot")
async def upload_screenshot(
    report_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user)
):
    """Upload screenshot for bug report."""
    try:
        # Verify bug report exists and user has access
        report = await persistent_db_service.fetchrow(
            "SELECT user_id FROM bug_reports WHERE id = $1",
            report_id
        )
        
        if not report:
            raise HTTPException(status_code=404, detail="Bug report not found")
        
        if not user.is_admin and str(report['user_id']) != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Upload to S3
        file_content = await file.read()
        s3_key = f"bug-reports/{report_id}/{file.filename}"
        
        # TODO: Implement S3 upload (reuse existing upload_to_s3 function)
        # For now, return a placeholder
        screenshot_url = f"https://s3.amazonaws.com/depodigest-uploads/{s3_key}"
        
        return {"screenshot_url": screenshot_url}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload screenshot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload screenshot")


@router.patch("/bug-reports/{report_id}/status")
async def update_status(
    report_id: str,
    status: str,
    admin: User = Depends(require_admin)
):
    """Update bug report status (admin only)."""
    try:
        await persistent_db_service.execute(
            "UPDATE bug_reports SET status = $2, updated_at = NOW() WHERE id = $1",
            report_id, status
        )
        
        return {"message": "Status updated successfully"}
    
    except Exception as e:
        logger.error(f"Failed to update status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update status")

