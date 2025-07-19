# 依赖管理说明

本项目使用多个依赖文件来管理不同环境和用途的依赖包。

## 依赖文件说明

### 1. requirements.txt
**主要依赖文件**
- 包含项目运行所需的所有核心依赖
- 版本已锁定为当前测试通过的版本
- 适用于生产环境部署

### 2. requirements-core.txt
**最小核心依赖**
- 包含项目运行的最小必需依赖
- 适用于容器化部署或资源受限环境
- 不包含开发工具和可选功能

### 3. requirements-dev.txt
**开发环境依赖**
- 继承 requirements.txt 的所有依赖
- 包含开发、测试、代码质量工具
- 仅在开发环境中使用

## 安装指南

### 生产环境
```bash
# 使用主要依赖文件
uv pip install -r requirements.txt

# 或使用最小核心依赖（推荐用于容器）
uv pip install -r requirements-core.txt
```

### 开发环境
```bash
# 安装开发依赖（包含所有功能）
uv pip install -r requirements-dev.txt
```

### 特定功能安装
```bash
# 仅安装核心功能
uv pip install -r requirements-core.txt

# 添加数据库迁移工具
uv pip install alembic==1.12.1

# 添加PostgreSQL支持
uv pip install psycopg2-binary==2.9.9

# 添加性能分析工具
uv pip install py-spy memory-profiler
```

## 依赖版本说明

### 已解决的依赖冲突
- `aiolock==1.4.0` - 版本不存在，已移除
- `safety==2.3.5/3.0.1` - 与 pydantic 2.x 存在冲突，已注释
- `psycopg2` - 需要 PostgreSQL 开发环境，改用 aiosqlite

### 核心版本锁定
- FastAPI: 0.116.1
- Pydantic: 2.11.7
- SQLAlchemy: 2.0.41
- Uvicorn: 0.35.0

## 更新依赖

### 检查当前安装的包
```bash
uv pip list
```

### 更新特定包
```bash
uv pip install --upgrade package_name
```

### 生成新的依赖文件
```bash
# 导出当前环境的所有包
uv pip freeze > requirements-current.txt
```

## 注意事项

1. **版本兼容性**: 所有版本都经过测试，确保相互兼容
2. **安全性**: 定期检查依赖的安全漏洞
3. **性能**: 生产环境建议使用 requirements-core.txt 以减少依赖
4. **开发**: 开发时使用 requirements-dev.txt 获得完整功能

## 故障排除

### 常见问题

1. **依赖冲突**
   ```bash
   # 清理环境重新安装
   uv pip uninstall -r requirements.txt
   uv pip install -r requirements.txt
   ```

2. **缺少系统依赖**
   ```bash
   # Windows 用户可能需要安装 Visual Studio Build Tools
   # Linux 用户可能需要安装 python3-dev, libpq-dev 等
   ```

3. **Redis 连接失败**
   - Redis 是可选依赖，项目可以在没有 Redis 的情况下运行
   - 如需使用缓存功能，请安装并启动 Redis 服务

## 贡献指南

更新依赖时请：
1. 测试新版本的兼容性
2. 更新相应的依赖文件
3. 更新此文档
4. 提交 PR 时说明变更原因