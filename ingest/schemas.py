"""Pydantic schemas for validating Gemini output."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EventType = Literal["announcement", "verdict", "statement", "update", "correction"]


class ClusterOut(BaseModel):
    """One story cluster returned by Gemini Phase 2."""
    title: str
    category: str = "India Top News"
    article_indices: list[int]
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("title")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("empty title")
        return v[:280]


class ClustersResponse(BaseModel):
    clusters: list[ClusterOut]


class EventOut(BaseModel):
    """One new timeline event returned by Gemini Phase 5."""
    event_timestamp: datetime
    headline: str
    details: str = ""
    event_type: EventType = "update"
    source_index: int = -1  # index into the cluster's articles
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("headline")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("empty headline")
        return v[:280]


class StoryEventsOut(BaseModel):
    cluster_index: int
    updated_summary: str = ""
    new_events: list[EventOut] = []


class EventsResponse(BaseModel):
    stories: list[StoryEventsOut]
