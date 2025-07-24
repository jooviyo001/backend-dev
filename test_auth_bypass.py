#!/usr/bin/env python3
"""
测试鉴权跳过功能
"""
import requests
import json

# 服务器地址
BASE_URL = "http://127.0.0.1:8000"

def test_auth_bypass():
    """测试鉴权跳过功能"""
    print("🔧 测试鉴权跳过功能...")
    
    # 测试需要鉴权的接口（不提供token）
    test_endpoints = [
        "/api/v1/users/list",
        "/api/v1/projects/list", 
        "/api/v1/organizations/list",
        "/api/v1/dashboard/stats"
    ]
    
    success_count = 0
    total_count = len(test_endpoints)
    
    for endpoint in test_endpoints:
        try:
            print(f"\n📡 测试接口: {endpoint}")
            
            # 不提供Authorization头，直接访问需要鉴权的接口
            response = requests.get(f"{BASE_URL}{endpoint}")
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   响应: {data.get('message', '成功')}")
                success_count += 1
            elif response.status_code == 401:
                print("   ❌ 鉴权未跳过，仍需要token")
            elif response.status_code == 403:
                print("   ❌ 权限检查未跳过")
            else:
                print(f"   ⚠️  其他错误: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ 连接失败，请确保服务器运行在 {BASE_URL}")
            return False
        except Exception as e:
            print(f"   ❌ 请求异常: {e}")
    
    print(f"\n📊 测试结果: {success_count}/{total_count} 个接口成功跳过鉴权")
    
    if success_count == total_count:
        print("✅ 鉴权跳过功能正常工作！")
        return True
    else:
        print("❌ 部分接口仍需要鉴权")
        return False

def test_basic_endpoints():
    """测试基础接口"""
    print("\n🔧 测试基础接口...")
    
    try:
        # 测试根路径
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ 根路径访问正常")
        else:
            print(f"❌ 根路径访问失败: {response.status_code}")
            
        # 测试健康检查
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ 健康检查正常")
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 基础接口测试失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 开始测试鉴权跳过功能...")
    
    # 测试基础接口
    if not test_basic_endpoints():
        print("❌ 基础接口测试失败，请检查服务器状态")
        exit(1)
    
    # 测试鉴权跳过
    if test_auth_bypass():
        print("\n🎉 所有测试通过！鉴权已成功跳过，可以开始调试了。")
    else:
        print("\n⚠️  鉴权跳过可能未完全生效，请检查配置。")