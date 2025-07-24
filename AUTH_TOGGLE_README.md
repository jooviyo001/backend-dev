# 鉴权绕过一键切换工具使用说明

## 功能概述
这个工具可以让你快速切换后端API的鉴权模式，在开发和测试时非常有用。

## 文件说明
- `auth_toggle.py` - 主要的切换脚本
- `auth_on.bat` - 启用鉴权绕过的批处理文件
- `auth_off.bat` - 禁用鉴权绕过的批处理文件
- `auth_toggle.bat` - 切换鉴权状态的批处理文件
- `auth_status.bat` - 查看当前鉴权状态的批处理文件

## 使用方法

### 方法一：双击批处理文件（推荐）
1. **启用鉴权绕过**：双击 `auth_on.bat`
2. **禁用鉴权绕过**：双击 `auth_off.bat`
3. **切换鉴权状态**：双击 `auth_toggle.bat`
4. **查看当前状态**：双击 `auth_status.bat`

### 方法二：命令行使用
```bash
# 查看当前状态
uv run python auth_toggle.py status

# 启用鉴权绕过
uv run python auth_toggle.py on

# 禁用鉴权绕过
uv run python auth_toggle.py off

# 切换状态
uv run python auth_toggle.py toggle

# 测试鉴权状态
uv run python auth_toggle.py test

# 交互式菜单
uv run python auth_toggle.py
```

## 状态说明
- **启用绕过**：所有API接口都可以无需token访问
- **禁用绕过**：API接口需要正确的token才能访问

## 注意事项
1. 修改配置后需要重启服务器才能生效
2. 工具会自动备份当前配置到 `.env.backup`
3. 仅在开发环境使用，生产环境请勿启用绕过模式
4. 如果服务器支持热重载，配置可能会自动生效

## 故障排除
如果遇到问题，请检查：
1. 服务器是否正在运行
2. `.env` 文件是否存在
3. 是否有足够的文件权限
4. 网络连接是否正常

## 安全提醒
⚠️ **重要**：鉴权绕过功能仅用于开发和测试，请确保在生产环境中禁用此功能！