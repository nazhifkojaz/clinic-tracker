"""Notification helpers for profile change request lifecycle events."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.pending_profile_change import PendingProfileChange
from app.models.user import User, UserRole, display_name
from app.utils.email import sanitize_for_email, send_email

logger = logging.getLogger(__name__)


FIELD_LABELS: dict[str, str] = {
    "full_name": "Full Name",
    "institutional_id": "Institutional ID",
    "department_id": "Department",
    "email": "Email",
    "supervisor_id": "Academic Supervisor",
    "remove_student_id": "Remove Student",
}


async def notify_admins_new_request(
    db: AsyncSession,
    change: PendingProfileChange,
    user: User,
) -> None:
    """Notify all active admins of a new profile change request.

    Email failures are logged but never abort the caller's transaction.
    """
    result = await db.execute(
        select(User).where(User.role == UserRole.admin, User.is_active.is_(True))
    )
    admins = result.scalars().all()
    if not admins:
        return

    user_name = display_name(user)
    field_label = FIELD_LABELS.get(change.field_name, change.field_name)
    subject = f"New profile change request from {user_name}"
    message = (
        f"{user_name} has requested a change to their {field_label}. "
        f"Old value: {change.old_value}. New value: {change.new_value}."
    )

    for admin in admins:
        db.add(
            Notification(
                sender_id=user.id,
                recipient_id=admin.id,
                subject=subject,
                message=message,
            )
        )
    await db.commit()

    for admin in admins:
        admin_name = display_name(admin)
        html = f"""
    <p>Hi {sanitize_for_email(admin_name)},</p>
    <p>{sanitize_for_email(user_name)} has submitted a profile change request:</p>
    <ul>
      <li><strong>Field:</strong> {sanitize_for_email(field_label)}</li>
      <li><strong>Old value:</strong> {sanitize_for_email(change.old_value or "None")}</li>
      <li><strong>New value:</strong> {sanitize_for_email(change.new_value or "None")}</li>
    </ul>
    {"<p><strong>Reason:</strong> " + sanitize_for_email(change.reason) + "</p>" if change.reason else ""}
    <p>Please log in to Smart Clinic Tracker to review this request.</p>
    """
        try:
            await send_email(to=admin.email, subject=subject, html=html)
        except Exception:
            logger.exception(
                "Failed to email admin (id=%s) for profile change request %s",
                admin.id,
                change.id,
            )


async def notify_user_of_decision(
    db: AsyncSession,
    change: PendingProfileChange,
    user: User,
    reviewer: User,
) -> None:
    """Notify user that their profile change was approved or rejected.

    Email failures are logged but never abort the caller's transaction.
    """
    user_name = display_name(user)
    reviewer_name = display_name(reviewer)
    field_label = FIELD_LABELS.get(change.field_name, change.field_name)
    status_label = change.status.value  # "approved" or "rejected"
    status_color = "green" if status_label == "approved" else "red"

    subject = f"Your {field_label} change request has been {status_label}"
    message = (
        f"Your request to change {field_label} has been {status_label} "
        f"by {reviewer_name}."
    )
    db.add(
        Notification(
            sender_id=reviewer.id,
            recipient_id=user.id,
            subject=subject,
            message=message,
        )
    )
    await db.commit()

    html = f"""
    <p>Hi {sanitize_for_email(user_name)},</p>
    <p>Your request to change <strong>{sanitize_for_email(field_label)}</strong> has been
    <strong style="color:{status_color}">{status_label}</strong>
    by {sanitize_for_email(reviewer_name)}.</p>
    <ul>
      <li><strong>Old value:</strong> {sanitize_for_email(change.old_value or "None")}</li>
      <li><strong>New value:</strong> {sanitize_for_email(change.new_value or "None")}</li>
    </ul>
    <p>Log in to Smart Clinic Tracker to view the details.</p>
    """
    try:
        await send_email(to=user.email, subject=subject, html=html)
    except Exception:
        logger.exception(
            "Failed to email user (id=%s) for profile change %s decision",
            user.id,
            change.id,
        )
