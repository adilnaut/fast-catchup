"""change gmessage columns.

Revision ID: 25645b91153a
Revises: ce983d4b9f88
Create Date: 2023-02-02 20:07:42.875095

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '25645b91153a'
down_revision = 'ce983d4b9f88'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('gmail_message', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mime_type', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('gmail_message', schema=None) as batch_op:
        batch_op.drop_column('mime_type')

    # ### end Alembic commands ###
