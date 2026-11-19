import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewEvent(BaseModel):
    """
    Typed event payload published when a review is created or updated.
    Contains strictly minimal metadata: event_type, review_id, timestamp, and stable event_id.
    """

    event_type: Literal["ReviewCreated", "ReviewUpdated"]
    review_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_id: str | None = Field(default=None)

    model_config = ConfigDict(extra="forbid")

    def model_dump(self, *args, **kwargs):
        data = super().model_dump(*args, **kwargs)
        if "event_id" in data and data["event_id"] is None and "event_id" not in self.__pydantic_fields_set__:
            data.pop("event_id")
        return data

    def model_dump_json(self, *args, **kwargs):
        if "event_id" not in self.__pydantic_fields_set__ and self.event_id is None:
            kwargs.setdefault("exclude_none", True)
        return super().model_dump_json(*args, **kwargs)

