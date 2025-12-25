"""Email notification service using SendGrid."""
import logging
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

from config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email notification service."""
    
    def __init__(self):
        self.client = None
        if settings.sendgrid_api_key:
            self.client = SendGridAPIClient(settings.sendgrid_api_key)
            logger.info("SendGrid email service initialized")
        else:
            logger.warning("SendGrid API key not configured - email notifications disabled")
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        from_email: Optional[str] = None
    ) -> bool:
        """Send an email via SendGrid."""
        if not self.client:
            logger.warning(f"Email not sent (SendGrid not configured): {to_email} - {subject}")
            return False
        
        try:
            from_email = from_email or settings.notification_from_email
            
            message = Mail(
                from_email=Email(from_email),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            response = self.client.send(message)
            logger.info(f"Email sent to {to_email}: {subject} (status: {response.status_code})")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)
            return False
    
    async def send_bug_report_notification(
        self,
        admin_email: str,
        user_name: str,
        user_email: str,
        report_title: str,
        report_id: str
    ) -> bool:
        """Send notification to admin when user submits bug report."""
        subject = f"New Bug Report: {report_title}"
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #4F46E5;">New Bug Report Submitted</h2>
                <p><strong>From:</strong> {user_name} ({user_email})</p>
                <p><strong>Title:</strong> {report_title}</p>
                <p>
                    <a href="{settings.frontend_url}/admin/chats/{report_id}" 
                       style="display: inline-block; padding: 10px 20px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 5px;">
                        View and Respond
                    </a>
                </p>
                <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
                <p style="color: #888; font-size: 12px;">
                    This is an automated notification from DepoDigest.
                </p>
            </body>
        </html>
        """
        
        return await self.send_email(admin_email, subject, html_content)
    
    async def send_chat_response_notification(
        self,
        user_email: str,
        user_name: str,
        report_title: str,
        report_id: str,
        admin_message: str
    ) -> bool:
        """Send notification to user when admin responds to their bug report."""
        subject = f"Response to: {report_title}"
        
        # Truncate message if too long
        message_preview = admin_message[:200] + "..." if len(admin_message) > 200 else admin_message
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #4F46E5;">Response to Your Bug Report</h2>
                <p>Hi {user_name},</p>
                <p>An admin has responded to your bug report: <strong>{report_title}</strong></p>
                <blockquote style="margin: 20px 0; padding: 15px; background-color: #f5f5f5; border-left: 4px solid #4F46E5;">
                    {message_preview}
                </blockquote>
                <p>
                    <a href="{settings.frontend_url}/bug-reports/{report_id}" 
                       style="display: inline-block; padding: 10px 20px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 5px;">
                        View Full Conversation
                    </a>
                </p>
                <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
                <p style="color: #888; font-size: 12px;">
                    This is an automated notification from DepoDigest.
                </p>
            </body>
        </html>
        """
        
        return await self.send_email(user_email, subject, html_content)


# Global email service instance
email_service = EmailService()






