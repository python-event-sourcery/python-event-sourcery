"""empty message

Revision ID: 517def3ab014
Revises: 7c32da608e21
Create Date: 2022-09-11 14:54:41.375974

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "517def3ab014"
down_revision = "7c32da608e21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "books_read_model",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("isbn", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("copies_total", sa.Integer(), nullable=False),
        sa.Column(
            "copies_available", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("books_read_model")
    # ### end Alembic commands ###