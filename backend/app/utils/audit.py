"""Audit log recording helper.

Call record_audit() from route handlers after state-changing operations
to create an audit trail of who changed what, when.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


def _serialize_value(value: Any) -> Any:
    """Convert a value to a JSON-safe representation.

    Handles UUIDs, datetime objects, and enums.
    """
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "isoformat"):  # datetime, date
        return value.isoformat()
    if hasattr(value, "value"):  # enum
        return value.value
    if isinstance(value, bytes):
        return "<bytes>"  # Don't include binary data in audit logs
    return value


def _sanitize_dict(d: dict | None) -> dict | None:
    """Remove sensitive fields from a dict before storing in audit log.

    Currently filters out password_hash.
    """
    if d is None:
        return None

    SENSITIVE_KEYS = {"password_hash", "password"}

    return {k: _serialize_value(v) for k, v in d.items() if k not in SENSITIVE_KEYS}


def _serialize_dict(d: dict | None) -> dict | None:
    """Convert a dict to JSON-safe representation."""
    if d is None:
        return None
    return {k: _serialize_value(v) for k, v in d.items()}


async def record_audit(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    action: str,
    table_name: str,
    record_id: uuid.UUID,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> None:
    """Record an audit log entry.

    Call AFTER the main db.commit() for the action being audited.

    Args:
        db: Database session
        user_id: ID of the user who made the change
        action: Type of action ("create", "update", "delete")
        table_name: Name of the affected table
        record_id: ID of the affected record
        old_values: Dictionary of old field values (for update/delete)
        new_values: Dictionary of new field values (for create/update)
    """
    # For certain tables, sanitize sensitive data
    if table_name == "users":
        old_values = _sanitize_dict(old_values)
        new_values = _sanitize_dict(new_values)
    else:
        old_values = _serialize_dict(old_values)
        new_values = _serialize_dict(new_values)

    entry = AuditLog(
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=old_values,
        new_values=new_values,
    )
    db.add(entry)
    await db.commit()


class DefaultDict(dict):
    """Dict that returns the key itself for missing values."""

    def __missing__(self, key):
        return f"{{{key}}}"


def format_template(template: str, variables: dict[str, str]) -> str:
    """Format a template string with variables.

    Missing variables are rendered as placeholders.
    """
    return template.format_map(DefaultDict(variables))
