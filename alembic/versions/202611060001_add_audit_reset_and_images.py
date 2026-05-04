"""Add audit logs, password reset flag, and listing images

Revision ID: 202611060001
Revises:
Create Date: 2026-11-06 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op  # type: ignore[import-not-found]

# revision identifiers, used by Alembic.
revision: str = "202611060001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())

    if "audit_logs" not in table_names:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("target_type", sa.String(), nullable=False),
            sa.Column("target_id", sa.String(), nullable=False),
            sa.Column("details", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_audit_logs_id", "audit_logs", ["id"], unique=False)
        op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"], unique=False)
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)

    if "users" in table_names:
        user_columns = {col["name"] for col in inspector.get_columns("users")}
        if "must_reset_password" not in user_columns:
            with op.batch_alter_table("users") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "must_reset_password",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.text("0"),
                    )
                )

    if "listings" in table_names:
        listing_columns = {col["name"] for col in inspector.get_columns("listings")}
        if "image_url" not in listing_columns:
            with op.batch_alter_table("listings") as batch_op:
                batch_op.add_column(sa.Column("image_url", sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "listings" in table_names:
        listing_columns = {col["name"] for col in inspector.get_columns("listings")}
        if "image_url" in listing_columns:
            with op.batch_alter_table("listings") as batch_op:
                batch_op.drop_column("image_url")

    if "users" in table_names:
        user_columns = {col["name"] for col in inspector.get_columns("users")}
        if "must_reset_password" in user_columns:
            with op.batch_alter_table("users") as batch_op:
                batch_op.drop_column("must_reset_password")

    if "audit_logs" in table_names:
        op.drop_index("ix_audit_logs_action", table_name="audit_logs")
        op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
        op.drop_index("ix_audit_logs_id", table_name="audit_logs")
        op.drop_table("audit_logs")
