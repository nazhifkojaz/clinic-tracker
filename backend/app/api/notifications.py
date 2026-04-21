"""Notification API endpoints.

Supervisors and admins can view notification history.
Notifications are created automatically by the submission workflow.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import require_supervisor
from app.core.database import get_db
from app.models.notification import Notification
from app.models.user import User, UserRole, display_name
from app.schemas.notification import NotificationResponse

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
    recipient_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List notification history. Supervisors see their own; admins see all."""
    query = select(Notification).options(
        selectinload(Notification.sender), selectinload(Notification.recipient)
    )

    if user.role == UserRole.supervisor:
        query = query.where(Notification.sender_id == user.id)

    if recipient_id:
        query = query.where(Notification.recipient_id == recipient_id)

    query = query.order_by(Notification.sent_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    notifications = result.scalars().all()

    return [
        NotificationResponse(
            id=n.id,
            sender_id=n.sender_id,
            sender_name=display_name(n.sender),
            recipient_id=n.recipient_id,
            recipient_name=display_name(n.recipient),
            subject=n.subject,
            message=n.message,
            sent_at=n.sent_at,
        )
        for n in notifications
    ]
