"""drop foreign key slack user id in slack attachment

Revision ID: 77ae7e120ccd
Revises: dbdd6092af53
Create Date: 2023-02-06 16:56:37.248528

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '77ae7e120ccd'
down_revision = 'dbdd6092af53'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('slack_attachment', schema=None) as batch_op:
        batch_op.drop_constraint('fk_slack_attachment_slack_user_id_slack_user', type_='foreignkey')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('slack_attachment', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_slack_attachment_slack_user_id_slack_user', 'slack_user', ['slack_user_id'], ['id'])

    # ### end Alembic commands ###
