"""Daily rotation reminder scheduler.

Finds students past 50% rotation time with < 60% case progress
and sends a reminder email + creates a Notification record.
Cooldown: once per 7 days per student per department (via last_reminder_sent).
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.database import async_session_maker
from app.models.department import Department, TaskCategory
from app.models.notification import Notification
from app.models.rotation import StudentRotation
from app.models.submission import CaseSubmission, SubmissionStatus
from app.models.user import User, UserRole, display_name
from app.utils.email import sanitize_for_email, send_email

logger = logging.getLogger(__name__)

REMINDER_SUBJECT_PREFIX = "[Rotation Reminder]"


async def _get_system_sender_id(db) -> str | None:
    """Get the first active admin user ID to use as system notification sender."""
    result = await db.execute(
        select(User.id)
        .where(User.role == UserRole.admin, User.is_active.is_(True))
        .limit(1)
    )
    row = result.first()
    return row[0] if row else None


async def run_rotation_reminders() -> None:
    """Core job logic. Called by APScheduler at 5 AM daily."""
    logger.info("Running daily rotation reminder job")
    async with async_session_maker() as db:
        try:
            now = datetime.now(timezone.utc)
            seven_days_ago = now - timedelta(days=7)

            # 1. Get all current rotations with department info
            rot_result = await db.execute(
                select(StudentRotation, Department)
                .join(Department, StudentRotation.department_id == Department.id)
                .where(
                    StudentRotation.is_current.is_(True),
                    Department.is_active.is_(True),
                )
            )
            rows = rot_result.all()

            if not rows:
                logger.info("No current rotations found, skipping")
                return

            # 2. Build required counts per department
            cat_result = await db.execute(
                select(
                    TaskCategory.department_id,
                    func.sum(TaskCategory.required_count).label("total_required"),
                )
                .where(TaskCategory.is_active.is_(True))
                .group_by(TaskCategory.department_id)
            )
            required_map: dict[str, int] = {
                str(row.department_id): int(row.total_required)
                for row in cat_result.all()
            }

            # 3. Build approved counts per (student, department)
            student_ids = list({str(rot.student_id) for rot, _ in rows})
            dept_ids = list({str(rot.department_id) for rot, _ in rows})

            from uuid import UUID

            sub_result = await db.execute(
                select(
                    CaseSubmission.student_id,
                    CaseSubmission.department_id,
                    func.sum(CaseSubmission.case_count).label("approved"),
                )
                .where(
                    CaseSubmission.student_id.in_([UUID(sid) for sid in student_ids]),
                    CaseSubmission.department_id.in_([UUID(did) for did in dept_ids]),
                    CaseSubmission.status == SubmissionStatus.approved,
                    CaseSubmission.deleted_at.is_(None),
                )
                .group_by(CaseSubmission.student_id, CaseSubmission.department_id)
            )
            approved_map: dict[tuple[str, str], int] = {
                (str(row.student_id), str(row.department_id)): int(row.approved)
                for row in sub_result.all()
            }

            # 4. Get student info
            user_result = await db.execute(
                select(User).where(
                    User.id.in_([UUID(sid) for sid in student_ids]),
                    User.is_active.is_(True),
                )
            )
            student_map: dict[str, User] = {
                str(u.id): u for u in user_result.scalars().all()
            }

            # 5. System sender
            sender_id = await _get_system_sender_id(db)
            if not sender_id:
                logger.warning(
                    "No admin user found; cannot create Notification records"
                )
                return

            # 6. Evaluate each rotation
            sent_count = 0

            for rot, dept in rows:
                required = required_map.get(str(dept.id), 0)
                if required == 0:
                    continue

                elapsed = max(0, int((now - rot.started_at).total_seconds() // 86400))
                days_active = rot.days_offset + elapsed
                time_pct = (
                    (days_active / dept.rotation_duration_days) * 100
                    if dept.rotation_duration_days > 0
                    else 0
                )

                if time_pct < 50:
                    continue

                approved = approved_map.get((str(rot.student_id), str(dept.id)), 0)
                case_pct = (approved / required) * 100 if required > 0 else 0

                if case_pct >= 60:
                    continue

                # Cooldown: skip if reminded within 7 days
                if rot.last_reminder_sent and rot.last_reminder_sent >= seven_days_ago:
                    continue

                student = student_map.get(str(rot.student_id))
                if not student:
                    continue

                student_name = display_name(student)
                subject = (
                    f"{REMINDER_SUBJECT_PREFIX} Progress update needed in {dept.name}"
                )
                message = (
                    f"Dear {student_name},\n\n"
                    f"You are currently on Day {days_active} of "
                    f"{dept.rotation_duration_days} "
                    f"in your {dept.name} rotation, but have only completed "
                    f"{approved} of {required} required cases "
                    f"({approved / required * 100:.0f}%).\n\n"
                    f"Please prioritize your case submissions to stay on track.\n\n"
                    f"Best regards,\nClinic Tracker System"
                )

                notification = Notification(
                    sender_id=sender_id,
                    recipient_id=rot.student_id,
                    subject=subject,
                    message=message,
                )
                db.add(notification)

                try:
                    await send_email(
                        to=student.email,
                        subject=subject,
                        html=f"<p>{sanitize_for_email(message).replace(chr(10), '<br>')}</p>",
                    )
                except Exception:
                    logger.exception(
                        "Failed to send reminder email to student_id=%s",
                        rot.student_id,
                    )

                # Update cooldown timestamp
                rot.last_reminder_sent = now
                sent_count += 1

            if sent_count > 0:
                await db.commit()
                logger.info("Sent %d rotation reminders", sent_count)
            else:
                logger.info("No reminders needed today")

        except Exception:
            logger.exception("Rotation reminder job failed")


def create_scheduler():
    """Create and configure the APScheduler instance."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_rotation_reminders,
        trigger="cron",
        hour=5,
        minute=0,
        id="rotation_reminders",
        replace_existing=True,
    )
    return scheduler
