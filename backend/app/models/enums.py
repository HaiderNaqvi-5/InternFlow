from enum import Enum


class UserRole(str, Enum):
    INTERN = "intern"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"

    @property
    def label(self) -> str:
        return {
            UserRole.INTERN: "Intern",
            UserRole.SUPERVISOR: "Supervisor",
            UserRole.ADMIN: "Admin",
        }[self]


class BatchStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TaskScope(str, Enum):
    BATCH = "batch"
    INDIVIDUAL = "individual"


class TaskCategory(str, Enum):
    DEVELOPMENT = "Development"
    RESEARCH = "Research"
    DOCUMENTATION = "Documentation"
    TESTING = "Testing"
    PRESENTATION = "Presentation"
    DESIGN = "Design"
    OTHER = "Other"


class TaskPriority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    PENDING_RESUBMISSION = "pending_resubmission"


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class SubmissionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class AttendanceStatus(str, Enum):
    ON_TIME = "on_time"
    LATE = "late"


class LeaveStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EventType(str, Enum):
    REVIEW = "review"
    PRESENTATION = "presentation"
    MEETING = "meeting"
    OTHER = "other"


class NotificationType(str, Enum):
    TASK_ASSIGNED = "task_assigned"
    DEADLINE_APPROACHING = "deadline_approaching"
    REVIEW_RESULT = "review_result"
    DEADLINE_EXTENSION = "deadline_extension"
    MENTION = "mention"
    ANNOUNCEMENT = "announcement"
    LEAVE_DECISION = "leave_decision"
    ATTENDANCE_UPDATE = "attendance_update"
    COMMENT = "comment"
    SUBMISSION_SUBMITTED = "submission_submitted"
    REMARK = "remark"
    BATCH_EVENT = "batch_event"
    INTERNSHIP_COMPLETED = "internship_completed"


class OutcomeRecommendation(str, Enum):
    SUCCESSFULLY_COMPLETED = "successfully_completed"
    COMPLETED_WITH_CONCERNS = "completed_with_concerns"
    NEEDS_EXTENSION = "needs_extension"


class CompletionStatus(str, Enum):
    NOT_COMPLETED = "not_completed"
    SUCCESSFULLY_COMPLETED = "successfully_completed"


class ReportType(str, Enum):
    INTERNSHIP_REPORT = "internship_report"
    ATTENDANCE_EXPORT = "attendance_export"
    EVALUATION_EXPORT = "evaluation_export"


ALL_TASK_CATEGORIES = [c.value for c in TaskCategory]
ALL_PRIORITIES = [p.value for p in TaskPriority]