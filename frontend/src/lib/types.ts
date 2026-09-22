// Shared API contract types mirroring the internal backend schemas.

export type Role = 'admin' | 'supervisor' | 'intern'

export interface User {
  id: number
  email: string
  full_name: string
  role: Role
  is_active: boolean
  must_reset_password: boolean
  avatar_key: string | null
  github_url: string | null
  linkedin_url: string | null
  bio: string | null
  phone: string | null
  skills?: string[] | null
  created_at: string
}

export interface UserMe extends User {
  active_batch_id: number | null
  active_batch_name: string | null
}

export interface PaginatedUsers {
  items: User[]
  total: number
  page: number
  page_size: number
}

export interface Batch {
  id: number
  name: string
  description: string | null
  start_date: string
  end_date: string
  supervisor_id: number | null
  supervisor_name: string | null
  capacity: number
  start_time: string
  end_time: string
  grace_minutes: number
  status: 'active' | 'archived'
  active_intern_count: number | null
  created_at: string
}

export interface BatchDetail extends Batch {
  members: BatchMembership[]
}

export interface BatchMembership {
  id: number
  intern_id: number
  intern_name: string | null
  email: string | null
  is_active: boolean
  joined_at: string
}

export interface PaginatedBatches {
  items: Batch[]
  total: number
  page: number
  page_size: number
}

export type TaskScope = 'batch' | 'individual'
export type TaskCategory = 'Development' | 'Design' | 'Research' | 'Documentation' | 'Testing' | 'Presentation' | 'Other'
export type TaskPriority = 'Low' | 'Medium' | 'High'
export type TaskStatus = 'open' | 'in_progress' | 'submitted' | 'reviewed' | 'pending_resubmission'

export interface Task {
  id: number
  title: string
  description: string | null
  scope: TaskScope
  batch_id: number | null
  assignee_id: number | null
  created_by: number | null
  category: TaskCategory | null
  priority: TaskPriority | null
  status: TaskStatus
  deadline: string | null
  estimated_effort_hours: number | null
  authorized: boolean
  is_archived: boolean
  created_at: string
}

export interface TaskDetail extends Task {
  effective_deadline: string | null
  attachments: TaskAttachment[]
  author_name: string | null
  assignee_name: string | null
  latest_submission: Submission | null
  extension: DeadlineExtension | null
}

export interface TaskAttachment {
  id: number
  task_id: number
  uploaded_by: number | null
  filename: string
  file_key: string
  uploaded_at: string
}

export interface DeadlineExtension {
  id: number
  task_id: number
  intern_id: number
  original_deadline: string
  new_deadline: string
  reason: string | null
  granted_by: number | null
  created_at: string
}

export interface PaginatedTasks {
  items: Task[]
  total: number
  page: number
  page_size: number
}

export type SubmissionStatus = 'pending' | 'changes_requested' | 'approved' | 'rejected'
export type ReviewDecision = 'approved' | 'changes_requested' | 'rejected'

export interface Submission {
  id: number
  task_id: number
  task_title: string | null
  intern_id: number
  intern_name: string | null
  batch_id: number | null
  version: number
  github_url: string | null
  live_url: string | null
  zip_file_key: string | null
  filename: string | null
  notes: string | null
  actual_effort_hours: number | null
  submitted_at: string
  is_late: boolean
  late_reason: string | null
  status: SubmissionStatus
}

export interface Review {
  id: number
  submission_id: number
  supervisor_id: number | null
  supervisor_name: string | null
  decision: ReviewDecision
  score: number | null
  feedback: string | null
  reviewed_at: string
}

export interface SubmissionDetail extends Submission {
  reviews: Review[]
}

export interface PaginatedSubmissions {
  items: Submission[]
  total: number
  page: number
  page_size: number
}

export interface AttendanceRecord {
  id: number
  intern_id: number
  batch_id: number | null
  date: string
  check_in: string | null
  check_out: string | null
  late_status: 'on_time' | 'late' | null
  worked_hours: number | null
  work_done: string | null
  blockers: string | null
  next_day_plan: string | null
  intern_name?: string | null
}

