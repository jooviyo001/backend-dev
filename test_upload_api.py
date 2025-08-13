#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试上传接口的脚本
"""

import requests
import json
import io

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
        print(f"登录响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        if result.get("code") == "200":
            return result["data"]["access_token"]
        else:
            print(f"❌ 登录失败: {result.get('message', '未知错误')}")
            return None
    else:
        print(f"❌ 登录请求失败: {response.status_code}")
        print(f"响应内容: {response.text}")
        return None

def create_test_image():
    """创建一个测试图片（简单的PNG格式字节数据）"""
    # 创建一个最小的PNG文件字节数据
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
    return io.BytesIO(png_data)

def test_upload_info(token):
    """测试获取上传配置信息"""
    print("\n📋 测试获取上传配置信息...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/uploads/info", headers=headers)
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return True
    else:
        print(f"❌ 请求失败: {response.text}")
        return False

def test_single_image_upload(token):
    """测试单个图片上传"""
    print("\n📤 测试单个图片上传...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 创建测试图片
    test_image = create_test_image()
    
    files = {
        'file': ('test_image.png', test_image, 'image/png')
    }
    
    response = requests.post(f"{BASE_URL}/uploads/image", headers=headers, files=files)
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return result.get("data", {}).get("filename")
    else:
        print(f"❌ 上传失败: {response.text}")
        return None

def test_batch_image_upload(token):
    """测试批量图片上传"""
    print("\n📤 测试批量图片上传...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 创建多个测试图片
    files = []
    for i in range(3):
        test_image = create_test_image()
        files.append(('files', (f'test_image_{i}.png', test_image, 'image/png')))
    
    response = requests.post(f"{BASE_URL}/uploads/images", headers=headers, files=files)
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return [file_info["filename"] for file_info in result.get("data", {}).get("files", [])]
    else:
        print(f"❌ 批量上传失败: {response.text}")
        return []

def test_file_access(token, filename):
    """测试文件访问"""
    print(f"\n🔍 测试文件访问: {filename}")
    
    response = requests.get(f"{BASE_URL}/uploads/files/{filename}")
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print(f"✅ 文件访问成功，文件大小: {len(response.content)} 字节")
        print(f"Content-Type: {response.headers.get('content-type')}")
        return True
    else:
        print(f"❌ 文件访问失败: {response.text}")
        return False

def test_file_delete(token, filename):
    """测试文件删除"""
    print(f"\n🗑️ 测试文件删除: {filename}")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.delete(f"{BASE_URL}/uploads/files/{filename}", headers=headers)
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 文件删除成功: {result.get('message')}")
        return True
    else:
        print(f"❌ 文件删除失败: {response.text}")
        return False

def main():
    """主函数"""
    print("🚀 开始测试上传接口...")
    
    # 登录获取token
    print("\n🔐 正在登录...")
    token = login()
    if not token:
        print("❌ 无法获取认证token，测试终止")
        return
    
    print(f"✅ 登录成功，获取到token")
    
    # 测试获取上传配置
    test_upload_info(token)
    
    # 测试单个图片上传
    uploaded_filename = test_single_image_upload(token)
    
    # 测试批量图片上传
    batch_filenames = test_batch_image_upload(token)
    
    # 测试文件访问
    if uploaded_filename:
        test_file_access(token, uploaded_filename)
    
    # 测试文件删除
    if uploaded_filename:
        test_file_delete(token, uploaded_filename)
    
    # 清理批量上传的文件
    for filename in batch_filenames:
        test_file_delete(token, filename)
    
    print("\n✅ 上传接口测试完成！")

if __name__ == "__main__":
    main()