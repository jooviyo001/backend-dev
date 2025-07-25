import requests
import json

BASE_URL = "http://localhost:8000"

def get_admin_token():
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
    response.raise_for_status()
    return response.json()["data"]["access_token"]

def get_user_info(user_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/v1/users/{user_id}", headers=headers)
    response.raise_for_status()
    return response.json()["data"]

def update_user_avatar(user_id, token, avatar_url):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    update_data = {"avatar": avatar_url}
    response = requests.put(f"{BASE_URL}/api/v1/users/{user_id}", headers=headers, data=json.dumps(update_data))
    response.raise_for_status()
    return response.json()["data"]

def main():
    try:
        print("获取管理员token...")
        admin_token = get_admin_token()
        print("管理员token获取成功。")

        # 获取admin用户的ID
        headers = {"Authorization": f"Bearer {admin_token}"}
        me_response = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
        me_response.raise_for_status()
        admin_user_id = me_response.json()["data"]["id"]
        print(f"获取到admin用户ID: {admin_user_id}")

        print("检查初始用户头像...")
        initial_user_info = get_user_info(admin_user_id, admin_token)
        initial_avatar = initial_user_info.get("avatar")
        print(f"初始头像: {initial_avatar}")
        assert initial_avatar is None
        print("初始用户头像为None，符合预期。")

        new_avatar_url = "http://example.com/new_avatar.jpg"
        print(f"更新用户头像为: {new_avatar_url}...")
        updated_user = update_user_avatar(admin_user_id, admin_token, new_avatar_url)
        print("头像更新成功。")

        print("再次检查更新后的用户头像...")
        user_info_after_update = get_user_info(admin_user_id, admin_token)
        updated_avatar = user_info_after_update.get("avatar")
        print(f"更新后头像: {updated_avatar}")

        assert updated_avatar == new_avatar_url
        print("测试通过：头像已成功更新并获取。")

    except requests.exceptions.RequestException as e:
        print(f"API请求失败: {e}")
        if e.response:
            print(f"响应内容: {e.response.text}")
    except AssertionError:
        print("测试失败：头像更新不一致。")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main()