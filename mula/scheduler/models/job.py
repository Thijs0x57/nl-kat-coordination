import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, constr
from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from scheduler.utils import GUID

from .base import Base
from .queue import PrioritizedItem
from .rate_limit import RateLimit
from .tasks import Task


class Job(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)

    scheduler_id: str

    enabled: bool = True

    p_item: PrioritizedItem

    tasks: List[Task] = []

    # TODO: not yet implemented, added as proof of concept
    rate_limit: Optional[RateLimit] = None

    # TODO: not yet implemented, added as proof of concept
    crontab: Optional[str] = None

    deadline_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobDB(Base):
    __tablename__ = "jobs"

    id = Column(GUID, primary_key=True)
    scheduler_id = Column(String)
    enabled = Column(Boolean, nullable=False, default=True)
    p_item = Column(JSONB, nullable=False)
    tasks = relationship("TaskDB", back_populates="job", order_by="TaskDB.created_at")
    rate_limit = Column(JSONB, nullable=True)
    crontab = Column(String, nullable=True)

    deadline_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    evaluated_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    modified_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
