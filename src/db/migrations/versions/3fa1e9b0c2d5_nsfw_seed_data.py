"""nsfw seed data - baseline domains and keywords

Revision ID: 3fa1e9b0c2d5
Revises: 2de4cb8db991
Create Date: 2026-03-19 13:00:00.000000
"""
from typing import Sequence, Union
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision: str = '3fa1e9b0c2d5'
down_revision: Union[str, Sequence[str], None] = '2de4cb8db991'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = datetime.now(timezone.utc)

_DOMAINS = [
    "pornhub.com", "xvideos.com", "xhamster.com", "xnxx.com",
    "redtube.com", "youporn.com", "tube8.com", "spankbang.com",
    "eporner.com", "beeg.com", "tnaflix.com", "extremetube.com",
    "keezmovies.com", "empflix.com", "4tube.com", "slutload.com",
    "thumbzilla.com", "rule34.xxx", "rule34.paheal.net", "gelbooru.com",
    "e-hentai.org", "exhentai.org", "nhentai.net",
    "kemono.party", "kemono.cr", "coomer.party", "coomer.su",
    "onlyfans.com", "fansly.com",
]

_KEYWORDS = [
    "porn", "pornhub", "hentai", "nsfw", "xxx",
    "sex tape", "sex video",
    "nude", "nudes", "naked",
    "anal", "blowjob", "handjob", "cumshot", "creampie",
    "milf", "dildo", "vibrator",
    "onlyfans", "fansly",
    "порно", "секс видео", "голая", "эротика",
]


def upgrade() -> None:
    t_domains = sa.table(
        "nsfw_domains",
        sa.column("domain", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    t_keywords = sa.table(
        "nsfw_keywords",
        sa.column("keyword", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    op.bulk_insert(t_domains, [{"domain": d, "created_at": _NOW} for d in _DOMAINS])
    op.bulk_insert(t_keywords, [{"keyword": k, "created_at": _NOW} for k in _KEYWORDS])


def downgrade() -> None:
    op.execute("DELETE FROM nsfw_keywords")
    op.execute("DELETE FROM nsfw_domains")
