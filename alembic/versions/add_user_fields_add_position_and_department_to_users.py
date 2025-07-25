"""add position and department to users

Revision ID: add_user_fields
Revises: 5aeb1cb303e4
Create Date: 2025-07-25 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_user_fields'
down_revision = '5aeb1cb303e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 只添加新字段，不修改现有字段类型
    op.add_column('users', sa.Column('position', sa.String(length=100), nullable=True, comment='用户岗位/职位'))
    op.add_column('users', sa.Column('department', sa.String(length=100), nullable=True, comment='用户所属部门'))


def downgrade() -> None:
    # 删除添加的字段
    op.drop_column('users', 'department')
    op.drop_column('users', 'position')