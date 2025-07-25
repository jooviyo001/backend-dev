"""add organization_id to users table

Revision ID: add_organization_id_to_users_simple
Revises: add_user_fields
Create Date: 2025-07-25 11:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_organization_id_to_users_simple'
down_revision = 'add_user_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加 organization_id 字段到 users 表
    op.add_column('users', sa.Column('organization_id', sa.String(length=20), nullable=True, comment='用户所属组织ID'))
    
    # 创建外键约束（如果organizations表存在）
    try:
        op.create_foreign_key(
            'fk_users_organization_id',
            'users', 'organizations',
            ['organization_id'], ['id']
        )
    except Exception:
        # 如果organizations表不存在，忽略外键创建
        pass


def downgrade() -> None:
    # 删除外键约束
    try:
        op.drop_constraint('fk_users_organization_id', 'users', type_='foreignkey')
    except Exception:
        pass
    
    # 删除 organization_id 字段
    op.drop_column('users', 'organization_id')