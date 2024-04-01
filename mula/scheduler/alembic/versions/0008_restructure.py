"""restructure

Revision ID: 0008
Revises: 0007
Create Date: 2024-04-01 15:45:35.429784

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import scheduler

# revision identifiers, used by Alembic.
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "schemas",
        sa.Column("id", scheduler.utils.datastore.GUID(), nullable=False),
        sa.Column("scheduler_id", sa.String(), nullable=False),
        sa.Column("hash", sa.String(length=32), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule", sa.String(), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.drop_index("ix_items_hash", table_name="items")
    op.drop_table("items")
    op.add_column("tasks", sa.Column("schema_id", scheduler.utils.datastore.GUID(), nullable=True))
    op.add_column("tasks", sa.Column("hash", sa.String(length=32), nullable=True))
    op.add_column("tasks", sa.Column("priority", sa.Integer(), nullable=True))
    op.add_column("tasks", sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False))
    op.alter_column("tasks", "scheduler_id", existing_type=sa.VARCHAR(), nullable=False)
    op.drop_index("ix_tasks_p_item_hash", table_name="tasks")
    op.create_index(op.f("ix_tasks_hash"), "tasks", ["hash"], unique=False)
    op.create_foreign_key(None, "tasks", "schemas", ["schema_id"], ["id"], ondelete="SET NULL")
    op.drop_column("tasks", "p_item")
    op.drop_column("tasks", "type")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("tasks", sa.Column("type", sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column(
        "tasks", sa.Column("p_item", postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False)
    )
    op.drop_constraint(None, "tasks", type_="foreignkey")
    op.drop_index(op.f("ix_tasks_hash"), table_name="tasks")
    op.create_index(
        "ix_tasks_p_item_hash",
        "tasks",
        [sa.text("(p_item ->> 'hash'::text)"), sa.text("created_at DESC")],
        unique=False,
    )
    op.alter_column("tasks", "scheduler_id", existing_type=sa.VARCHAR(), nullable=True)
    op.drop_column("tasks", "data")
    op.drop_column("tasks", "priority")
    op.drop_column("tasks", "hash")
    op.drop_column("tasks", "schema_id")
    op.create_table(
        "items",
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("scheduler_id", sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column("hash", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column("priority", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "modified_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="items_pkey"),
    )
    op.create_index("ix_items_hash", "items", ["hash"], unique=False)
    op.drop_table("schemas")
    # ### end Alembic commands ###
