from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user_record
from app.models.enums import NotificationStatus
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationRead, NotificationsReadAllResponse

router = APIRouter()


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    status_filter: NotificationStatus | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = NotificationRepository(db)
    return repo.list_for_user(
        current_user.id,  # type: ignore[invalid-argument-type]
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.post("/read-all", response_model=NotificationsReadAllResponse)
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = NotificationRepository(db)
    updated = repo.mark_all_read(current_user.id)  # type: ignore[invalid-argument-type]
    return NotificationsReadAllResponse(updated=updated)


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = NotificationRepository(db)
    notification = repo.get(notification_id)
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )
    if notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot mark another user's notification",
        )
    updated = repo.mark_read(notification_id)
    assert updated is not None
    return updated


@router.post("/{notification_id}/archive", response_model=NotificationRead)
async def archive_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = NotificationRepository(db)
    notification = repo.get(notification_id)
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )
    if notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot archive another user's notification",
        )
    updated = repo.mark_archived(notification_id)
    assert updated is not None
    return updated
