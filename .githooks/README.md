# Git Hooks

本目录包含项目的 Git hooks，用于在代码提交和推送过程中自动执行代码质量检查和验证。

## 📋 可用的 Hooks

### 1. pre-commit
在每次提交前运行，执行以下检查：
- **Python 语法检查**：验证所有 Python 文件的语法正确性
- **代码格式化**：使用 Black 检查代码格式
- **导入排序**：使用 isort 检查导入语句排序
- **代码规范**：使用 flake8 进行代码规范检查
- **类型检查**：使用 mypy 进行静态类型检查
- **常见问题检查**：
  - 检测调试语句（`pdb.set_trace()`, `breakpoint()`, `print()` 等）
  - 检测 TODO/FIXME 注释
  - 检测潜在的密钥和敏感信息
  - 检查文件大小（警告大文件）

### 2. commit-msg
验证提交信息格式，确保遵循约定式提交（Conventional Commits）规范：
- **格式验证**：`type(scope): description`
- **支持的类型**：
  - `feat`: 新功能
  - `fix`: 错误修复
  - `docs`: 文档更改
  - `style`: 代码格式更改
  - `refactor`: 代码重构
  - `perf`: 性能优化
  - `test`: 测试相关
  - `chore`: 构建过程或辅助工具的变动
  - `build`: 构建系统或外部依赖的变动
  - `ci`: CI 配置文件和脚本的变动
  - `revert`: 回滚之前的提交

**示例**：
```
feat: add user authentication
feat(auth): implement JWT token validation
fix: resolve database connection issue
fix(api): handle null pointer exception in user service
docs: update API documentation
style: format code with black
refactor: extract user validation logic
test: add unit tests for user service
chore: update dependencies
```

### 3. pre-push
在推送到远程仓库前运行综合检查：
- **所有 pre-commit 检查**
- **安全检查**：
  - 使用 bandit 进行安全漏洞扫描
  - 使用 safety 检查依赖项漏洞
- **测试执行**：
  - 运行 pytest 或 unittest
  - 检查测试覆盖率
- **文件检查**：
  - 检测大文件（建议使用 Git LFS）
  - 扫描潜在的密钥泄露
- **提交信息验证**：验证推送中所有提交的信息格式

## 🚀 安装 Hooks

### 方法 1：使用安装脚本（推荐）

**Linux/macOS**：
```bash
# 进入项目根目录
cd /path/to/your/project

# 运行安装脚本
bash .githooks/install-hooks.sh
```

**Windows**：
```cmd
REM 进入项目根目录
cd C:\path\to\your\project

REM 运行安装脚本
.githooks\install-hooks.bat
```

### 方法 2：手动安装

```bash
# 配置 Git 使用项目 hooks 目录（Git 2.9+）
git config core.hooksPath .githooks

# 或者复制到 .git/hooks/ 目录
cp .githooks/pre-commit .git/hooks/
cp .githooks/commit-msg .git/hooks/
cp .githooks/pre-push .git/hooks/

# 确保 hooks 可执行
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/commit-msg
chmod +x .git/hooks/pre-push
```

## 📦 依赖要求

为了充分利用所有检查功能，请安装以下开发依赖：

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 或者单独安装
pip install black isort flake8 mypy pytest bandit safety coverage
```

## 🔧 配置

### 代码格式化配置

**pyproject.toml**：
```toml
[tool.black]
line-length = 88
target-version = ['py38']
include = '\.pyi?$'
extend-exclude = '''
(
  /(
      \.eggs
    | \.git
    | \.hg
    | \.mypy_cache
    | \.tox
    | \.venv
    | _build
    | buck-out
    | build
    | dist
  )/
)
'''

[tool.isort]
profile = "black"
line_length = 88
multi_line_output = 3
include_trailing_comma = true
force_grid_wrap = 0
use_parentheses = true
ensure_newline_before_comments = true

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

**setup.cfg** 或 **.flake8**：
```ini
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude = 
    .git,
    __pycache__,
    .venv,
    venv,
    .eggs,
    *.egg,
    build,
    dist
```

### 测试配置

**pytest.ini**：
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --strict-config
    --verbose
    --tb=short
    --cov=app
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=80
```

## 🎯 使用指南

### 正常工作流程

1. **开发代码**
2. **添加到暂存区**：`git add .`
3. **提交**：`git commit -m "feat: add new feature"`
   - pre-commit hook 自动运行检查
   - commit-msg hook 验证提交信息格式
4. **推送**：`git push`
   - pre-push hook 运行综合检查

### 绕过 Hooks（不推荐）

在紧急情况下，可以临时绕过 hooks：

```bash
# 绕过 pre-commit 和 commit-msg hooks
git commit --no-verify -m "emergency fix"

# 绕过 pre-push hook
git push --no-verify
```

### 修复常见问题

**代码格式问题**：
```bash
# 自动格式化代码
black .
isort .
```

**导入排序问题**：
```bash
# 自动排序导入
isort .
```

**代码规范问题**：
```bash
# 查看详细的 flake8 报告
flake8 . --statistics
```

**类型检查问题**：
```bash
# 运行 mypy 检查
mypy . --show-error-codes
```

## 🔍 故障排除

### Hook 没有运行

1. **检查 hooks 是否可执行**：
   ```bash
   ls -la .git/hooks/
   # 或
   ls -la .githooks/
   ```

2. **检查 Git 配置**：
   ```bash
   git config --get core.hooksPath
   ```

3. **重新安装 hooks**：
   ```bash
   bash .githooks/install-hooks.sh
   ```

### 依赖缺失错误

```bash
# 安装缺失的工具
pip install black isort flake8 mypy pytest bandit safety

# 或安装完整的开发依赖
pip install -r requirements-dev.txt
```

### 权限问题（Linux/macOS）

```bash
# 确保 hooks 有执行权限
chmod +x .githooks/*
chmod +x .git/hooks/*
```

### Windows 特定问题

1. **使用 Git Bash** 而不是 Command Prompt
2. **确保 Python 在 PATH 中**
3. **使用 `.bat` 版本的安装脚本**

## 📚 最佳实践

1. **定期更新工具**：
   ```bash
   pip install --upgrade black isort flake8 mypy pytest bandit safety
   ```

2. **团队协作**：
   - 确保所有团队成员都安装了 hooks
   - 在项目文档中说明 hooks 的使用
   - 定期审查和更新 hooks 配置

3. **CI/CD 集成**：
   - 在 CI 管道中运行相同的检查
   - 确保本地检查与 CI 检查一致

4. **渐进式采用**：
   - 对现有项目，可以先从警告开始
   - 逐步提高代码质量标准
   - 为遗留代码设置例外规则

## 🔗 相关资源

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Black Code Formatter](https://black.readthedocs.io/)
- [isort](https://pycqa.github.io/isort/)
- [Flake8](https://flake8.pycqa.org/)
- [MyPy](https://mypy.readthedocs.io/)
- [Bandit](https://bandit.readthedocs.io/)
- [Safety](https://pyup.io/safety/)
- [Git Hooks Documentation](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks)

## 🤝 贡献

如果您发现 hooks 有问题或想要改进，请：

1. 创建 issue 描述问题
2. 提交 pull request 包含修复
3. 确保新的 hooks 经过充分测试
4. 更新相关文档

---

**注意**：这些 hooks 旨在提高代码质量和一致性。如果遇到问题，请先尝试修复代码，而不是绕过检查。