#!/usr/bin/env python3
"""
一键切换鉴权绕过功能
"""
import os
import sys
import re
import subprocess
import time
from pathlib import Path

class AuthToggle:
    def __init__(self):
        self.env_file = Path(".env")
        self.backup_file = Path(".env.backup")
        
    def get_current_status(self):
        """获取当前鉴权绕过状态"""
        if not self.env_file.exists():
            return False
            
        with open(self.env_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 查找 DEBUG_SKIP_AUTH 配置
        match = re.search(r'^DEBUG_SKIP_AUTH\s*=\s*(.+)$', content, re.MULTILINE)
        if match:
            value = match.group(1).strip().lower()
            return value == "true"
        return False
    
    def toggle_auth_bypass(self):
        """切换鉴权绕过状态"""
        current_status = self.get_current_status()
        new_status = not current_status
        
        print(f"🔄 当前鉴权绕过状态: {'启用' if current_status else '禁用'}")
        print(f"🎯 切换到: {'启用' if new_status else '禁用'}")
        
        # 备份当前配置
        if self.env_file.exists():
            with open(self.env_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            with open(self.backup_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"📋 已备份当前配置到 {self.backup_file}")
        
        # 更新配置
        self.update_env_file(new_status)
        
        print(f"✅ 鉴权绕过已{'启用' if new_status else '禁用'}")
        return new_status
    
    def update_env_file(self, enable_bypass):
        """更新环境变量文件"""
        if not self.env_file.exists():
            print("❌ .env 文件不存在")
            return
            
        with open(self.env_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_value = "true" if enable_bypass else "false"
        
        # 查找并替换 DEBUG_SKIP_AUTH 配置
        if re.search(r'^DEBUG_SKIP_AUTH\s*=', content, re.MULTILINE):
            # 如果存在，则替换
            content = re.sub(
                r'^DEBUG_SKIP_AUTH\s*=\s*.+$',
                f'DEBUG_SKIP_AUTH={new_value}',
                content,
                flags=re.MULTILINE
            )
        else:
            # 如果不存在，则添加
            content += f"\n# 调试模式鉴权跳过 - 设置为true时将跳过所有接口鉴权检查\nDEBUG_SKIP_AUTH={new_value}\n"
        
        with open(self.env_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def restart_server(self):
        """重启服务器"""
        print("🔄 配置已更新")
        print("💡 请手动重启服务器以应用配置:")
        print("   1. 停止当前服务器 (Ctrl+C)")
        print("   2. 运行: uv run python run.py")
        print("   或者等待服务器自动重载配置")
        
        # 不自动重启，让用户手动控制
        return
    
    def test_auth_status(self):
        """测试当前鉴权状态"""
        try:
            import requests
            
            print("🧪 测试鉴权状态...")
            
            # 测试一个需要鉴权的接口
            response = requests.get("http://127.0.0.1:8000/api/v1/users/list", timeout=5)
            
            if response.status_code == 200:
                print("✅ 鉴权已绕过 - 接口可以无token访问")
                return True
            elif response.status_code == 401:
                print("🔒 鉴权正常 - 需要提供token")
                return False
            elif response.status_code == 403:
                print("🔒 鉴权正常 - 权限检查生效")
                return False
            else:
                print(f"⚠️  未知状态 - HTTP {response.status_code}")
                return None
                
        except requests.exceptions.ConnectionError:
            print("❌ 无法连接到服务器，请确保服务器正在运行")
            return None
        except ImportError:
            print("⚠️  缺少 requests 模块，无法测试")
            return None
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            return None
    
    def show_status(self):
        """显示当前状态"""
        config_status = self.get_current_status()
        print(f"📋 配置文件状态: {'启用绕过' if config_status else '正常鉴权'}")
        
        server_status = self.test_auth_status()
        if server_status is not None:
            print(f"🌐 服务器状态: {'绕过鉴权' if server_status else '正常鉴权'}")
            
            if config_status != server_status:
                print("⚠️  配置与服务器状态不一致，可能需要重启服务器")
        
        return config_status

def main():
    toggle = AuthToggle()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "status":
            print("🔍 查看当前鉴权状态...")
            toggle.show_status()
            
        elif command == "on":
            print("🔓 启用鉴权绕过...")
            toggle.update_env_file(True)
            toggle.restart_server()
            time.sleep(3)
            toggle.test_auth_status()
            
        elif command == "off":
            print("🔒 禁用鉴权绕过...")
            toggle.update_env_file(False)
            toggle.restart_server()
            time.sleep(3)
            toggle.test_auth_status()
            
        elif command == "toggle":
            print("🔄 切换鉴权状态...")
            new_status = toggle.toggle_auth_bypass()
            toggle.restart_server()
            time.sleep(3)
            toggle.test_auth_status()
            
        elif command == "test":
            print("🧪 测试当前鉴权状态...")
            toggle.test_auth_status()
            
        else:
            print(f"❌ 未知命令: {command}")
            print_help()
    else:
        # 交互式模式
        print("🎛️  鉴权绕过控制台")
        print("=" * 50)
        
        current_status = toggle.show_status()
        print("\n可用操作:")
        print("1. 切换鉴权状态")
        print("2. 启用鉴权绕过")
        print("3. 禁用鉴权绕过")
        print("4. 测试当前状态")
        print("5. 退出")
        
        while True:
            try:
                choice = input("\n请选择操作 (1-5): ").strip()
                
                if choice == "1":
                    new_status = toggle.toggle_auth_bypass()
                    toggle.restart_server()
                    time.sleep(3)
                    toggle.test_auth_status()
                    
                elif choice == "2":
                    toggle.update_env_file(True)
                    toggle.restart_server()
                    time.sleep(3)
                    toggle.test_auth_status()
                    
                elif choice == "3":
                    toggle.update_env_file(False)
                    toggle.restart_server()
                    time.sleep(3)
                    toggle.test_auth_status()
                    
                elif choice == "4":
                    toggle.test_auth_status()
                    
                elif choice == "5":
                    print("👋 再见!")
                    break
                    
                else:
                    print("❌ 无效选择，请输入 1-5")
                    
            except KeyboardInterrupt:
                print("\n👋 再见!")
                break
            except Exception as e:
                print(f"❌ 操作失败: {e}")

def print_help():
    print("""
🎛️  鉴权绕过控制工具

用法:
    python auth_toggle.py [命令]

命令:
    status  - 查看当前鉴权状态
    on      - 启用鉴权绕过
    off     - 禁用鉴权绕过  
    toggle  - 切换鉴权状态
    test    - 测试当前鉴权状态
    
不带参数运行将进入交互式模式。

示例:
    python auth_toggle.py on      # 启用鉴权绕过
    python auth_toggle.py off     # 禁用鉴权绕过
    python auth_toggle.py status  # 查看状态
""")

if __name__ == "__main__":
    main()