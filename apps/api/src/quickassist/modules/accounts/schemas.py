import uuid
from datetime import datetime

from quickassist.core.schemas import ApiModel


class UserOut(ApiModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    created_at: datetime
