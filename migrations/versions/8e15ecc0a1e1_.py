"""empty message

Revision ID: 8e15ecc0a1e1
Revises: 939082703ed3
Create Date: 2023-02-16 13:38:11.152521

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e15ecc0a1e1'
down_revision = '939082703ed3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('gmail_user', schema=None) as batch_op:
        batch_op.drop_constraint('pk_gmail_user', type_='primary')
        batch_op.create_primary_key('pk_gmail_user_2', ['email','platform_id'])

    with op.batch_alter_table('slack_user', schema=None) as batch_op:
        batch_op.drop_constraint('pk_slack_user', type_='primary')
        batch_op.create_primary_key('pk_slack_user_2', ['id','platform_id'])

    with op.batch_alter_table('slack_channel', schema=None) as batch_op:
        batch_op.drop_constraint('pk_slack_channel', type_='primary')
        batch_op.create_primary_key('pk_slack_channel_2', ['id','platform_id'])

def downgrade():
    with op.batch_alter_table('gmail_user', schema=None) as batch_op:
            batch_op.drop_constraint('pk_gmail_user_2', type_='primary')
            batch_op.create_primary_key('pk_gmail_user', ['email'])

    with op.batch_alter_table('slack_user', schema=None) as batch_op:
            batch_op.drop_constraint('pk_slack_user_2', type_='primary')
            batch_op.create_primary_key('pk_slack_user', ['id'])

    with op.batch_alter_table('slack_channel', schema=None) as batch_op:
            batch_op.drop_constraint('pk_slack_channel_2', type_='primary')
            batch_op.create_primary_key('pk_slack_channel', ['id'])
