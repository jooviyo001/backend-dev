"""fix_organization_type_enum

Revision ID: 535d5c526b32
Revises: 9b831bda5b05
Create Date: 2025-08-15 22:18:37.899865

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '535d5c526b32'
down_revision = '9b831bda5b05'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 修复OrganizationType枚举值，将数据库中的错误值更新为正确值
    # SQLite不支持ALTER TYPE，所以直接更新数据
    op.execute("UPDATE organizations SET type = 'organization' WHERE type = 'department' AND name LIKE '%实验室%'")


def downgrade() -> None:
    # 回滚操作
    op.execute("UPDATE organizations SET type = 'department' WHERE type = 'organization' AND name LIKE '%实验室%'")