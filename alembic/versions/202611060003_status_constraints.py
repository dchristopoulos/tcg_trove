"""Add reservation and inquiry status constraints

Revision ID: 202611060003
Revises: 202611060002
Create Date: 2026-11-06 00:03:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op  # type: ignore[import-not-found]

# revision identifiers, used by Alembic.
revision: str = "202611060003"
down_revision: str | Sequence[str] | None = "202611060002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "reservations" in table_names:
        op.execute(
            sa.text(
                """
                UPDATE reservations
                SET status = 'pending'
                WHERE status IS NULL OR status NOT IN ('pending', 'confirmed', 'cancelled', 'rejected')
                """
            )
        )
        check_names = {item["name"] for item in inspector.get_check_constraints("reservations")}
        if "ck_reservations_status_valid" not in check_names:
            with op.batch_alter_table("reservations") as batch_op:
                batch_op.create_check_constraint(
                    "ck_reservations_status_valid",
                    "status IN ('pending', 'confirmed', 'cancelled', 'rejected')",
                )

    if "inquiries" in table_names:
        op.execute(
            sa.text(
                """
                UPDATE inquiries
                SET status = 'open'
                WHERE status IS NULL OR status NOT IN ('open', 'in_progress', 'responded', 'closed')
                """
            )
        )
        check_names = {item["name"] for item in inspector.get_check_constraints("inquiries")}
        if "ck_inquiries_status_valid" not in check_names:
            with op.batch_alter_table("inquiries") as batch_op:
                batch_op.create_check_constraint(
                    "ck_inquiries_status_valid",
                    "status IN ('open', 'in_progress', 'responded', 'closed')",
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "inquiries" in table_names:
        check_names = {item["name"] for item in inspector.get_check_constraints("inquiries")}
        if "ck_inquiries_status_valid" in check_names:
            with op.batch_alter_table("inquiries") as batch_op:
                batch_op.drop_constraint("ck_inquiries_status_valid", type_="check")

    if "reservations" in table_names:
        check_names = {item["name"] for item in inspector.get_check_constraints("reservations")}
        if "ck_reservations_status_valid" in check_names:
            with op.batch_alter_table("reservations") as batch_op:
                batch_op.drop_constraint("ck_reservations_status_valid", type_="check")
