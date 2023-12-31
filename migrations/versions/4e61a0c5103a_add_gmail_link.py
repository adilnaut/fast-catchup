"""Add gmail link

Revision ID: 4e61a0c5103a
Revises: 04d06e6391c1
Create Date: 2023-02-05 16:04:37.294512

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4e61a0c5103a'
down_revision = '04d06e6391c1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('gmail_link',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('gmail_message_id', sa.String(length=240), nullable=True),
    sa.Column('link', sa.Text(), nullable=True),
    sa.Column('domain', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['gmail_message_id'], ['gmail_message.id'], name=op.f('fk_gmail_link_gmail_message_id_gmail_message')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_gmail_link'))
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('gmail_link')
    # ### end Alembic commands ###
