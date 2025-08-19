#!/usr/bin/env python3
"""
数据库表结构管理器
用于检查和更新数据库表结构
"""

import os
import sys
from typing import Dict, List, Set, Optional
from sqlalchemy import inspect, text, MetaData, Table, Column
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import engine, SessionLocal, Base
from models import *


class DatabaseSchemaManager:
    """数据库表结构管理器"""
    
    def __init__(self):
        """初始化数据库表结构管理器"""
        self.engine = engine
        self.inspector = inspect(engine)
        self.metadata = Base.metadata
        
    def get_existing_tables(self) -> Set[str]:
        """获取数据库中已存在的表名"""
        try:
            return set(self.inspector.get_table_names())
        except Exception as e:
            print(f"❌ 获取现有表列表失败: {e}")
            return set()
    
    def get_model_tables(self) -> Set[str]:
        """获取模型定义的表名"""
        return set(self.metadata.tables.keys())
    
    def check_table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        return table_name in self.get_existing_tables()
    
    def get_table_columns(self, table_name: str) -> Dict[str, Dict]:
        """获取表的列信息"""
        try:
            columns = self.inspector.get_columns(table_name)
            return {col['name']: col for col in columns}
        except Exception as e:
            print(f"❌ 获取表 {table_name} 列信息失败: {e}")
            return {}
    
    def get_model_table_columns(self, table_name: str) -> Dict[str, Column]:
        """获取模型定义的表列信息"""
        if table_name not in self.metadata.tables:
            return {}
        
        table = self.metadata.tables[table_name]
        return {col.name: col for col in table.columns}
    
    def compare_table_structure(self, table_name: str) -> Dict[str, List[str]]:
        """比较表结构差异"""
        existing_columns = self.get_table_columns(table_name)
        model_columns = self.get_model_table_columns(table_name)
        
        existing_col_names = set(existing_columns.keys())
        model_col_names = set(model_columns.keys())
        
        return {
            'missing_columns': list(model_col_names - existing_col_names),
            'extra_columns': list(existing_col_names - model_col_names),
            'common_columns': list(existing_col_names & model_col_names)
        }
    
    def check_database_schema(self) -> Dict[str, any]:
        """检查数据库表结构"""
        print("🔍 正在检查数据库表结构...")
        
        existing_tables = self.get_existing_tables()
        model_tables = self.get_model_tables()
        
        missing_tables = model_tables - existing_tables
        extra_tables = existing_tables - model_tables
        common_tables = existing_tables & model_tables
        
        schema_issues = {
            'missing_tables': list(missing_tables),
            'extra_tables': list(extra_tables),
            'table_structure_issues': {}
        }
        
        # 检查共同表的结构差异
        for table_name in common_tables:
            structure_diff = self.compare_table_structure(table_name)
            if structure_diff['missing_columns'] or structure_diff['extra_columns']:
                schema_issues['table_structure_issues'][table_name] = structure_diff
        
        return schema_issues
    
    def create_missing_tables(self, missing_tables: List[str]) -> bool:
        """创建缺失的表"""
        if not missing_tables:
            return True
            
        print(f"🏗️  正在创建缺失的表: {', '.join(missing_tables)}")
        
        try:
            # 只创建缺失的表
            tables_to_create = []
            for table_name in missing_tables:
                if table_name in self.metadata.tables:
                    tables_to_create.append(self.metadata.tables[table_name])
            
            if tables_to_create:
                # 创建表
                for table in tables_to_create:
                    table.create(bind=self.engine, checkfirst=True)
                    print(f"✅ 表 {table.name} 创建成功")
            
            return True
            
        except Exception as e:
            print(f"❌ 创建表失败: {e}")
            return False
    
    def add_missing_columns(self, table_structure_issues: Dict[str, Dict]) -> bool:
        """添加缺失的列（注意：这是一个简化版本，实际生产环境建议使用Alembic）"""
        if not table_structure_issues:
            return True
            
        print("🔧 正在添加缺失的列...")
        
        try:
            with self.engine.connect() as conn:
                for table_name, issues in table_structure_issues.items():
                    missing_columns = issues.get('missing_columns', [])
                    
                    if missing_columns:
                        print(f"📝 表 {table_name} 缺失列: {', '.join(missing_columns)}")
                        
                        # 获取模型定义的列信息
                        model_columns = self.get_model_table_columns(table_name)
                        
                        for col_name in missing_columns:
                            if col_name in model_columns:
                                col = model_columns[col_name]
                                
                                # 构建ALTER TABLE语句（简化版本，仅支持基本类型）
                                col_type = str(col.type)
                                nullable = "" if col.nullable else " NOT NULL"
                                default = ""
                                
                                # 处理默认值
                                if col.default is not None:
                                    if hasattr(col.default, 'arg'):
                                        if isinstance(col.default.arg, str):
                                            default = f" DEFAULT '{col.default.arg}'"
                                        else:
                                            default = f" DEFAULT {col.default.arg}"
                                
                                # 根据数据库类型构建SQL
                                if "sqlite" in str(self.engine.url):
                                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}{nullable}{default}"
                                else:
                                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}{nullable}{default}"
                                
                                try:
                                    conn.execute(text(sql))
                                    conn.commit()
                                    print(f"✅ 列 {table_name}.{col_name} 添加成功")
                                except Exception as col_e:
                                    print(f"⚠️  列 {table_name}.{col_name} 添加失败: {col_e}")
                                    # 继续处理其他列，不中断整个过程
            
            return True
            
        except Exception as e:
            print(f"❌ 添加列失败: {e}")
            return False
    
    def update_database_schema(self, schema_issues: Dict[str, any] = None) -> bool:
        """更新数据库表结构"""
        print("🔄 正在更新数据库表结构...")
        
        try:
            # 如果没有传入检查结果，则进行检查
            if schema_issues is None:
                schema_issues = self.check_database_schema()
            else:
                # 如果已经传入检查结果，就不再重复检查，直接使用传入的结果
                print("📋 使用已有的表结构检查结果...")
            
            # 报告检查结果
            if schema_issues['missing_tables']:
                print(f"📋 发现缺失的表: {', '.join(schema_issues['missing_tables'])}")
            
            if schema_issues['extra_tables']:
                print(f"📋 发现额外的表: {', '.join(schema_issues['extra_tables'])}")
            
            if schema_issues['table_structure_issues']:
                print(f"📋 发现表结构问题: {len(schema_issues['table_structure_issues'])} 个表")
                for table_name, issues in schema_issues['table_structure_issues'].items():
                    if issues['missing_columns']:
                        print(f"   - {table_name}: 缺失列 {', '.join(issues['missing_columns'])}")
                    if issues['extra_columns']:
                        print(f"   - {table_name}: 额外列 {', '.join(issues['extra_columns'])}")
            
            # 如果没有问题，直接返回
            if (not schema_issues['missing_tables'] and 
                not schema_issues['table_structure_issues']):
                print("✅ 数据库表结构正确，无需更新")
                return True
            
            # 创建缺失的表
            if schema_issues['missing_tables']:
                if not self.create_missing_tables(schema_issues['missing_tables']):
                    return False
            
            # 添加缺失的列
            if schema_issues['table_structure_issues']:
                if not self.add_missing_columns(schema_issues['table_structure_issues']):
                    print("⚠️  部分列添加失败，但继续执行")
            
            print("✅ 数据库表结构更新完成")
            return True
            
        except Exception as e:
            print(f"❌ 更新数据库表结构失败: {e}")
            return False
    
    def ensure_database_schema(self) -> bool:
        """确保数据库表结构正确"""
        print("🚀 开始数据库表结构检查和更新...")
        
        try:
            # 首先尝试创建所有表（如果不存在）
            print("🏗️  确保基础表结构存在...")
            Base.metadata.create_all(bind=self.engine)
            
            # 检查表结构（只检查一次）
            schema_issues = self.check_database_schema()
            
            # 然后更新表结构（传入检查结果，避免重复检查）
            return self.update_database_schema(schema_issues)
            
        except Exception as e:
            print(f"❌ 数据库表结构检查失败: {e}")
            return False


def ensure_database_schema() -> bool:
    """
    确保数据库表结构正确
    
    Returns:
        bool: 操作是否成功
    """
    try:
        manager = DatabaseSchemaManager()
        return manager.ensure_database_schema()
    except Exception as e:
        print(f"❌ 数据库表结构管理失败: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库表结构管理工具")
    parser.add_argument("--check", action="store_true", help="仅检查表结构，不进行更新")
    parser.add_argument("--update", action="store_true", help="检查并更新表结构")
    
    args = parser.parse_args()
    
    manager = DatabaseSchemaManager()
    
    if args.check:
        schema_issues = manager.check_database_schema()
        print("\n📊 检查结果:")
        print(f"缺失的表: {schema_issues['missing_tables']}")
        print(f"额外的表: {schema_issues['extra_tables']}")
        print(f"表结构问题: {schema_issues['table_structure_issues']}")
    elif args.update:
        success = manager.ensure_database_schema()
        sys.exit(0 if success else 1)
    else:
        print("请指定 --check 或 --update 参数")
        sys.exit(1)