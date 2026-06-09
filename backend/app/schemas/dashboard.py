"""Pydantic v2 response shapes for the dashboard read API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PoliticianOut(BaseModel):
    id: int
    name: str
    constituency: str | None = None
    state: str | None = None
    token_status: str = "unknown"  # connected | expired | revoked | missing


class TrendPoint(BaseModel):
    bucket_hour: datetime
    sentiment_score: int
    positive_count: int
    negative_count: int
    neutral_count: int
    is_spike: bool


class CommandCenterOut(BaseModel):
    politician_id: int
    sentiment_score: int  # latest 0-100
    positive_count: int
    negative_count: int
    neutral_count: int
    total_mentions: int
    active_spike: bool
    trend: list[TrendPoint]  # last N hourly buckets
    calibrating: bool  # true when no baseline yet
    generated_at: datetime


class TopPostOut(BaseModel):
    post_id: str
    platform: str
    likes: int
    comments_count: int
    shares: int
    reach: int
    engagement: int


class CityGeoOut(BaseModel):
    city: str
    follower_pct: float
    age_band: str | None = None
    gender: str | None = None


class IdentityOut(BaseModel):
    politician_id: int
    top_posts: list[TopPostOut]
    audience: list[CityGeoOut]
    generated_at: datetime


class CrisisOut(BaseModel):
    politician_id: int
    active_spike: bool
    recent_spikes: list[TrendPoint]
    dm_count: int
    generated_at: datetime
