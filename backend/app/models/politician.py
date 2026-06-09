"""Politician model — the tenant. meta_token is encrypted at rest."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import EncryptedString
from app.database import Base


class Politician(Base):
    __tablename__ = "politicians"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    constituency: Mapped[str | None] = mapped_column(String(200))
    state: Mapped[str | None] = mapped_column(String(100))

    ig_account_id: Mapped[str | None] = mapped_column(String(100))
    fb_page_id: Mapped[str | None] = mapped_column(String(100))
    # Encrypted at rest (Fernet) — plaintext never stored or logged.
    meta_token: Mapped[str | None] = mapped_column(EncryptedString(2000))
    x_handle: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
