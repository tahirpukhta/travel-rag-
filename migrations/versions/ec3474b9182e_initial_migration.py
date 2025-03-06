"""initial migration

Revision ID: ec3474b9182e
Revises: 
Create Date: 2025-03-06 16:14:24.958657

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'ec3474b9182e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('faqs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hotel_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key(None, 'hotels', ['hotel_id'], ['id'])

    with op.batch_alter_table('hotels', schema=None) as batch_op:
        batch_op.add_column(sa.Column('latitude', sa.Numeric(precision=10, scale=8), nullable=True))
        batch_op.add_column(sa.Column('longitude', sa.Numeric(precision=11, scale=8), nullable=True))
        batch_op.add_column(sa.Column('check_in_time', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('check_out_time', sa.Time(), nullable=True))
        batch_op.create_index(batch_op.f('ix_hotels_location'), ['location'], unique=False)
        batch_op.create_index(batch_op.f('ix_hotels_name'), ['name'], unique=False)
        batch_op.drop_column('amenities')

    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rating', sa.Numeric(precision=2, scale=1), nullable=True))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch_op.drop_index('idx_review_content', mysql_prefix='FULLTEXT')
        batch_op.drop_index('idx_reviews_hotel')
        batch_op.drop_index('idx_reviews_user')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contact_number', sa.String(length=20), nullable=False))
        batch_op.add_column(sa.Column('role', sa.Enum('customer', 'property_owner', name='user_role_enum'), nullable=True))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_login', sa.DateTime(), nullable=True))
        batch_op.drop_index('email')
        batch_op.drop_index('username')
        batch_op.create_index(batch_op.f('ix_users_contact_number'), ['contact_number'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_username'))
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.drop_index(batch_op.f('ix_users_contact_number'))
        batch_op.create_index('username', ['username'], unique=True)
        batch_op.create_index('email', ['email'], unique=True)
        batch_op.drop_column('last_login')
        batch_op.drop_column('created_at')
        batch_op.drop_column('role')
        batch_op.drop_column('contact_number')

    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.create_index('idx_reviews_user', ['user_id'], unique=False)
        batch_op.create_index('idx_reviews_hotel', ['hotel_id'], unique=False)
        batch_op.create_index('idx_review_content', ['content'], unique=False, mysql_prefix='FULLTEXT')
        batch_op.drop_column('created_at')
        batch_op.drop_column('rating')

    with op.batch_alter_table('hotels', schema=None) as batch_op:
        batch_op.add_column(sa.Column('amenities', mysql.VARCHAR(length=200), nullable=True))
        batch_op.drop_index(batch_op.f('ix_hotels_name'))
        batch_op.drop_index(batch_op.f('ix_hotels_location'))
        batch_op.drop_column('check_out_time')
        batch_op.drop_column('check_in_time')
        batch_op.drop_column('longitude')
        batch_op.drop_column('latitude')

    with op.batch_alter_table('faqs', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('hotel_id')

    # ### end Alembic commands ###
