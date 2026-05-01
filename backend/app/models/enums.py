"""Python enum mirrors of the dbml enum types.

Each enum value matches the dbml literal exactly. The `name` passed to
`sa.Enum(...)` (in the column definitions) controls the PostgreSQL
`CREATE TYPE` name.
"""

import enum


class UserRole(str, enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    fund_manager = "fund_manager"
    lp = "lp"


class OrganizationType(str, enum.Enum):
    fund_manager_firm = "fund_manager_firm"
    investor_firm = "investor_firm"
    service_provider = "service_provider"


class FundStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    closed = "closed"
    liquidating = "liquidating"
    archived = "archived"


class CommitmentStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    declined = "declined"
    cancelled = "cancelled"


class CapitalCallStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    sent = "sent"
    partially_paid = "partially_paid"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class DistributionStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    sent = "sent"
    partially_paid = "partially_paid"
    paid = "paid"
    cancelled = "cancelled"


class DocumentType(str, enum.Enum):
    legal = "legal"
    kyc_aml = "kyc_aml"
    financial = "financial"
    report = "report"
    notice = "notice"
    other = "other"


class CommunicationType(str, enum.Enum):
    announcement = "announcement"
    message = "message"
    notification = "notification"


class NotificationStatus(str, enum.Enum):
    unread = "unread"
    read = "read"
    archived = "archived"


class TaskStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"


class InvitationStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    revoked = "revoked"
    expired = "expired"
