# 项目管理系统 API

一个功能完整的项目管理系统后端API，基于FastAPI构建，支持用户管理、组织管理、项目管理、任务管理等核心功能。

## 🚀 功能特性

### 核心功能
- **用户管理**: 用户注册、登录、权限管理、个人资料管理
- **组织管理**: 多组织支持、组织成员管理、角色权限控制
- **项目管理**: 项目创建、编辑、删除、成员管理、进度跟踪
- **任务管理**: 任务分配、状态跟踪、优先级管理、时间记录
- **文件管理**: 文件上传、下载、预览、版本控制
- **搜索功能**: 全文搜索、高级筛选、智能推荐
- **数据导出**: Excel、PDF、CSV等格式导出
- **仪表板**: 数据可视化、统计报表、实时监控

### 技术特性
- **高性能**: 基于FastAPI的异步架构
- **安全性**: JWT认证、RBAC权限控制、数据加密
- **可扩展**: 模块化设计、插件架构
- **监控**: 完整的日志系统、性能监控、健康检查
- **缓存**: Redis缓存、查询优化
- **任务队列**: Celery异步任务处理
- **API文档**: 自动生成的OpenAPI文档

## 📋 系统要求

- Python 3.8+
- PostgreSQL 12+ 或 MySQL 8.0+
- Redis 6.0+
- Node.js 16+ (用于前端构建)

## 🛠️ 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd backend
```

### 2. 创建虚拟环境

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖

```bash
# 生产环境
pip install -r requirements.txt

# 开发环境
pip install -r requirements-dev.txt
```

### 4. 环境配置

复制环境配置文件并修改配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置数据库、Redis等连接信息：

```env
# 应用配置
APP_NAME="项目管理系统"
APP_VERSION="1.0.0"
ENVIRONMENT="development"
DEBUG=true

# 服务器配置
SERVER_HOST="0.0.0.0"
SERVER_PORT=8000

# 数据库配置
DATABASE_URL="postgresql://user:password@localhost:5432/project_management"
# 或使用MySQL
# DATABASE_URL="mysql+pymysql://user:password@localhost:3306/project_management"

# Redis配置
REDIS_HOST="localhost"
REDIS_PORT=6379
REDIS_PASSWORD=""
REDIS_DB=0

# JWT配置
SECRET_KEY="your-secret-key-here"
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# 邮件配置
SMTP_HOST="smtp.gmail.com"
SMTP_PORT=587
SMTP_USER="your-email@gmail.com"
SMTP_PASSWORD="your-app-password"
```

### 5. 数据库初始化

```bash
# 创建数据库迁移
alembic revision --autogenerate -m "Initial migration"

# 执行迁移
alembic upgrade head

# 初始化数据（可选）
python -c "from app.core.init_db import init_database; import asyncio; asyncio.run(init_database())"
```

### 6. 启动应用

```bash
# 开发模式
python run.py --reload

# 或使用uvicorn直接启动
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
python run.py --env production --workers 4
```

### 7. 访问应用

- API文档: http://localhost:8000/docs
- ReDoc文档: http://localhost:8000/redoc
- 健康检查: http://localhost:8000/health
- 系统信息: http://localhost:8000/info

## 📁 项目结构

```
backend/
├── app/
│   ├── api/                    # API路由
│   │   └── v1/
│   │       ├── api.py         # API路由汇总
│   │       └── endpoints/     # 具体端点
│   ├── core/                  # 核心模块
│   │   ├── auth.py           # 认证相关
│   │   ├── config.py         # 配置管理
│   │   ├── database.py       # 数据库连接
│   │   ├── dependencies.py   # 依赖注入
│   │   ├── exceptions.py     # 异常处理
│   │   ├── logging.py        # 日志配置
│   │   ├── middleware.py     # 中间件
│   │   ├── redis_client.py   # Redis客户端
│   │   ├── security.py       # 安全工具
│   │   └── utils.py          # 工具函数
│   ├── models/               # 数据模型
│   ├── schemas/              # Pydantic模式
│   ├── services/             # 业务逻辑
│   └── main.py              # 应用入口
├── alembic/                  # 数据库迁移
├── tests/                    # 测试文件
├── docs/                     # 文档
├── scripts/                  # 脚本文件
├── requirements.txt          # 生产依赖
├── requirements-dev.txt      # 开发依赖
├── run.py                   # 启动脚本
├── alembic.ini              # Alembic配置
├── .env.example             # 环境变量示例
└── README.md                # 项目说明
```

## 🔧 开发指南

### 代码规范

项目使用以下工具确保代码质量：

```bash
# 代码格式化
black app/
isort app/

