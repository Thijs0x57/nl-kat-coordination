import enum
import uuid
from datetime import datetime, timedelta, timezone
from typing import ClassVar, List, Optional

import mmh3
from pydantic import BaseModel, ConfigDict, Field, computed_field
from sqlalchemy import Column, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Index
from sqlalchemy.sql import func
from sqlalchemy.sql.expression import text
from sqlalchemy.sql.schema import ForeignKey

from scheduler.utils import GUID

from .base import Base
from .boefje import Boefje
from .normalizer import Normalizer
from .queue import PrioritizedItem
from .raw_data import RawData


class TaskStatus(str, enum.Enum):
    # Task has been created but not yet queued
    PENDING = "pending"

    # Task has been pushed onto queue and is ready to be picked up
    QUEUED = "queued"

    # Task has been picked up by a worker
    DISPATCHED = "dispatched"

    # Task has been picked up by a worker, and the worker indicates that it is
    # running.
    RUNNING = "running"

    # Task has been completed
    COMPLETED = "completed"

    # Task has failed
    FAILED = "failed"

    # Task has been cancelled
    CANCELLED = "cancelled"


class TaskEventType(str, enum.Enum):
    STATUS_CHANGE = "status_change"


class TaskEvent(BaseModel):
    """TaskEvent represent an event that happened to a Task."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task_id: uuid.UUID
    event_type: str
    event_data: dict
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskEventDB(Base):
    __tablename__ = "task_events"

    id = Column(GUID, primary_key=True)

    task_id = Column(GUID, ForeignKey("tasks.id"), index=True, nullable=False)
    task = relationship("TaskDB", back_populates="events")

    event_type = Column(String, nullable=False)
    event_data = Column(JSONB, nullable=False)

    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Task(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID

    scheduler_id: str

    type: str

    p_item: PrioritizedItem

    status: TaskStatus

    events: List[TaskEvent] = []

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field  # type: ignore
    @property
    def queued(self) -> Optional[timedelta]:
        """Get the time the task has been queued in seconds. From the time the
        task has been QUEUED to the time it has been DISPATCHED."""
        start_time: Optional[datetime] = None
        end_time: Optional[datetime] = None

        # From the events, get the timestamp of the first QUEUED event
        for event in self.events:
            if event.event_type == TaskEventType.STATUS_CHANGE and event.event_data["to_status"] == TaskStatus.QUEUED:
                start_time = event.timestamp
                break

        # From the events, get the timestamp of the first DISPATCHED event
        for event in self.events:
            if (
                event.event_type == TaskEventType.STATUS_CHANGE
                and event.event_data["to_status"] == TaskStatus.DISPATCHED
            ):
                end_time = event.timestamp
                break

        if start_time and end_time:
            return end_time - start_time

        return None

    @computed_field  # type: ignore
    @property
    def runtime(self) -> Optional[timedelta]:
        """Get the runtime of the task in seconds. From the time the task has
        been DISPATCHED to the time it has been COMPLETED or FAILED."""
        start_time: Optional[datetime] = None
        end_time: Optional[datetime] = None

        # From the events, get the timestamp of the first DISPATCHED event
        for event in self.events:
            if (
                event.event_type == TaskEventType.STATUS_CHANGE
                and event.event_data["to_status"] == TaskStatus.DISPATCHED
            ):
                start_time = event.timestamp
                break

        # From the events, get the timestamp of the last COMPLETED or FAILED event
        for event in reversed(self.events):
            if event.event_type == TaskEventType.STATUS_CHANGE and event.event_data["to_status"] in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
            ]:
                end_time = event.timestamp
                break

        if start_time and end_time:
            return end_time - start_time

        return None

    @computed_field  # type: ignore
    @property
    def duration(self) -> Optional[timedelta]:
        """Get the duration of the task in seconds. From the time the task has
        been QUEUED to the time it has been COMPLETED or FAILED."""
        start_time: Optional[datetime] = None
        end_time: Optional[datetime] = None

        # From the events, get the timestamp of the first QUEUED event
        for event in self.events:
            if event.event_type == TaskEventType.STATUS_CHANGE and event.event_data["to_status"] == TaskStatus.QUEUED:
                start_time = event.timestamp
                break

        # From the events, get the timestamp of the last COMPLETED or FAILED event
        for event in reversed(self.events):
            if event.event_type == TaskEventType.STATUS_CHANGE and event.event_data["to_status"] in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
            ]:
                end_time = event.timestamp
                break

        if start_time and end_time:
            return end_time - start_time

        return None

    def __repr__(self):
        return f"Task(id={self.id}, scheduler_id={self.scheduler_id}, type={self.type}, status={self.status})"

    def model_dump_db(self):
        return self.model_dump(exclude={"events", "runtime", "duration", "queued"})


class TaskDB(Base):
    __tablename__ = "tasks"

    id = Column(GUID, primary_key=True)

    scheduler_id = Column(String)

    type = Column(String)

    p_item = Column(JSONB, nullable=False)

    status = Column(
        Enum(TaskStatus),
        nullable=False,
        default=TaskStatus.PENDING,
    )

    events = relationship(
        "TaskEventDB", back_populates="task", cascade="all, delete-orphan", order_by="TaskEventDB.timestamp"
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

    __table_args__ = (
        Index(
            "ix_p_item_hash",
            text("(p_item->>'hash')"),
            created_at.desc(),
        ),
    )


class NormalizerTask(BaseModel):
    """NormalizerTask represent data needed for a Normalizer to run."""

    type: ClassVar[str] = "normalizer"

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    normalizer: Normalizer
    raw_data: RawData

    @property
    def hash(self) -> str:
        """Make NormalizerTask hashable, so that we can de-duplicate it when
        used in the PriorityQueue. We hash the combination of the attributes
        normalizer.id since this combination is unique."""
        return mmh3.hash_bytes(
            f"{self.normalizer.id}-{self.raw_data.boefje_meta.id}-{self.raw_data.boefje_meta.organization}"
        ).hex()


class BoefjeTask(BaseModel):
    """BoefjeTask represent data needed for a Boefje to run."""

    type: ClassVar[str] = "boefje"

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    boefje: Boefje
    input_ooi: Optional[str]
    organization: str

    dispatches: List[Normalizer] = Field(default_factory=list)

    @property
    def hash(self) -> str:
        """Make BoefjeTask hashable, so that we can de-duplicate it when used
        in the PriorityQueue. We hash the combination of the attributes
        input_ooi and boefje.id since this combination is unique."""
        if self.input_ooi:
            return mmh3.hash_bytes(f"{self.input_ooi}-{self.boefje.id}-{self.organization}").hex()

        return mmh3.hash_bytes(f"{self.boefje.id}-{self.organization}").hex()
