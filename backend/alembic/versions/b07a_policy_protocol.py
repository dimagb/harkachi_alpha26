"""B-07a: persist policy calculation and what-if protocol."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "b07a_policy_protocol"
down_revision = "e4617f936133"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("decision", sa.Column("policy", postgresql.JSONB(), nullable=True))
    op.add_column(
        "decision",
        sa.Column("what_if", postgresql.JSONB(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("decision", "what_if")
    op.drop_column("decision", "policy")
