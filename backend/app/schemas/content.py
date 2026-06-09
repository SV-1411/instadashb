"""Pydantic v2 shapes for Public Voice, Trends, and AI Brief."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MentionSample(BaseModel):
    text: str
    sentiment_label: str | None
    platform: str
    likes: int
    topics: list[str]
    platform_ts: datetime | None


class PublicVoiceOut(BaseModel):
    politician_id: int
    by_sentiment: dict[str, int]
    by_platform: dict[str, int]
    samples: list[MentionSample]
    generated_at: datetime


class TopicCount(BaseModel):
    topic: str
    count: int


class TrendSeriesPoint(BaseModel):
    bucket_hour: datetime
    total: int
    positive: int
    negative: int


class TrendsOut(BaseModel):
    politician_id: int
    top_topics: list[TopicCount]
    series: list[TrendSeriesPoint]
    generated_at: datetime


class AIBriefOut(BaseModel):
    politician_id: int
    summary: str
    actions: list[str]
    generated_at: str | None
    available: bool


class GeoCity(BaseModel):
    city: str
    lat: float
    lon: float
    mentions: int
    negative: int
    avg_sentiment: float  # -1..1


class GeoOut(BaseModel):
    politician_id: int
    cities: list[GeoCity]
    generated_at: datetime


class MisinfoOut(BaseModel):
    politician_id: int
    flagged: bool
    claim_volume: int
    window_hours: int
    sample_texts: list[str]
    generated_at: datetime


class GrowthPoint(BaseModel):
    day: str
    reach: int
    engagement: int


class GrowthOut(BaseModel):
    politician_id: int
    series: list[GrowthPoint]
    generated_at: datetime


class GroundInputIn(BaseModel):
    politician_id: int
    text: str
    city: str | None = None


class GroundInputOut(BaseModel):
    stored: bool
    mention_id: int
    sentiment_label: str | None
    topics: list[str]
    inferred_city: str | None
