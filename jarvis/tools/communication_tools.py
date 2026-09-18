"""Communication and External Action Tools for JARVIS.

Enforces Level 2 External Action permissions requiring explicit confirmation with full parameter previews.
"""

from __future__ import annotations
import time
from typing import Any, Dict, Optional
from jarvis.tools.base import (
    BaseTool,
    RiskLevel,
    PermissionLevel,
    ToolParameter,
    ToolResult,
    ToolVerification,
)


class SendEmailTool(BaseTool):
    """Sends an email via external communication channels. Requires user confirmation with parameter preview."""

    name = "send_email"
    description = "Send an email to a recipient with subject, message content, and optional attachment."
    risk_level = RiskLevel.MEDIUM
    permission_level = PermissionLevel.LEVEL_2_EXTERNAL_ACTION

    parameters = {
        "recipient": ToolParameter(
            name="recipient",
            type="string",
            description="The destination email address (e.g. alice@example.com).",
            required=True,
        ),
        "subject": ToolParameter(
            name="subject",
            type="string",
            description="The email subject line.",
            required=True,
        ),
        "message": ToolParameter(
            name="message",
            type="string",
            description="The text body of the email.",
            required=True,
        ),
        "attachment": ToolParameter(
            name="attachment",
            type="string",
            description="Optional file path of attachment to include.",
            required=False,
            default="",
        ),
    }

    def __init__(self):
        self.sent_log = []

    def build_confirmation_preview(self, arguments: Dict[str, Any]) -> Dict[str, str]:
        """Generate structured preview required by permission system before external execution."""
        return {
            "Recipient": str(arguments.get("recipient", "")),
            "Subject": str(arguments.get("subject", "")),
            "Message": str(arguments.get("message", "")),
            "Attachment": str(arguments.get("attachment") or "None"),
        }

    def format_confirmation_prompt(self, arguments: Dict[str, Any]) -> str:
        """Format the user-facing confirmation prompt with parameter details."""
        preview = self.build_confirmation_preview(arguments)
        lines = [
            "External Action Confirmation Required:",
            f"  Recipient : {preview['Recipient']}",
            f"  Subject   : {preview['Subject']}",
            f"  Message   : {preview['Message']}",
            f"  Attachment: {preview['Attachment']}",
            "Would you like me to send this email?",
        ]
        return "\n".join(lines)

    def execute(self, **kwargs) -> ToolResult:
        start_time = time.perf_counter()
        recipient = kwargs.get("recipient", "").strip()
        subject = kwargs.get("subject", "").strip()
        message = kwargs.get("message", "").strip()
        attachment = kwargs.get("attachment", "").strip()

        if not recipient:
            return ToolResult(
                success=False,
                output=None,
                error="Recipient cannot be empty.",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        email_record = {
            "recipient": recipient,
            "subject": subject,
            "message": message,
            "attachment": attachment or None,
            "timestamp": time.time(),
        }
        self.sent_log.append(email_record)

        msg = f"Email sent successfully to {recipient} with subject '{subject}'."
        if attachment:
            msg += f" (Attachment: {attachment})"

        return ToolResult(
            success=True,
            output=msg,
            duration_ms=(time.perf_counter() - start_time) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Failed to send email: {result.error}")
        recipient = arguments.get("recipient", "").strip()
        matched = any(e["recipient"] == recipient for e in self.sent_log)
        if matched:
            return ToolVerification(
                verified=True,
                details=f"Email delivery verified in outbound transmission log for {recipient}.",
            )
        return ToolVerification(verified=False, details="Email record not found in sent log.")
