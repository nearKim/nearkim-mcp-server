from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import partial
from typing import Optional

logger = logging.getLogger(__name__)


class EmailService:
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str,
        to_email: str,
        enabled: bool = True
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.to_email = to_email
        self.enabled = enabled
    
    async def send_error_notification(
        self,
        task_id: str,
        task_content: str,
        error: Exception,
        error_detail: Optional[str] = None
    ) -> None:
        if not self.enabled:
            logger.debug("Email notifications disabled, skipping")
            return
        
        subject = f"[Eisenhower MCP] Classification Error for Task {task_id}"
        
        html_body = f"""
        <html>
            <body>
                <h2>Task Classification Error</h2>
                <p><strong>Task ID:</strong> {task_id}</p>
                <p><strong>Task Content:</strong> {task_content}</p>
                <p><strong>Error Type:</strong> {type(error).__name__}</p>
                <p><strong>Error Message:</strong> {str(error)}</p>
                {f'<p><strong>Details:</strong> {error_detail}</p>' if error_detail else ''}
                <hr>
                <p><em>This task has been labeled with 'error' for manual review.</em></p>
            </body>
        </html>
        """
        
        text_body = f"""
        Task Classification Error
        
        Task ID: {task_id}
        Task Content: {task_content}
        Error Type: {type(error).__name__}
        Error Message: {str(error)}
        {'Details: ' + error_detail if error_detail else ''}
        
        This task has been labeled with 'error' for manual review.
        """
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = self.to_email
            
            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))
            
            # Run blocking SMTP operation in thread executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                partial(self._send_email_sync, msg)
            )
            
            logger.info(f"Error notification sent for task {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
    
    async def send_batch_error_summary(
        self,
        error_count: int,
        total_tasks: int,
        errors: list[tuple[str, str, Exception]]
    ) -> None:
        if not self.enabled or error_count == 0:
            return
        
        subject = f"[Eisenhower MCP] {error_count} Classification Errors Detected"
        
        error_rows = "\n".join([
            f"<tr><td>{task_id}</td><td>{task_content[:50]}...</td><td>{type(error).__name__}</td></tr>"
            for task_id, task_content, error in errors[:10]
        ])
        
        html_body = f"""
        <html>
            <body>
                <h2>Classification Error Summary</h2>
                <p><strong>Total Tasks Processed:</strong> {total_tasks}</p>
                <p><strong>Errors Encountered:</strong> {error_count}</p>
                <p><strong>Success Rate:</strong> {((total_tasks - error_count) / total_tasks * 100):.1f}%</p>
                
                <h3>Recent Errors (up to 10):</h3>
                <table border="1" cellpadding="5">
                    <thead>
                        <tr>
                            <th>Task ID</th>
                            <th>Content</th>
                            <th>Error Type</th>
                        </tr>
                    </thead>
                    <tbody>
                        {error_rows}
                    </tbody>
                </table>
                
                <hr>
                <p><em>All failed tasks have been labeled with 'error' for manual review.</em></p>
            </body>
        </html>
        """
        
        try:
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = self.to_email
            msg.attach(MIMEText(html_body, 'html'))
            
            # Run blocking SMTP operation in thread executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                partial(self._send_email_sync, msg)
            )
            
            logger.info(f"Batch error summary sent: {error_count} errors")
            
        except Exception as e:
            logger.error(f"Failed to send batch error summary: {e}")
    
    def _send_email_sync(self, msg: MIMEMultipart) -> None:
        """Synchronous email sending to be run in thread executor."""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)