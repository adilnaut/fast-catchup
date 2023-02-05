"""empty message

Revision ID: 33153c9c95f9
Revises: c96bd8c107b0
Create Date: 2023-02-05 21:53:32.147752

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '33153c9c95f9'
down_revision = 'c96bd8c107b0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('gmail_attachment', schema=None) as batch_op:
        batch_op.drop_constraint('pk_gmail_attachment', type_='primary')
        batch_op.create_primary_key('pk_gmail_attachment_2', ['md5','gmail_message_id'])




def downgrade():

    with op.batch_alter_table('gmail_attachment', schema=None) as batch_op:
            batch_op.drop_constraint('pk_gmail_attachment_2', type_='primary')
            batch_op.create_primary_key('pk_gmail_attachment', ['md5'])
