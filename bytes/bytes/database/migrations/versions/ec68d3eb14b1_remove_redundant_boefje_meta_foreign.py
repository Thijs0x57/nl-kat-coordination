"""Remove redundant boefje_meta foreign key from normalizer meta

Revision ID: ec68d3eb14b1
Revises: fa64454868a9
Create Date: 2023-04-13 13:36:50.196441

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "ec68d3eb14b1"
down_revision = "fa64454868a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###

    conn = op.get_bind()
    with conn.begin():
        # A small part of older raw files were saved with the boefje_meta id as filename
        conn.execute(
            "INSERT INTO raw_file (id, boefje_meta_id) SELECT DISTINCT boefje_meta_id, boefje_meta_id "
            "FROM normalizer_meta WHERE raw_file_id IS NULL;"
        )
        conn.execute("UPDATE normalizer_meta SET raw_file_id = boefje_meta_id WHERE raw_file_id IS NULL;")

    op.alter_column("normalizer_meta", "raw_file_id", existing_type=postgresql.UUID(), nullable=False)
    op.drop_constraint("normalizer_meta_boefje_meta_id_fkey", "normalizer_meta", type_="foreignkey")
    op.drop_column("normalizer_meta", "boefje_meta_id")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "normalizer_meta", sa.Column("boefje_meta_id", postgresql.UUID(), autoincrement=False, nullable=False)
    )
    op.create_foreign_key(
        "normalizer_meta_boefje_meta_id_fkey",
        "normalizer_meta",
        "boefje_meta",
        ["boefje_meta_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("normalizer_meta", "raw_file_id", existing_type=postgresql.UUID(), nullable=True)
    # ### end Alembic commands ###
