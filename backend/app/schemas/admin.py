from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PendingUserResponse(BaseModel):
    id: int
    skala_id: str
    name: str
    created_at: datetime


class ReviewUserResponse(BaseModel):
    id: int
    skala_id: str
    name: str
    status: Literal["ACTIVE", "REJECTED"]
