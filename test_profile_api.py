import requests
import json
from datetime import datetime

def login_and_get_token():
    """登录获取访问令牌"""
    login_url = "http://localhost:8000/api/v1/auth/login"
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        response = requests.post(login_url, json=login_data)
        if response.status_code == 200:
            result = response.json()
            if result.get('data') and result['data'].get('access_token'):
                return result['data']['access_token']
        print(f"登录失败: {response.text}")
        return None
    except Exception as e:
        print(f"登录异常: {e}")
        return None

# 先登录获取token
print("=== 正在登录获取访问令牌 ===")
token = login_and_get_token()
if not token:
    print("无法获取访问令牌，测试终止")
    exit()

print(f"获取到访问令牌: {token[:20]}...")
print()

# 测试数据 - 使用用户提供的实际数据格式
test_data = {
    "username": "admin",
    "name": "asd",
    "email": "admin@example.com",
    "phone": "1520000001",
    "position": "asd",
    "department": "asd",
    "avatar": None,
    "full_name": "系统管理员",
    "role": "admin",
    "id": "USER_206386416517648384",
    "is_active": True,
    "is_verified": True,
    "last_login": "2025-07-25T00:47:28.040233",
    "created_at": "2025-07-23T12:25:56",
    "updated_at": "2025-07-24T16:47:28"
}

# 发送PUT请求
url = "http://localhost:8000/api/v1/user/profile"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

print("=== 测试 /api/v1/user/profile 接口 ===")
print(f"请求URL: {url}")
print(f"请求方法: PUT")
print(f"请求数据: {json.dumps(test_data, indent=2, ensure_ascii=False)}")
print("\n正在发送请求...")

try:
    response = requests.put(url, json=test_data, headers=headers)
    print(f"\n状态码: {response.status_code}")
    print(f"响应内容: {response.text}")
    
    if response.status_code == 200:
        result = response.json()
        print("\n=== API 测试成功 ===")
        print(f"消息: {result.get('message')}")
        
        # 验证时间格式
        data = result.get('data', {})
        time_fields = ['last_login', 'created_at', 'updated_at']
        print("\n时间格式验证:")
        for field in time_fields:
            if field in data and data[field]:
                try:
                    datetime.strptime(data[field], "%Y-%m-%d %H:%M:%S")
                    print(f"✓ {field} 时间格式正确: {data[field]}")
                except ValueError:
                    print(f"✗ {field} 时间格式错误: {data[field]}")
            else:
                print(f"- {field} 字段为空或不存在")
    else:
        print("\n=== API 测试失败 ===")
        try:
            error_data = response.json()
            print(f"错误详情: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
        except:
            print(f"错误信息: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("\n❌ 连接失败，请确保服务器正在运行")
    print("提示: 请先运行 'python run.py' 启动服务器")
except Exception as e:
    print(f"\n❌ 请求异常: {e}")