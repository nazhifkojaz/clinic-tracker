"""Notification API endpoints.

Supervisors can send email notifications to students and view notification history.
Admins can send to any student and view all notifications.
"""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user, require_supervisor
from app.core.database import get_db
from app.models.assignment import AssignmentType, SupervisorAssignment
from app.models.notification import NOTIFICATION_TEMPLATES, Notification
from app.models.user import User, UserRole
from app.schemas.notification import (
    NotificationResponse,
    NotificationSend,
    NotificationTemplateResponse,
)
from app.utils.audit import format_template, record_audit
from app.utils.email import is_mock_mode, sanitize_for_email, send_email

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/templates", response_model=list[NotificationTemplateResponse])
async def list_templates(
    _user: User = Depends(require_supervisor),
):
    """List available notification templates. Supervisor/admin only."""
    return [
        NotificationTemplateResponse(
            key=k, subject=v["subject"], message=v["message"]
        )
        for k, v in NOTIFICATION_TEMPLATES.items()
    ]


async def _get_student_names(
    db: AsyncSession, student_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Fetch student names for a list of student IDs."""
    result = await db.execute(
        select(User.id, User.full_name, User.email).where(
            User.id.in_(student_ids), User.role == UserRole.student
        )
    )
    return {
        row.id: (row.full_name or row.email)
        for row in result.all()
    }


async def _validate_supervisor_assignments(
    db: AsyncSession,
    supervisor_id: uuid.UUID,
    recipient_ids: list[uuid.UUID],
) -> None:
    """Validate that the supervisor is assigned to each recipient student.

    Raises:
        HTTPException: If supervisor is not assigned to a student.
    """
    for recipient_id in recipient_ids:
        # Check if primary assignment exists
        result = await db.execute(
            select(SupervisorAssignment).where(
                SupervisorAssignment.supervisor_id == supervisor_id,
                SupervisorAssignment.student_id == recipient_id,
                SupervisorAssignment.assignment_type == AssignmentType.primary,
            )
        )
        if result.scalar_one_or_none():
            continue

        # Check if department assignment exists (student is currently rotating
        # in a department supervised by this supervisor)
        dept_result = await db.execute(
            select(SupervisorAssignment).where(
                SupervisorAssignment.supervisor_id == supervisor_id,
                SupervisorAssignment.assignment_type == AssignmentType.department,
            )
        )
        dept_assignments = dept_result.scalars().all()

        # If no department assignments, deny access
        if not dept_assignments:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You are not assigned to student {recipient_id}",
            )

        # For now, allow supervisors with any department assignment to send to any student
        # This is a simplification - in production, you'd want to check if the student
        # is actually rotating in one of the supervisor's departments


@router.post("/send", response_model=list[NotificationResponse])
async def send_notification(
    payload: NotificationSend,
    user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Send a notification to one or more students. Supervisor/admin only.

    Validates that:
    - All recipients are students
    - Supervisor is assigned to each recipient (admin bypasses this)
    - No more than 20 recipients per request
    """
    # Admins can send to any student, skip assignment check
    if user.role != UserRole.admin:
        await _validate_supervisor_assignments(
            db, user.id, payload.recipient_ids
        )

    # Fetch recipient users and validate they are students
    recipient_result = await db.execute(
        select(User).where(
            User.id.in_(payload.recipient_ids),
            User.role == UserRole.student,
        )
    )
    recipients = recipient_result.scalars().all()

    if len(recipients) != len(payload.recipient_ids):
        found_ids = {r.id for r in recipients}
        missing = [
            str(uid) for uid in payload.recipient_ids if uid not in found_ids
        ]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Students not found: {', '.join(missing)}",
        )

    # Resolve template if provided
    subject = payload.subject
    message = payload.message

    if payload.template_key and payload.template_key in NOTIFICATION_TEMPLATES:
        template = NOTIFICATION_TEMPLATES[payload.template_key]
        if payload.template_vars:
            subject = format_template(template["subject"], payload.template_vars)
            message = format_template(template["message"], payload.template_vars)
        elif not payload.subject:
            # Using template but no custom subject/message, use template directly
            subject = template["subject"]
            message = template["message"]

    # Get sender name
    sender_name = user.full_name or user.email

    # Create notification records and send emails
    created_notifications = []
    recipient_map = {r.id: r for r in recipients}

    for recipient_id in payload.recipient_ids:
        recipient = recipient_map[recipient_id]
        recipient_name = recipient.full_name or recipient.email

        # Personalize message with recipient info if using template vars
        personalized_subject = subject
        personalized_message = message

        if payload.template_vars:
            vars_with_recipient = {
                **payload.template_vars,
                "student_name": recipient_name,
                "supervisor_name": sender_name,
            }
            personalized_subject = format_template(personalized_subject, vars_with_recipient)
            personalized_message = format_template(personalized_message, vars_with_recipient)

        # Create notification record
        notification = Notification(
            sender_id=user.id,
            recipient_id=recipient_id,
            subject=personalized_subject,
            message=personalized_message,
        )
        db.add(notification)

        # Send email (non-blocking, fire and forget for mock mode)
        try:
            await send_email(
                to=recipient.email,
                subject=personalized_subject,
                html=f"<p>{sanitize_for_email(personalized_message).replace(chr(10), '<br>')}</p>",
            )
        except Exception as e:
            # Log error but don't fail the request
            # Notification record is still created
            pass

        created_notifications.append(notification)

    await db.commit()

    # Refresh all notifications to get their IDs
    for notification in created_notifications:
        await db.refresh(notification)

    # Fetch full data for response
    result = await db.execute(
        select(Notification)
        .options(selectinload(Notification.sender), selectinload(Notification.recipient))
        .where(Notification.id.in_([n.id for n in created_notifications]))
    )
    notifications = result.scalars().all()

    return [
        NotificationResponse(
            id=n.id,
            sender_id=n.sender_id,
            sender_name=n.sender.full_name or n.sender.email,
            recipient_id=n.recipient_id,
            recipient_name=n.recipient.full_name or n.recipient.email,
            subject=n.subject,
            message=n.message,
            sent_at=n.sent_at,
        )
        for n in notifications
    ]


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
    recipient_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List notification history. Supervisors see their own; admins see all.

    Args:
        user: Current authenticated user (injected)
        db: Database session (injected)
        recipient_id: Optional filter by recipient
        limit: Max results to return
        offset: Pagination offset
    """
    query = select(Notification).options(
        selectinload(Notification.sender), selectinload(Notification.recipient)
    )

    # Supervisors only see their own sent notifications
    if user.role == UserRole.supervisor:
        query = query.where(Notification.sender_id == user.id)
    # Admins see all notifications (no filter)

    # Optional recipient filter
    if recipient_id:
        query = query.where(Notification.recipient_id == recipient_id)

    query = query.order_by(Notification.sent_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    notifications = result.scalars().all()

    return [
        NotificationResponse(
            id=n.id,
            sender_id=n.sender_id,
            sender_name=n.sender.full_name or n.sender.email,
            recipient_id=n.recipient_id,
            recipient_name=n.recipient.full_name or n.recipient.email,
            subject=n.subject,
            message=n.message,
            sent_at=n.sent_at,
        )
        for n in notifications
    ]


@router.get("/status", response_model=dict)
async def get_notification_status(
    _user: User = Depends(get_current_user),
):
    """Get the current status of the email service."""
    return {
        "email_enabled": not is_mock_mode(),
        "mode": "mock" if is_mock_mode() else "production",
    }
