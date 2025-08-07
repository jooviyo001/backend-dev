#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缺陷分页查询接口测试脚本
"""

import requests
import json
from datetime import datetime

# API基础URL
BASE_URL = "http://127.0.0.1:8000/api/v1"

def login():
    """登录获取token"""
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if response.status_code == 200:
        result = response.json()
        print(f"🔍 登录响应: {result}")
        
        # 检查多种可能的成功状态码格式
        code = result.get("code")
        if code in ["200", "20000"] or response.status_code == 200:
            data = result.get("data", {})
            token = data.get("access_token")
            if token:
                print(f"✅ 登录成功，获取到token: {token[:20]}...")
                return token
            else:
                print(f"❌ 响应中未找到access_token: {data}")
                return None
        else:
            print(f"❌ 登录失败: {result.get('message')}")
            return None
    else:
        print(f"❌ 登录请求失败: {response.status_code}")
        try:
            error_detail = response.json()
            print(f"错误详情: {error_detail}")
        except:
            print(f"错误详情: {response.text}")
        return None

def test_defects_page(token):
    """测试缺陷分页查询接口"""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n🔍 测试缺陷分页查询接口...")
    
    # 测试基本分页查询
    params = {
        "page": 1,
        "size": 10
    }
    
    response = requests.get(f"{BASE_URL}/defects/page", headers=headers, params=params)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 缺陷分页查询成功")
        print(f"📊 响应状态码: {result.get('code')}")
        print(f"📝 响应消息: {result.get('message')}")
        
        data = result.get("data", {})
        records = data.get("records", [])
        total = data.get("total", 0)
        page = data.get("page", 1)
        size = data.get("size", 10)
        
        print(f"📈 总记录数: {total}")
        print(f"📄 当前页: {page}")
        print(f"📏 每页大小: {size}")
        print(f"📋 当前页记录数: {len(records)}")
        
        if records:
            print("\n📝 缺陷记录示例:")
            for i, record in enumerate(records[:3]):  # 只显示前3条
                print(f"  {i+1}. ID: {record.get('id')}")
                print(f"     标题: {record.get('title')}")
                print(f"     状态: {record.get('status')}")
                print(f"     优先级: {record.get('priority')}")
                print(f"     类型: {record.get('type')}")
                print(f"     项目: {record.get('project_name')}")
                print(f"     负责人: {record.get('assignee_name')}")
                print(f"     报告人: {record.get('reporter_name')}")
                print(f"     创建时间: {record.get('created_at')}")
                print()
        else:
            print("📭 暂无缺陷记录")
            
    else:
        print(f"❌ 缺陷分页查询失败: {response.status_code}")
        try:
            error_detail = response.json()
            print(f"错误详情: {error_detail}")
        except:
            print(f"错误详情: {response.text}")

def test_defects_page_with_filters(token):
    """测试带筛选条件的缺陷分页查询"""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n🔍 测试带筛选条件的缺陷分页查询...")
    
    # 测试关键词搜索
    params = {
        "page": 1,
        "size": 5,
        "keyword": "bug"
    }
    
    response = requests.get(f"{BASE_URL}/defects/page", headers=headers, params=params)
    
    if response.status_code == 200:
        result = response.json()
        data = result.get("data", {})
        records = data.get("records", [])
        total = data.get("total", 0)
        
        print(f"✅ 关键词搜索成功，找到 {total} 条包含 'bug' 的缺陷")
        
        if records:
            print("📝 搜索结果:")
            for record in records:
                print(f"  - {record.get('title')} (ID: {record.get('id')})")
    else:
        print(f"❌ 关键词搜索失败: {response.status_code}")

def main():
    """主函数"""
    print("🚀 开始测试缺陷分页查询接口...")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 登录获取token
    token = login()
    if not token:
        print("❌ 无法获取token，测试终止")
        return
    
    # 测试缺陷分页查询
    test_defects_page(token)
    
    # 测试带筛选条件的查询
    test_defects_page_with_filters(token)
    
    print("\n✅ 缺陷分页查询接口测试完成!")

if __name__ == "__main__":
    main()