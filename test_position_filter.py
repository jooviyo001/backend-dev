#!/usr/bin/env python3
"""
测试职位筛选功能
"""
import requests
import json

# 配置
BASE_URL = "http://localhost:8000/api/v1"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    """登录获取token"""
    login_data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if response.status_code == 200:
        return response.json()["data"]["access_token"]
    else:
        print(f"登录失败: {response.text}")
        return None

def test_position_filter():
    """测试职位筛选功能"""
    token = login()
    if not token:
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print("=== 测试职位筛选功能 ===")
    
    # 1. 获取职位列表
    print("\n1. 获取职位列表:")
    response = requests.get(f"{BASE_URL}/users/positions", headers=headers)
    if response.status_code == 200:
        positions = response.json()["data"]
        print(f"可用职位: {positions}")
    else:
        print(f"获取职位列表失败: {response.text}")
        return
    
    # 2. 测试不带职位筛选的用户列表
    print("\n2. 获取所有用户:")
    response = requests.get(f"{BASE_URL}/users/page", headers=headers)
    if response.status_code == 200:
        all_users = response.json()["data"]["records"]
        print(f"总用户数: {len(all_users)}")
        for user in all_users:
            print(f"  - {user['name']} ({user['username']}) - 职位: {user.get('position', '未设置')}")
    else:
        print(f"获取用户列表失败: {response.text}")
        return
    
    # 3. 测试职位筛选
    if positions:
        test_position = positions[0]  # 使用第一个职位进行测试
        print(f"\n3. 筛选职位为 '{test_position}' 的用户:")
        response = requests.get(f"{BASE_URL}/users/page?position={test_position}", headers=headers)
        if response.status_code == 200:
            filtered_users = response.json()["data"]["records"]
            print(f"筛选后用户数: {len(filtered_users)}")
            for user in filtered_users:
                print(f"  - {user['name']} ({user['username']}) - 职位: {user.get('position', '未设置')}")
        else:
            print(f"职位筛选失败: {response.text}")
    
    # 4. 测试不存在的职位筛选
    print(f"\n4. 筛选不存在的职位 '测试职位':")
    response = requests.get(f"{BASE_URL}/users/page?position=测试职位", headers=headers)
    if response.status_code == 200:
        filtered_users = response.json()["data"]["records"]
        print(f"筛选后用户数: {len(filtered_users)}")
    else:
        print(f"职位筛选失败: {response.text}")

if __name__ == "__main__":
    test_position_filter()