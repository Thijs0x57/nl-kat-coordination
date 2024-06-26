"""Introduce Boefje and Normalizer models

Revision ID: 6f99834a4a5a
Revises: 7c88b9cd96aa
Create Date: 2024-05-28 13:00:12.338182

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6f99834a4a5a"
down_revision = "7c88b9cd96aa"
branch_labels = None
depends_on = None


scan_level_enum = sa.Enum("0", "1", "2", "3", "4", name="scan_level")


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###

    op.create_table(
        "boefje",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scan_level", scan_level_enum, nullable=False),
        sa.Column("consumes", sa.ARRAY(sa.String(length=128)), nullable=False),
        sa.Column("produces", sa.ARRAY(sa.String(length=128)), nullable=False),
        sa.Column("environment_keys", sa.ARRAY(sa.String(length=128)), nullable=False),
        sa.Column("oci_image", sa.String(length=256), nullable=True),
        sa.Column("oci_arguments", sa.ARRAY(sa.String(length=128)), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id"),
    )
    op.create_table(
        "normalizer",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("consumes", sa.ARRAY(sa.String(length=128)), nullable=False),
        sa.Column("produces", sa.ARRAY(sa.String(length=128)), nullable=False),
        sa.Column("environment_keys", sa.ARRAY(sa.String(length=128)), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("normalizer")
    op.drop_table("boefje")
    scan_level_enum.drop(op.get_bind(), checkfirst=False)
    # ### end Alembic commands ###
