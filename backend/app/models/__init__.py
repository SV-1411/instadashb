"""ORM models for the 5 core tables. Importing this package registers all
tables on ``Base.metadata`` (needed by Alembic autogenerate and tests)."""

from app.models.aggregate import Aggregate
from app.models.audience_geo import AudienceGeo
from app.models.mention import Mention
from app.models.politician import Politician
from app.models.post_metric import PostMetric

__all__ = [
    "Aggregate",
    "AudienceGeo",
    "Mention",
    "Politician",
    "PostMetric",
]
