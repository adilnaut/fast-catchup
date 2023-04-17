"""pscore

Revision ID: 9f8266f81ada
Revises: 92f0b791403a
Create Date: 2023-04-06 02:02:39.208229

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f8266f81ada'
down_revision = '92f0b791403a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pscore_method', sa.Text(), nullable=True))
        batch_op.drop_column('priority_method')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('priority_method', sa.TEXT(), nullable=True))
        batch_op.drop_column('pscore_method')

    # ### end Alembic commands ###
