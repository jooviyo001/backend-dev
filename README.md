# 项目管理系统后端API

基于 FastAPI 构建的项目管理系统后端服务，提供用户认证、项目管理、任务管理、组织管理等功能。

## 功能特性

- **用户认证**: 用户注册、登录、JWT令牌认证
- **用户管理**: 用户增删改查、角色管理、权限控制
- **组织管理**: 组织创建、成员管理、权限控制
- **项目管理**: 项目创建、成员管理、状态跟踪
- **任务管理**: 任务增删改查、状态管理、优先级设置
- **文件管理**: 任务附件上传、下载
- **评论系统**: 任务评论功能
- **统计分析**: 任务统计、项目进度分析

## 技术栈

- **框架**: FastAPI
- **数据库**: SQLAlchemy (支持 SQLite、PostgreSQL、MySQL)
- **认证**: JWT (JSON Web Tokens)
- **密码加密**: bcrypt
- **API文档**: Swagger UI / ReDoc
- **异步支持**: asyncio

## 快速开始

### 1. 环境要求

- Python 3.8+
- pip

### 2. 安装依赖

推荐使用 UV 来管理依赖（更快的包管理器）：

```bash
# 安装 UV（如果还没有安装）
pip install uv

# 使用 UV 安装依赖
uv sync
```

或者使用传统的 pip 方式：

```bash
pip install -e .
```

### 3. 环境配置

复制环境配置文件并修改配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置数据库连接和其他参数。

### 4. 初始化数据库

```bash
# 使用 UV
uv run python init_db.py

# 或者使用传统方式
python init_db.py
```

这将创建数据库表并插入初始数据，包括默认管理员账户。

### 5. 启动服务

```bash
# 使用 UV
uv run python run.py

# 或者使用传统方式
python run.py

# 或者直接使用 uvicorn
uv run uvicorn main:app --reload
```

### 6. 访问API文档

启动服务后，可以通过以下地址访问API文档：

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## 默认账户

初始化数据库后，系统会创建以下默认账户：

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| admin | admin123 | 管理员 | 系统管理员，拥有所有权限 |
| manager | manager123 | 项目经理 | 项目管理权限 |
| developer1 | dev123 | 开发者 | 普通开发者权限 |
| developer2 | dev123 | 开发者 | 普通开发者权限 |

**注意**: 生产环境请及时修改默认密码！

## API 接口概览

### 认证相关
- `POST /auth/login` - 用户登录
- `POST /auth/register` - 用户注册
- `POST /auth/logout` - 用户登出
- `GET /auth/me` - 获取当前用户信息
- `PUT /auth/change-password` - 修改密码
- `POST /auth/refresh` - 刷新令牌

### 用户管理
- `GET /users` - 获取用户列表
- `GET /users/{user_id}` - 获取用户详情
- `POST /users` - 创建用户
- `PUT /users/{user_id}` - 更新用户信息
- `DELETE /users/{user_id}` - 删除用户

### 组织管理
- `GET /organizations` - 获取组织列表
- `GET /organizations/{org_id}` - 获取组织详情
- `POST /organizations` - 创建组织
- `PUT /organizations/{org_id}` - 更新组织信息
- `DELETE /organizations/{org_id}` - 删除组织

### 项目管理
- `GET /projects` - 获取项目列表
- `GET /projects/{project_id}` - 获取项目详情
- `POST /projects` - 创建项目
- `PUT /projects/{project_id}` - 更新项目信息
- `DELETE /projects/{project_id}` - 删除项目

### 任务管理
- `GET /tasks` - 获取任务列表
- `GET /tasks/{task_id}` - 获取任务详情
- `POST /tasks` - 创建任务
- `PUT /tasks/{task_id}` - 更新任务信息
- `DELETE /tasks/{task_id}` - 删除任务

## 项目结构

```
backend/
├── main.py                 # FastAPI 应用入口
├── run.py                  # 启动脚本
├── init_db.py             # 数据库初始化脚本
├── requirements.txt        # 依赖包列表
├── .env.example           # 环境配置示例
├── README.md              # 项目说明文档
├── models/                # 数据模型
│   ├── __init__.py
│   ├── database.py        # 数据库配置
│   └── models.py          # SQLAlchemy 模型
├── schemas/               # Pydantic 模式
│   ├── __init__.py
│   └── schemas.py         # API 请求/响应模式
├── routers/               # 路由模块
│   ├── __init__.py
│   ├── auth.py           # 认证路由
│   ├── users.py          # 用户管理路由
│   ├── organizations.py  # 组织管理路由
│   ├── projects.py       # 项目管理路由
│   └── tasks.py          # 任务管理路由
└── utils/                 # 工具模块
    ├── __init__.py
    └── auth.py           # 认证工具
```

## 开发说明

### 开发环境设置

安装开发依赖：

```bash
# 使用 UV 安装开发依赖
uv sync --extra dev

# 或者使用 pip
pip install -e ".[dev]"
```

### 代码质量工具

```bash
# 代码格式化
uv run black .
uv run isort .

# 代码检查
uv run flake8 .
uv run mypy .

# 运行测试
uv run pytest

# 测试覆盖率
uv run coverage run -m pytest
uv run coverage report
```

### 数据库迁移

如果修改了数据模型，需要进行数据库迁移：

```bash
# 生成迁移文件
uv run alembic revision --autogenerate -m "描述变更内容"

# 执行迁移
uv run alembic upgrade head
```

### 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DATABASE_URL | 数据库连接字符串 | sqlite:///./project_management.db |
| SECRET_KEY | JWT 密钥 | 需要设置 |
| ALGORITHM | JWT 算法 | HS256 |
| ACCESS_TOKEN_EXPIRE_MINUTES | 令牌过期时间(分钟) | 30 |
| DEBUG | 调试模式 | True |
| ALLOWED_ORIGINS | 允许的跨域来源 | http://localhost:3000 |

### 权限说明

系统定义了以下角色：

- **ADMIN**: 系统管理员，拥有所有权限
- **MANAGER**: 项目经理，可以管理项目和任务
- **DEVELOPER**: 开发者，可以查看和更新分配给自己的任务
- **VIEWER**: 观察者，只有查看权限

## 部署说明

### 生产环境部署

1. 设置生产环境变量
2. 使用 PostgreSQL 或 MySQL 数据库
3. 配置反向代理 (Nginx)
4. 使用 Gunicorn 或 uWSGI 作为 WSGI 服务器
5. 配置 HTTPS

### Docker 部署

```dockerfile
# Dockerfile 示例
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "run.py"]
```

## 许可证

MIT License

## Git 版本管理

### 分支策略

项目采用 Git Flow 工作流：

- `main` - 主分支，生产环境代码
- `develop` - 开发分支，集成最新功能
- `feature/*` - 功能分支
- `hotfix/*` - 热修复分支
- `release/*` - 发布分支

### 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```bash
# 新功能
git commit -m "feat(auth): 添加JWT令牌刷新功能"

# 修复bug
git commit -m "fix(tasks): 修复任务状态更新问题"

# 文档更新
git commit -m "docs: 更新API文档"
```

### 开发流程

```bash
# 1. 创建功能分支
git checkout develop
git checkout -b feature/your-feature

# 2. 开发和提交
git add .
git commit -m "feat: 添加新功能"

# 3. 推送分支
git push origin feature/your-feature

# 4. 创建 Pull Request
```

详细的贡献指南请参考 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 更新日志

查看 [CHANGELOG.md](CHANGELOG.md) 了解版本更新历史。

## 贡献

欢迎提交 Issue 和 Pull Request！请先阅读 [贡献指南](CONTRIBUTING.md)。