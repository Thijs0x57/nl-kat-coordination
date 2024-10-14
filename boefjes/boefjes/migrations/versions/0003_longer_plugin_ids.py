"""Change lengths of several Char fields

Revision ID: 0002
Revises: 0001
Create Date: 2022-09-06 10:13:48.622901

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "setting", "plugin_id", existing_type=sa.String(length=32), type_=sa.String(length=64), existing_nullable=False
    )
    op.alter_column(
        "plugin_state",
        "plugin_id",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "plugin_state",
        "plugin_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    op.alter_column(
        "setting", "plugin_id", existing_type=sa.String(length=64), type_=sa.String(length=32), existing_nullable=False
    )
    # ### end Alembic commands ###
