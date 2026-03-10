"""Audit log API endpoints.

Admins can view a filterable, paginated audit trail of data modifications.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/api/admin/audit-logs", tags=["audit"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    table_name: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List audit logs with optional filters. Admin only.

    Args:
        _admin: Current authenticated admin user (injected)
        db: Database session (injected)
        user_id: Filter by user who made the change
        action: Filter by action type (create, update, delete)
        table_name: Filter by affected table
        date_from: Filter to entries after this date
        date_to: Filter to entries before this date
        limit: Max results to return
        offset: Pagination offset
    """
    # Build base query with user join for user_name
    base_query = select(AuditLog, User.full_name).outerjoin(
        User, AuditLog.user_id == User.id
    )

    # Apply filters
    if user_id:
        base_query = base_query.where(AuditLog.user_id == user_id)
    if action:
        base_query = base_query.where(AuditLog.action == action)
    if table_name:
        base_query = base_query.where(AuditLog.table_name == table_name)
    if date_from:
        base_query = base_query.where(AuditLog.created_at >= date_from)
    if date_to:
        base_query = base_query.where(AuditLog.created_at <= date_to)

    # Count total matching records
    count_subquery = base_query.subquery()
    count_query = select(func.count()).select_from(count_subquery)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Fetch paginated results
    query = base_query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    results = await db.execute(query)
    rows = results.all()

    # Build response items
    items = [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            user_name=user_name,
            action=log.action,
            table_name=log.table_name,
            record_id=log.record_id,
            old_values=log.old_values,
            new_values=log.new_values,
            created_at=log.created_at,
        )
        for log, user_name in rows
    ]

    return AuditLogListResponse(items=items, total=total)


@router.get("/metadata", response_model=dict)
async def get_audit_metadata(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get metadata for audit log filters. Admin only.

    Returns distinct values for action, table_name, etc. to populate filter dropdowns.
    """
    # Get distinct actions
    actions_result = await db.execute(
        select(AuditLog.action).distinct().order_by(AuditLog.action)
    )
    actions = [row[0] for row in actions_result.all()]

    # Get distinct table names
    tables_result = await db.execute(
        select(AuditLog.table_name).distinct().order_by(AuditLog.table_name)
    )
    tables = [row[0] for row in tables_result.all()]

    return {
        "actions": actions,
        "table_names": tables,
    }
