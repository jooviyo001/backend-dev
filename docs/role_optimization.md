# 角色模块数据库优化建议

## 概述

本文档提供了角色模块的数据库优化建议，包括索引创建、查询优化和性能监控等方面。

## 数据库索引建议

### 1. 角色表(roles)索引

```sql
-- 角色编码唯一索引（已存在）
CREATE UNIQUE INDEX idx_roles_code ON roles(code);

-- 角色名称唯一索引（已存在）
CREATE UNIQUE INDEX idx_roles_name ON roles(name);

-- 角色状态索引（用于快速查询激活角色）
CREATE INDEX idx_roles_is_active ON roles(is_active);

-- 复合索引：状态+创建时间（用于分页查询）
CREATE INDEX idx_roles_active_created ON roles(is_active, created_at);

-- 角色编码前缀索引（用于系统角色快速识别）
CREATE INDEX idx_roles_code_prefix ON roles(code varchar_pattern_ops);
```

### 2. 用户表(users)相关索引

```sql
-- 用户角色外键索引（用于角色用户数量统计）
CREATE INDEX idx_users_role_id ON users(role_id);

-- 复合索引：角色ID+用户状态（用于统计激活用户）
CREATE INDEX idx_users_role_status ON users(role_id, is_active);
```

## 查询优化策略

### 1. 角色列表查询优化

**原始查询问题：**
- N+1查询问题：为每个角色单独查询用户数量
- 多次数据库访问

**优化方案：**
```python
# 使用子查询优化
user_count_subquery = (
    db.query(
        User.role_id,
        func.count(User.id).label('user_count')
    )
    .group_by(User.role_id)
    .subquery()
)

# 左连接获取角色和用户数量
roles_with_count = (
    db.query(
        Role,
        func.coalesce(user_count_subquery.c.user_count, 0).label('user_count')
    )
    .outerjoin(user_count_subquery, Role.id == user_count_subquery.c.role_id)
    .all()
)
```

### 2. 角色统计查询优化

**优化前：**
```python
# 多次查询
total_roles = db.query(Role).count()
active_roles = db.query(Role).filter(Role.is_active == True).count()
system_roles = db.query(Role).filter(Role.code.in_(system_codes)).count()
```

**优化后：**
```python
# 单次查询获取所有统计数据
stats_query = db.query(
    func.count(Role.id).label('total_roles'),
    func.sum(func.case([(Role.is_active == True, 1)], else_=0)).label('active_roles'),
    func.sum(func.case([(Role.code.in_(system_codes), 1)], else_=0)).label('system_roles')
).first()
```

### 3. 批量查询优化

**空值检查：**
```python
def get_roles_by_codes(self, codes: List[str]) -> List[Role]:
    if not codes:  # 避免空列表查询
        return []
    return self.db.query(Role).filter(Role.code.in_(codes)).all()
```

**批量ID查询：**
```python
def get_roles_by_ids(self, role_ids: List[str]) -> List[Role]:
    if not role_ids:
        return []
    return self.db.query(Role).filter(Role.id.in_(role_ids)).all()
```

## 性能监控建议

### 1. 慢查询监控

监控以下查询的执行时间：
- 角色列表查询（包含用户数量统计）
- 角色统计查询
- 角色权限验证查询
- 批量角色查询

### 2. 关键指标

- **查询响应时间**：< 100ms（角色列表）、< 50ms（单个角色）
- **并发查询数**：监控高峰期查询并发量
- **索引使用率**：确保查询使用了合适的索引
- **缓存命中率**：角色权限缓存命中率 > 90%

### 3. 性能测试场景

```python
# 测试场景1：大量角色列表查询
def test_role_list_performance():
    start_time = time.time()
    roles = role_service.get_all_roles()
    end_time = time.time()
    assert end_time - start_time < 0.1  # 100ms内完成

# 测试场景2：批量角色查询
def test_batch_role_query():
    role_ids = [str(uuid.uuid4()) for _ in range(100)]
    start_time = time.time()
    roles = role_service.get_roles_by_ids(role_ids)
    end_time = time.time()
    assert end_time - start_time < 0.05  # 50ms内完成
```

## 缓存策略建议

### 1. 角色信息缓存

```python
# Redis缓存键设计
ROLE_CACHE_KEY = "role:{role_id}"
ROLE_LIST_CACHE_KEY = "roles:list"
ROLE_STATS_CACHE_KEY = "roles:stats"

# 缓存过期时间
ROLE_CACHE_TTL = 3600  # 1小时
ROLE_STATS_CACHE_TTL = 300  # 5分钟
```

### 2. 缓存更新策略

- **写入时更新**：角色创建/更新/删除时清除相关缓存
- **定时刷新**：角色统计信息定时刷新
- **缓存预热**：系统启动时预加载常用角色信息

## 数据库连接池优化

### 1. 连接池配置

```python
# SQLAlchemy连接池配置
engine = create_engine(
    DATABASE_URL,
    pool_size=20,          # 连接池大小
    max_overflow=30,       # 最大溢出连接数
    pool_timeout=30,       # 获取连接超时时间
    pool_recycle=3600,     # 连接回收时间
    pool_pre_ping=True     # 连接预检查
)
```

### 2. 连接管理最佳实践

- 使用连接池避免频繁创建/销毁连接
- 及时关闭数据库会话
- 监控连接池使用情况
- 避免长时间持有连接

## 总结

通过以上优化措施，角色模块的性能将得到显著提升：

1. **查询性能提升**：通过索引和查询优化，减少查询时间50-80%
2. **并发能力增强**：通过连接池和缓存，提升系统并发处理能力
3. **资源使用优化**：减少数据库负载，提高系统整体性能
4. **用户体验改善**：更快的响应时间，更好的用户体验

建议按优先级逐步实施这些优化措施，并持续监控性能指标。