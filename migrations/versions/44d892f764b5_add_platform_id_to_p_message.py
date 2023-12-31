"""add platform id to p message

Revision ID: 44d892f764b5
Revises: 884d0c47ef35
Create Date: 2023-02-25 15:19:56.592408

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '44d892f764b5'
down_revision = '884d0c47ef35'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('priority_message', schema=None) as batch_op:
        batch_op.add_column(sa.Column('platform_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_priority_message_platform_id_platform'), 'platform', ['platform_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('priority_message', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_priority_message_platform_id_platform'), type_='foreignkey')
        batch_op.drop_column('platform_id')

    # ### end Alembic commands ###
