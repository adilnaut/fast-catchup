"""priority constraints

Revision ID: 5aa04c3228a2
Revises: 5c5205a1c534
Create Date: 2023-02-24 11:25:59.980743

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5aa04c3228a2'
down_revision = '5c5205a1c534'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('priority_item', schema=None) as batch_op:
        batch_op.create_unique_constraint('_unique_constraint_pl_pm', ['priority_list_id', 'priority_message_id'])

    with op.batch_alter_table('priority_item_method', schema=None) as batch_op:
        batch_op.create_unique_constraint('_unique_constraint_pitem_plmethod', ['priority_item_id', 'priority_list_method_id'])

    with op.batch_alter_table('priority_message', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_id', sa.Text(), nullable=True))
        batch_op.create_unique_constraint('_unique_constraint_sess_mess', ['session_id', 'message_id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('priority_message', schema=None) as batch_op:
        batch_op.drop_constraint('_unique_constraint_sess_mess', type_='unique')
        batch_op.drop_column('session_id')

    with op.batch_alter_table('priority_item_method', schema=None) as batch_op:
        batch_op.drop_constraint('_unique_constraint_pitem_plmethod', type_='unique')

    with op.batch_alter_table('priority_item', schema=None) as batch_op:
        batch_op.drop_constraint('_unique_constraint_pl_pm', type_='unique')

    # ### end Alembic commands ###