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


class BankStatementImportStatus(str, enum.Enum):
    pending = "pending"
    applied = "applied"
    discarded = "discarded"


class BankPaymentTransactionStatus(str, enum.Enum):
    unmatched = "unmatched"
    matched = "matched"
    applied = "applied"
    ignored = "ignored"


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


# ---------------------------------------------------------------------------
# Notification types
#
# Every notification is either admin- (org-level, fanned to org managers) or
# customer-facing (a single user). The string value is audience-prefixed and
# dotted so the same logical event can exist in both enums without colliding;
# it is load-bearing: it is what the worker stores, and — with non-alphanumerics
# stripped — the Resend template id (``customer.capital_call`` →
# ``customercapitalcall``). See app/services/channels/email_channel.py.
# ---------------------------------------------------------------------------


class AdminNotificationType(enum.StrEnum):
    INVITATION_ACCEPTED = "admin.invitation_accepted"


class CustomerNotificationType(enum.StrEnum):
    WELCOME = "customer.welcome"
    INVITATION = "customer.invitation"
    CAPITAL_CALL = "customer.capital_call"
    DISTRIBUTION = "customer.distribution"
    DOCUMENT_UPLOADED = "customer.document_uploaded"
    COMMITMENT_STATUS = "customer.commitment_status"
    TASK_ASSIGNED = "customer.task_assigned"
    COMMUNICATION = "customer.communication"


NotificationType = AdminNotificationType | CustomerNotificationType


def coerce_notification_type(value: str) -> NotificationType:
    """Narrow a raw notification-type string back to its enum.

    The worker receives the type as a plain string off the queue; the DB column
    is a bare ``VARCHAR`` because SQLAlchemy can't type a union of two enums.
    """
    try:
        return AdminNotificationType(value)
    except ValueError:
        return CustomerNotificationType(value)
