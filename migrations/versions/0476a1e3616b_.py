"""empty message

Revision ID: 0476a1e3616b
Revises: f6a4b8423ea0
Create Date: 2023-02-19 02:46:03.284969

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0476a1e3616b'
down_revision = 'f6a4b8423ea0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('slack_message', schema=None) as batch_op:
        batch_op.create_primary_key('pk_slack_message', ['ts'])



def downgrade():
    with op.batch_alter_table('slack_message', schema=None) as batch_op:
        batch_op.drop_constraint('pk_slack_message', type_='primary')
