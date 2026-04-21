# backend/app/schemas/dashboard.py

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.pagination import PaginatedResponse


class CategoryProgress(BaseModel):
    """Progress for a single task category within a department."""

    category_id: uuid.UUID
    category_name: str
    required_count: int
    completed_count: int  # sum of approved case_count
    pending_count: int  # sum of pending case_count
    completion_percentage: float  # (completed / required) * 100, capped at 100

    model_config = {"from_attributes": True}


class DepartmentProgress(BaseModel):
    """Progress for a single department, including all its categories."""

    department_id: uuid.UUID
    department_name: str
    categories: list[CategoryProgress]
    total_required: int  # sum of all category required_counts
    total_completed: int  # sum of all category completed_counts
    completion_percentage: float  # (total_completed / total_required) * 100

    model_config = {"from_attributes": True}


class RecentSubmission(BaseModel):
    """Lightweight submission record for dashboard display."""

    id: uuid.UUID
    department_name: str
    category_name: str
    case_count: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProgressDataPoint(BaseModel):
    """A single data point for the progress-over-time line chart."""

    date: str  # ISO date string (YYYY-MM-DD)
    cumulative_cases: int


class StudentDashboardResponse(BaseModel):
    """Full dashboard data for a single student."""

    student_id: uuid.UUID
    student_name: str
    current_department: str | None  # name of current rotation dept, or None
    overall_completion_percentage: float
    total_required: int
    total_completed: int
    departments: list[DepartmentProgress]
    recent_submissions: list[RecentSubmission]
    progress_over_time: list[ProgressDataPoint]
    show_rotation_warning: bool = False

    # Rotation time progress
    rotation_days_active: int = 0
    rotation_duration_days: int = 0
    rotation_time_pct: float = 0.0


class StudentSummary(BaseModel):
    """Lightweight student record for supervisor's student list."""

    student_id: uuid.UUID
    student_name: str
    student_email: str
    student_code: str | None
    current_department: str | None
    overall_completion_percentage: float
    total_required: int
    total_completed: int
    status: str  # "on_track", "at_risk", "unassigned"
    assignment_type: str | None = None  # "primary" | "department" | null


class SupervisorDashboardResponse(BaseModel):
    """Dashboard data for supervisor overview."""

    total_students: int
    on_track_count: int
    at_risk_count: int
    unassigned_count: int
    students: PaginatedResponse[StudentSummary]


class DepartmentStudentProgress(BaseModel):
    """A student's progress within a specific department."""

    student_id: uuid.UUID
    student_name: str
    total_required: int
    total_completed: int
    completion_percentage: float
    status: str


class DepartmentDashboardResponse(BaseModel):
    """Dashboard data for a specific department."""

    department_id: uuid.UUID
    department_name: str
    total_students: int  # students with submissions or current rotation
    average_completion: float
    students: list[DepartmentStudentProgress]


# --- Rotation Tracker Schemas ---


class DepartmentTrackerEntry(BaseModel):
    """Per-department rotation tracker card."""

    department_id: uuid.UUID
    department_name: str
    is_current: bool

    # Case progress
    total_required: int
    total_completed: int
    total_pending: int
    case_completion_percentage: float
    case_status_color: str  # "red" | "yellow" | "green"

    # Time progress
    rotation_duration_days: int
    days_active: int
    time_completion_percentage: float

    # Rotation metadata
    started_at: datetime | None
    rotation_id: uuid.UUID | None


class DepartmentTrackerResponse(BaseModel):
    """Full tracker data for the student tracker page."""

    current_department_id: uuid.UUID | None
    entries: list[DepartmentTrackerEntry]
    show_warning: bool
