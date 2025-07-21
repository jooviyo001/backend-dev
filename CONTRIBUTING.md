# 贡献指南

## Git 工作流程

### 分支策略

我们采用 Git Flow 分支模型：

- `main` - 主分支，包含生产就绪的代码
- `develop` - 开发分支，包含最新的开发功能
- `feature/*` - 功能分支，用于开发新功能
- `hotfix/*` - 热修复分支，用于紧急修复生产问题
- `release/*` - 发布分支，用于准备新版本发布

### 开发流程

#### 1. 克隆仓库

```bash
git clone <repository-url>
cd project-management-backend
```

#### 2. 创建功能分支

```bash
# 从 develop 分支创建新的功能分支
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name
```

#### 3. 开发和提交

```bash
# 进行开发工作
# ...

# 添加文件到暂存区
git add .

# 提交更改
git commit -m "feat: 添加新功能描述"
```

#### 4. 推送分支

```bash
git push origin feature/your-feature-name
```

#### 5. 创建 Pull Request

在 GitHub/GitLab 上创建 Pull Request，将功能分支合并到 develop 分支。

### 提交信息规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

#### 类型 (type)

- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式化（不影响代码运行的变动）
- `refactor`: 重构（既不是新增功能，也不是修复 bug 的代码变动）
- `perf`: 性能优化
- `test`: 增加测试
- `chore`: 构建过程或辅助工具的变动
- `ci`: CI/CD 相关变动

#### 示例

```bash
# 新功能
git commit -m "feat(auth): 添加JWT令牌刷新功能"

# 修复bug
git commit -m "fix(tasks): 修复任务状态更新问题"

# 文档更新
git commit -m "docs: 更新API文档"

# 重构
git commit -m "refactor(models): 优化数据库模型结构"
```

### 代码审查

所有代码更改都需要通过 Pull Request 进行审查：

1. **自我审查**: 提交前检查代码质量
2. **同行审查**: 至少一个团队成员审查
3. **测试通过**: 确保所有测试通过
4. **文档更新**: 如需要，更新相关文档

### 发布流程

#### 1. 创建发布分支

```bash
git checkout develop
git pull origin develop
git checkout -b release/v1.0.0
```

#### 2. 准备发布

- 更新版本号
- 更新 CHANGELOG.md
- 进行最终测试

#### 3. 合并到主分支

```bash
# 合并到 main
git checkout main
git merge release/v1.0.0
git tag v1.0.0
git push origin main --tags

# 合并回 develop
git checkout develop
git merge release/v1.0.0
git push origin develop

# 删除发布分支
git branch -d release/v1.0.0
git push origin --delete release/v1.0.0
```

### 热修复流程

#### 1. 创建热修复分支

```bash
git checkout main
git pull origin main
git checkout -b hotfix/critical-bug-fix
```

#### 2. 修复和测试

```bash
# 进行修复
# ...

git add .
git commit -m "fix: 修复关键安全漏洞"
```

#### 3. 合并和发布

```bash
# 合并到 main
git checkout main
git merge hotfix/critical-bug-fix
git tag v1.0.1
git push origin main --tags

# 合并到 develop
git checkout develop
git merge hotfix/critical-bug-fix
git push origin develop

# 删除热修复分支
git branch -d hotfix/critical-bug-fix
git push origin --delete hotfix/critical-bug-fix
```

## 开发环境设置

### 1. 安装依赖

```bash
# 使用 UV
uv sync --extra dev

# 或使用 pip
pip install -e ".[dev]"
```

### 2. 设置 Git Hooks

```bash
# 安装 pre-commit
uv add --dev pre-commit
# 或
pip install pre-commit

# 安装 hooks
pre-commit install
```

### 3. 代码质量检查

```bash
# 代码格式化
uv run black .
uv run isort .

# 代码检查
uv run flake8 .
uv run mypy .

# 运行测试
uv run pytest
```

## 问题报告

如果发现 bug 或有功能建议，请：

1. 检查是否已有相关 issue
2. 创建新的 issue，包含：
   - 清晰的标题
   - 详细的描述
   - 重现步骤（如果是 bug）
   - 期望行为
   - 环境信息

## 联系方式

- 项目维护者：Project Management Team
- 邮箱：admin@example.com
- 项目地址：https://github.com/example/project-management-backend