# 代码检查
flake8 app/
mypy app/

# 安全检查
bandit -r app/

# 依赖检查
safety check
```

### 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_users.py

# 生成覆盖率报告
pytest --cov=app --cov-report=html
```

### 数据库迁移

```bash
# 创建新迁移
alembic revision --autogenerate -m "描述变更"

# 执行迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1

# 查看迁移历史
alembic history
```

### API开发

1. 在 `app/models/` 中定义数据模型
2. 在 `app/schemas/` 中定义Pydantic模式
3. 在 `app/services/` 中实现业务逻辑
4. 在 `app/api/v1/endpoints/` 中创建API端点
5. 在 `tests/` 中编写测试

## 🚀 部署

### Docker部署

```bash
# 构建镜像
docker build -t project-management-api .

# 运行容器
docker run -d -p 8000:8000 --env-file .env project-management-api
```

### Docker Compose

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 生产环境

1. 使用Gunicorn或uWSGI作为WSGI服务器
2. 配置Nginx作为反向代理
3. 使用PostgreSQL作为生产数据库
4. 配置Redis集群
5. 设置监控和日志收集

## 📊 监控和维护

### 健康检查

- `/health` - 基本健康检查
- `/info` - 系统信息
- `/metrics` - 性能指标

### 日志

日志文件位置：
- 应用日志: `logs/app.log`
- 错误日志: `logs/error.log`
- 访问日志: `logs/access.log`

### 性能监控

- 使用Prometheus收集指标
- 使用Grafana可视化监控数据
- 配置告警规则

## 🔐 安全

### 认证和授权

- JWT Token认证
- RBAC权限控制
- API密钥认证
- OAuth2集成

### 安全措施

- HTTPS强制
- CORS配置
- 请求限流
- SQL注入防护
- XSS防护
- CSRF防护

## 📚 API文档

### 主要端点

#### 认证
- `POST /api/v1/auth/login` - 用户登录
- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/refresh` - 刷新Token
- `POST /api/v1/auth/logout` - 用户登出

#### 用户管理
- `GET /api/v1/users/` - 获取用户列表
- `GET /api/v1/users/me` - 获取当前用户信息
- `PUT /api/v1/users/me` - 更新用户信息
- `POST /api/v1/users/` - 创建用户

#### 组织管理
- `GET /api/v1/organizations/` - 获取组织列表
- `POST /api/v1/organizations/` - 创建组织
- `GET /api/v1/organizations/{id}` - 获取组织详情
- `PUT /api/v1/organizations/{id}` - 更新组织

#### 项目管理
- `GET /api/v1/projects/` - 获取项目列表
- `POST /api/v1/projects/` - 创建项目
- `GET /api/v1/projects/{id}` - 获取项目详情
- `PUT /api/v1/projects/{id}` - 更新项目

#### 任务管理
- `GET /api/v1/tasks/` - 获取任务列表
- `POST /api/v1/tasks/` - 创建任务
- `GET /api/v1/tasks/{id}` - 获取任务详情
- `PUT /api/v1/tasks/{id}` - 更新任务

### 响应格式

成功响应：
```json
{
  "success": true,
  "data": {},
  "message": "操作成功"
}
```

错误响应：
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "details": {}
  }
}
```

## 🤝 贡献

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

### 贡献指南

- 遵循代码规范
- 编写测试用例
- 更新文档
- 确保所有测试通过

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持

如果您有任何问题或建议，请：

1. 查看[文档](docs/)
2. 搜索[已知问题](issues)
3. 创建新的[Issue](issues/new)
4. 联系维护者

## 🔄 更新日志

查看 [CHANGELOG.md](CHANGELOG.md) 了解版本更新历史。

## 🙏 致谢

感谢所有为这个项目做出贡献的开发者和用户。

---

**项目管理系统** - 让项目管理更简单、更高效！