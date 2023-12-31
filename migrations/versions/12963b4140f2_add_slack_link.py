"""add slack link

Revision ID: 12963b4140f2
Revises: 77ae7e120ccd
Create Date: 2023-02-08 20:44:07.850533

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '12963b4140f2'
down_revision = '77ae7e120ccd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('slack_link',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slack_message_ts', sa.String(length=40), nullable=True),
    sa.Column('type', sa.Text(), nullable=True),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('text', sa.UnicodeText(), nullable=True),
    sa.Column('domain', sa.Text(), nullable=True),
    sa.Column('content', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['slack_message_ts'], ['slack_message.ts'], name=op.f('fk_slack_link_slack_message_ts_slack_message')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_slack_link'))
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('slack_link')
    # ### end Alembic commands ###
