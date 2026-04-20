"""Notification helpers for case submission lifecycle events."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.submission import CaseSubmission
from app.models.user import User, display_name
from app.utils.email import sanitize_for_email, send_email

logger = logging.getLogger(__name__)


def _e(text: str) -> str:
    return sanitize_for_email(text)


async def notify_submission_created(
    db: AsyncSession,
    submission: CaseSubmission,
    student: User,
    target_supervisor: User,
    academic_supervisor: User | None,
) -> None:
    """Persist Notification records and send emails on submission creation.

    Notifies the target supervisor; CCs the academic supervisor when assigned.
    Email failures are logged but never abort the caller's transaction.
    """
    student_name = display_name(student)
    sv_name = display_name(target_supervisor)
    notes_html = (
        f"<p><strong>Notes:</strong> {_e(submission.notes)}</p>"
        if submission.notes
        else ""
    )

    # Target supervisor
    sv_subject = "New case submission awaiting your review"
    sv_message = (
        f"{student_name} has submitted a case record "
        f"({submission.case_count} case(s)) and selected you as the reviewer."
    )
    db.add(
        Notification(
            sender_id=student.id,
            recipient_id=target_supervisor.id,
            subject=sv_subject,
            message=sv_message,
        )
    )
    sv_html = f"""
    <p>Hi {_e(sv_name)},</p>
    <p>{_e(student_name)} has submitted a case record for your review.</p>
    <ul><li><strong>Case count:</strong> {submission.case_count}</li></ul>
    {notes_html}
    <p>Please log in to Smart Clinic Tracker to review this submission.</p>
    """
    try:
        await send_email(to=target_supervisor.email, subject=sv_subject, html=sv_html)
    except Exception:
        logger.exception(
            "Failed to email target supervisor (id=%s) for submission %s",
            target_supervisor.id,
            submission.id,
        )

    # Academic supervisor CC
    if academic_supervisor:
        acad_name = display_name(academic_supervisor)
        acad_subject = f"[CC] New case submission from {student_name}"
        acad_message = (
            f"Your student {student_name} has submitted a case record "
            f"({submission.case_count} case(s)) for review by {sv_name}."
        )
        db.add(
            Notification(
                sender_id=student.id,
                recipient_id=academic_supervisor.id,
                subject=acad_subject,
                message=acad_message,
            )
        )
        acad_html = f"""
        <p>Hi {_e(acad_name)},</p>
        <p>This is a courtesy copy. Your student {_e(student_name)} has submitted a
        case record for review by {_e(sv_name)}.</p>
        <ul><li><strong>Case count:</strong> {submission.case_count}</li></ul>
        {notes_html}
        """
        try:
            await send_email(
                to=academic_supervisor.email, subject=acad_subject, html=acad_html
            )
        except Exception:
            logger.exception(
                "Failed to email academic supervisor (id=%s) for submission %s",
                academic_supervisor.id,
                submission.id,
            )


async def notify_submission_reviewed(
    db: AsyncSession,
    submission: CaseSubmission,
    student: User,
    reviewer: User,
    academic_supervisor: User | None,
) -> None:
    """Persist Notification records and send emails on submission review.

    Notifies the student; CCs the academic supervisor when assigned.
    Email failures are logged but never abort the caller's transaction.
    """
    student_name = display_name(student)
    reviewer_name = display_name(reviewer)
    status_label = submission.status.value  # "approved" or "rejected"
    status_color = "green" if status_label == "approved" else "red"
    review_notes_html = (
        f"<p><strong>Review notes:</strong> {_e(submission.review_notes)}</p>"
        if submission.review_notes
        else ""
    )

    # Student
    student_subject = f"Your case submission has been {status_label}"
    student_message = (
        f"Your case submission ({submission.case_count} case(s)) has been "
        f"{status_label} by {reviewer_name}."
    )
    if submission.review_notes:
        student_message += f" Review notes: {submission.review_notes}"
    db.add(
        Notification(
            sender_id=reviewer.id,
            recipient_id=student.id,
            subject=student_subject,
            message=student_message,
        )
    )
    student_html = f"""
    <p>Hi {_e(student_name)},</p>
    <p>Your case submission has been
    <strong style="color:{status_color}">{status_label}</strong>
    by {_e(reviewer_name)}.</p>
    <ul><li><strong>Case count:</strong> {submission.case_count}</li></ul>
    {review_notes_html}
    <p>Log in to Smart Clinic Tracker to view the details.</p>
    """
    try:
        await send_email(to=student.email, subject=student_subject, html=student_html)
    except Exception:
        logger.exception(
            "Failed to email student (id=%s) for submission %s review",
            student.id,
            submission.id,
        )

    # Academic supervisor CC
    if academic_supervisor:
        acad_name = display_name(academic_supervisor)
        acad_subject = f"[CC] Case submission by {student_name} has been {status_label}"
        acad_message = (
            f"Your student {student_name}'s case submission ({submission.case_count} case(s)) "
            f"has been {status_label} by {reviewer_name}."
        )
        if submission.review_notes:
            acad_message += f" Review notes: {submission.review_notes}"
        db.add(
            Notification(
                sender_id=reviewer.id,
                recipient_id=academic_supervisor.id,
                subject=acad_subject,
                message=acad_message,
            )
        )
        acad_html = f"""
        <p>Hi {_e(acad_name)},</p>
        <p>This is a courtesy copy. Your student {_e(student_name)}'s case submission has been
        <strong style="color:{status_color}">{status_label}</strong>
        by {_e(reviewer_name)}.</p>
        <ul><li><strong>Case count:</strong> {submission.case_count}</li></ul>
        {review_notes_html}
        """
        try:
            await send_email(
                to=academic_supervisor.email, subject=acad_subject, html=acad_html
            )
        except Exception:
            logger.exception(
                "Failed to email academic supervisor (id=%s) for submission %s review",
                academic_supervisor.id,
                submission.id,
            )