export interface AttendanceSummaryRow {
  intern_id: number
  intern_name: string
  present_days: number
  late_days: number
  total_hours: number
  workdays: number
  absent_days?: number
  attendance_rate: number
}

export interface LeaveRequest {
  id: number
  intern_id: number
  intern_name: string | null
  batch_id?: number | null
  leave_type?: string | null
  start_date: string
  end_date: string
  reason: string | null
  note?: string | null
  status: 'pending' | 'approved' | 'rejected'
  decided_by: number | null
  decided_at: string | null
  created_at: string
}

export interface TaskComment {
  id: number
  task_id: number
  author_id: number
  author_name: string | null
  content: string
  is_edited: boolean
  is_deleted: boolean
  is_pinned: boolean
  mentions: number[]
  created_at: string
  updated_at: string | null
}

export interface Announcement {
  id: number
  batch_id: number | null
  author_id: number
  author_name: string | null
  title: string
  body: string
  is_pinned: boolean
  created_at: string
}

export interface BatchEvent {
  id: number
  batch_id: number
  title: string
  event_type: string
  starts_at: string
  ends_at: string | null
  location: string | null
  details: string | null
  created_by: number | null
  created_at: string
}

export interface CalendarEntry {
  type: 'task' | 'event' | 'leave'
  title: string
  start: string
  end: string | null
  link: string
  status?: string
}

export type NotificationType =
  | 'task_assigned'
  | 'deadline_approaching'
  | 'review_result'
  | 'deadline_extension'
  | 'mention'
  | 'announcement'
  | 'leave_decision'
  | 'attendance_update'
  | 'comment'
  | 'submission_submitted'
  | 'remark'
  | 'batch_event'
  | 'internship_completed'

export interface Notification {
  id: number
  recipient_id: number
  actor_id: number | null
  notification_type: NotificationType
  title: string
  body: string | null
  link: string | null
  is_read: boolean
  created_at: string
}

export interface PaginatedNotifications {
  items: Notification[]
  total: number
  page: number
  page_size: number
}

export interface CompanySettings {
  id: number
  company_name: string
  company_address: string | null
  company_phone: string | null
  company_email: string | null
  logo_key: string | null
  supervisor_signatory: string | null
  signatory_title: string | null
  onboarding_message: string | null
  welcome_message: string | null
  week_start: string
  timezone: string
  csrf_enabled: boolean
  registration_enabled: boolean
}

export interface SearchResult {
  type: string
  id: number
  label: string
  subtitle: string | null
  link: string
}

export interface SearchResults {
  query: string
  results: SearchResult[]
}

export interface AuditEntry {
  id: number
  actor_id: number | null
  actor_name: string | null
  action: string
  entity_type: string | null
  entity_id: number | null
  metadata: Record<string, unknown> | null
  created_at: string
}

export interface InternAnalytics {
  tasks_total: number
  tasks_completed: number
  tasks_pending: number
  overdue_tasks: number
  average_score: number | null
  attendance_rate: number | null
  on_time_rate: number | null
  late_days: number
  total_hours: number
  recent_tasks?: Task[]
  progress_by_week?: { week: string; completed: number; pending: number }[]
}

export interface SupervisorAnalytics {
  tasks_total: number
  overdue_tasks: number
  pending_reviews: number
  interns_active: number
  batch_attendance_rate: number | null
  tasks_by_category: Record<string, number>
  per_intern: { intern_id: number; intern_name: string; average_score: number | null; completion_rate: number }[]
}

export interface HrAnalytics {
  active_batches: number
  total_interns: number
  active_interns: number
  avg_completion_rate: number | null
  avg_score: number | null
  attendance_rate: number | null
  interns_by_batch: { batch_id: number; batch_name: string; count: number }[]
  completion_by_status: Record<string, number>
  up_for_completion?: { intern_id: number; intern_name: string; batch_id: number; batch_name: string | null }[]
}

export interface CertificatesResponse {
  items: Certificate[]
  total: number
  page: number
  page_size: number
}

export interface Certificate {
  id: number
  intern_id: number
  batch_id: number | null
  hash: string | null
  href: string | null
  file_key: string | null
  issued_at: string
  created_at: string
}