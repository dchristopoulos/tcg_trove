"""Session hardening and integrity constraints

Revision ID: 202611060002
Revises: 202611060001
Create Date: 2026-11-06 00:02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op  # type: ignore[import-not-found]

# revision identifiers, used by Alembic.
revision: str = "202611060002"
down_revision: str | Sequence[str] | None = "202611060001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "users" in table_names:
        user_columns = {col["name"] for col in inspector.get_columns("users")}
        if "active_session_expires_at" not in user_columns:
            with op.batch_alter_table("users") as batch_op:
                batch_op.add_column(sa.Column("active_session_expires_at", sa.DateTime(timezone=True), nullable=True))

    if "listings" in table_names:
        listing_columns = {col["name"] for col in inspector.get_columns("listings")}
        if "image_url" in listing_columns:
            op.execute(
                sa.text(
                    "UPDATE listings SET image_url = :fallback WHERE image_url IS NULL OR TRIM(image_url) = ''"
                ).bindparams(fallback="/static/uploads/placeholder.jpg")
            )
            with op.batch_alter_table("listings") as batch_op:
                batch_op.alter_column("image_url", existing_type=sa.String(), nullable=False)

    if "favorites" in table_names:
        favorite_columns = {col["name"] for col in inspector.get_columns("favorites")}
        if {"user_id", "listing_id"}.issubset(favorite_columns):
            # Keep one row per (user_id, listing_id) before adding unique constraint.
            op.execute(
                sa.text(
                    """
                    DELETE FROM favorites
                    WHERE id NOT IN (
                        SELECT MIN(id)
                        FROM favorites
                        GROUP BY user_id, listing_id
                    )
                    """
                )
            )
            existing_uqs = {item["name"] for item in inspector.get_unique_constraints("favorites")}
            if "uq_favorites_user_listing" not in existing_uqs:
                with op.batch_alter_table("favorites") as batch_op:
                    batch_op.create_unique_constraint(
                        "uq_favorites_user_listing",
                        ["user_id", "listing_id"],
                    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "favorites" in table_names:
        existing_uqs = {item["name"] for item in inspector.get_unique_constraints("favorites")}
        if "uq_favorites_user_listing" in existing_uqs:
            with op.batch_alter_table("favorites") as batch_op:
                batch_op.drop_constraint("uq_favorites_user_listing", type_="unique")

    if "listings" in table_names:
        listing_columns = {col["name"] for col in inspector.get_columns("listings")}
        if "image_url" in listing_columns:
            with op.batch_alter_table("listings") as batch_op:
                batch_op.alter_column("image_url", existing_type=sa.String(), nullable=True)

    if "users" in table_names:
        user_columns = {col["name"] for col in inspector.get_columns("users")}
        if "active_session_expires_at" in user_columns:
            with op.batch_alter_table("users") as batch_op:
                batch_op.drop_column("active_session_expires_at")
