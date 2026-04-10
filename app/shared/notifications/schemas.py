from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient_id: int
    title: str
    message: str
    action_url: Optional[str]
    is_read: bool
    created_at: datetime


class NotificationList(BaseModel):
    notifications: list[NotificationPublic]
    unread_count: int
