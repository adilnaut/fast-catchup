"""add metadata columns to priority_item

Revision ID: e2b2c7aa1eb8
Revises: 44d892f764b5
Create Date: 2023-02-27 11:27:25.361311

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2b2c7aa1eb8'
down_revision = '44d892f764b5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('priority_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('p_a_c', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('p_b_c', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('p_a_b_c', sa.Float(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('priority_item', schema=None) as batch_op:
        batch_op.drop_column('p_a_b_c')
        batch_op.drop_column('p_b_c')
        batch_op.drop_column('p_a_c')

    # ### end Alembic commands ###
