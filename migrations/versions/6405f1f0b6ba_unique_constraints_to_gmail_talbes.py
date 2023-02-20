"""unique constraints to gmail talbes

Revision ID: 6405f1f0b6ba
Revises: 9f60da0f00dd
Create Date: 2023-02-20 01:32:10.343134

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6405f1f0b6ba'
down_revision = '9f60da0f00dd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('gmail_message_label', schema=None) as batch_op:
        batch_op.create_unique_constraint('_unique_constraint_gl', ['gmail_message_id', 'label'])

    with op.batch_alter_table('gmail_message_list_metadata', schema=None) as batch_op:
        batch_op.create_unique_constraint('_unique_constraint_gmlm_list_id', ['gmail_message_id', 'list_id'])

    with op.batch_alter_table('gmail_message_tag', schema=None) as batch_op:
        batch_op.create_unique_constraint('_unique_constraint_gm_tag', ['gmail_message_id', 'tag'])

    with op.batch_alter_table('gmail_message_text', schema=None) as batch_op:
        batch_op.add_column(sa.Column('text_hash', sa.Text(), nullable=True))
        batch_op.create_unique_constraint('_unique_constraint_gt', ['gmail_message_id', 'text_hash'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('gmail_message_text', schema=None) as batch_op:
        batch_op.drop_constraint('_unique_constraint_gt', type_='unique')
        batch_op.drop_column('text_hash')

    with op.batch_alter_table('gmail_message_tag', schema=None) as batch_op:
        batch_op.drop_constraint('_unique_constraint_gm_tag', type_='unique')

    with op.batch_alter_table('gmail_message_list_metadata', schema=None) as batch_op:
        batch_op.drop_constraint('_unique_constraint_gmlm_list_id', type_='unique')

    with op.batch_alter_table('gmail_message_label', schema=None) as batch_op:
        batch_op.drop_constraint('_unique_constraint_gl', type_='unique')

    # ### end Alembic commands ###
