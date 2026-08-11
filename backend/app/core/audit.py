import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger("audit")


class AuditAction(str, Enum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"

    FILE_UPLOAD = "FILE_UPLOAD"
    FILE_UPLOAD_REJECTED = "FILE_UPLOAD_REJECTED"
    FILE_DELETE = "FILE_DELETE"

    REPORT_GENERATE = "REPORT_GENERATE"
    REPORT_DOWNLOAD = "REPORT_DOWNLOAD"

    USER_CREATE = "USER_CREATE"
    USER_UPDATE = "USER_UPDATE"
    USER_DELETE = "USER_DELETE"
    USER_ROLE_CHANGE = "USER_ROLE_CHANGE"

    WORKFLOW_CONFIG_UPDATE = "WORKFLOW_CONFIG_UPDATE"
    SYSTEM_CONFIG_UPDATE = "SYSTEM_CONFIG_UPDATE"


class AuditEntry(BaseModel):
    timestamp: datetime
    action: AuditAction
    user_id: str | None
    username: str | None
    ip_address: str | None
    user_agent: str | None
    resource_type: str | None
    resource_id: str | None
    details: dict[str, Any] | None
    success: bool


class AuditLogger:
    def log(
        self,
        action: AuditAction,
        *,
        user_id: str | None = None,
        username: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        success: bool = True,
    ) -> AuditEntry:
        entry = AuditEntry(
            timestamp=datetime.now(UTC),
            action=action,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            details=self._sanitize_details(details),
            success=success,
        )

        log_method = logger.info if success else logger.warning
        log_method(
            "AUDIT: %s | user=%s | ip=%s | resource=%s/%s | success=%s",
            action.value,
            username or user_id or "anonymous",
            ip_address or "unknown",
            resource_type or "-",
            resource_id or "-",
            success,
            extra={"audit": entry.model_dump(mode="json")},
        )

        return entry

    def _sanitize_details(self, details: dict[str, Any] | None) -> dict[str, Any] | None:
        if not details:
            return None

        sensitive_keys = {"password", "token", "secret", "key", "authorization"}
        sanitized = {}

        for key, value in details.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value

        return sanitized

    def log_login(
        self,
        username: str,
        ip_address: str | None,
        user_agent: str | None,
        success: bool,
        user_id: str | None = None,
        failure_reason: str | None = None,
    ) -> AuditEntry:
        action = AuditAction.LOGIN_SUCCESS if success else AuditAction.LOGIN_FAILURE
        details = {"failure_reason": failure_reason} if failure_reason else None

        return self.log(
            action,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            success=success,
        )

    def log_upload(
        self,
        user_id: str,
        username: str,
        filename: str,
        file_size: int,
        ip_address: str | None,
        success: bool,
        rejection_reason: str | None = None,
    ) -> AuditEntry:
        action = AuditAction.FILE_UPLOAD if success else AuditAction.FILE_UPLOAD_REJECTED
        details = {
            "filename": filename,
            "file_size": file_size,
        }
        if rejection_reason:
            details["rejection_reason"] = rejection_reason

        return self.log(
            action,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            resource_type="file",
            resource_id=filename,
            details=details,
            success=success,
        )

    def log_report_generation(
        self,
        user_id: str,
        username: str,
        workflow_id: str,
        ip_address: str | None,
        success: bool,
    ) -> AuditEntry:
        return self.log(
            AuditAction.REPORT_GENERATE,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            resource_type="workflow",
            resource_id=workflow_id,
            success=success,
        )


audit_logger = AuditLogger()
