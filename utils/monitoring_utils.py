"""监控和健康检查工具模块

提供系统监控、性能指标、健康检查、告警通知等功能
"""
import time
import psutil
import asyncio
from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
from functools import wraps
import logging
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from models.database import get_db
from utils.logging_middleware import logger
from utils.config_manager import config_manager


class HealthStatus(str, Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class MetricType(str, Enum):
    """指标类型枚举"""
    COUNTER = "counter"        # 计数器
    GAUGE = "gauge"            # 仪表盘
    HISTOGRAM = "histogram"    # 直方图
    SUMMARY = "summary"        # 摘要
    TIMER = "timer"            # 计时器


class AlertLevel(str, Enum):
    """告警级别枚举"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthCheck:
    """健康检查项"""
    name: str
    check_func: Callable[[], bool]
    description: str = ""
    timeout: int = 30
    interval: int = 60
    enabled: bool = True
    last_check: Optional[datetime] = None
    last_status: HealthStatus = HealthStatus.UNKNOWN
    last_error: Optional[str] = None
    check_count: int = 0
    success_count: int = 0
    
    def execute(self) -> Dict[str, Any]:
        """执行健康检查"""
        start_time = time.time()
        self.check_count += 1
        
        try:
            # 设置超时
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"健康检查超时: {self.name}")
            
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.timeout)
            
            try:
                result = self.check_func()
                signal.alarm(0)  # 取消超时
                
                if result:
                    self.last_status = HealthStatus.HEALTHY
                    self.success_count += 1
                    self.last_error = None
                else:
                    self.last_status = HealthStatus.CRITICAL
                    self.last_error = "检查返回False"
                
            except TimeoutError as e:
                self.last_status = HealthStatus.CRITICAL
                self.last_error = str(e)
                result = False
            
        except Exception as e:
            self.last_status = HealthStatus.CRITICAL
            self.last_error = str(e)
            result = False
        
        finally:
            signal.alarm(0)  # 确保取消超时
        
        duration = time.time() - start_time
        self.last_check = datetime.now()
        
        return {
            "name": self.name,
            "status": self.last_status.value,
            "success": result,
            "duration": round(duration, 3),
            "error": self.last_error,
            "timestamp": self.last_check.isoformat()
        }
    
    def get_success_rate(self) -> float:
        """获取成功率"""
        if self.check_count == 0:
            return 0.0
        return (self.success_count / self.check_count) * 100


@dataclass
class Metric:
    """指标"""
    name: str
    metric_type: MetricType
    value: Union[int, float]
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    description: str = ""
    unit: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "value": self.value,
            "labels": self.labels,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "unit": self.unit
        }


@dataclass
class Alert:
    """告警"""
    id: str
    title: str
    message: str
    level: AlertLevel
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def resolve(self):
        """解决告警"""
        self.resolved = True
        self.resolved_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "level": self.level.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata
        }


class SystemMonitor:
    """系统监控器"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.metrics_history = deque(maxlen=1000)
        self.alerts_history = deque(maxlen=500)
        self.active_alerts = {}
        
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            # CPU信息
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # 内存信息
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # 磁盘信息
            disk = psutil.disk_usage('/')
            
            # 网络信息
            network = psutil.net_io_counters()
            
            # 进程信息
            process = psutil.Process()
            process_memory = process.memory_info()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "uptime": str(datetime.now() - self.start_time),
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": cpu_count,
                    "frequency": {
                        "current": cpu_freq.current if cpu_freq else None,
                        "min": cpu_freq.min if cpu_freq else None,
                        "max": cpu_freq.max if cpu_freq else None
                    }
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "usage_percent": memory.percent,
                    "swap": {
                        "total": swap.total,
                        "used": swap.used,
                        "usage_percent": swap.percent
                    }
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "usage_percent": (disk.used / disk.total) * 100
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                },
                "process": {
                    "pid": process.pid,
                    "memory_rss": process_memory.rss,
                    "memory_vms": process_memory.vms,
                    "cpu_percent": process.cpu_percent(),
                    "num_threads": process.num_threads(),
                    "create_time": datetime.fromtimestamp(process.create_time()).isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"获取系统信息失败: {str(e)}")
            return {"error": str(e)}
    
    def collect_metrics(self) -> List[Metric]:
        """收集系统指标"""
        metrics = []
        current_time = datetime.now()
        
        try:
            # CPU指标
            cpu_percent = psutil.cpu_percent()
            metrics.append(Metric(
                name="system_cpu_usage",
                metric_type=MetricType.GAUGE,
                value=cpu_percent,
                timestamp=current_time,
                description="CPU使用率",
                unit="percent"
            ))
            
            # 内存指标
            memory = psutil.virtual_memory()
            metrics.append(Metric(
                name="system_memory_usage",
                metric_type=MetricType.GAUGE,
                value=memory.percent,
                timestamp=current_time,
                description="内存使用率",
                unit="percent"
            ))
            
            metrics.append(Metric(
                name="system_memory_available",
                metric_type=MetricType.GAUGE,
                value=memory.available,
                timestamp=current_time,
                description="可用内存",
                unit="bytes"
            ))
            
            # 磁盘指标
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            metrics.append(Metric(
                name="system_disk_usage",
                metric_type=MetricType.GAUGE,
                value=disk_usage_percent,
                timestamp=current_time,
                description="磁盘使用率",
                unit="percent"
            ))
            
            # 网络指标
            network = psutil.net_io_counters()
            metrics.append(Metric(
                name="system_network_bytes_sent",
                metric_type=MetricType.COUNTER,
                value=network.bytes_sent,
                timestamp=current_time,
                description="网络发送字节数",
                unit="bytes"
            ))
            
            metrics.append(Metric(
                name="system_network_bytes_recv",
                metric_type=MetricType.COUNTER,
                value=network.bytes_recv,
                timestamp=current_time,
                description="网络接收字节数",
                unit="bytes"
            ))
            
            # 进程指标
            process = psutil.Process()
            process_memory = process.memory_info()
            
            metrics.append(Metric(
                name="process_memory_rss",
                metric_type=MetricType.GAUGE,
                value=process_memory.rss,
                timestamp=current_time,
                description="进程内存使用量",
                unit="bytes"
            ))
            
            metrics.append(Metric(
                name="process_cpu_percent",
                metric_type=MetricType.GAUGE,
                value=process.cpu_percent(),
                timestamp=current_time,
                description="进程CPU使用率",
                unit="percent"
            ))
            
            # 保存到历史记录
            for metric in metrics:
                self.metrics_history.append(metric)
            
        except Exception as e:
            logger.error(f"收集系统指标失败: {str(e)}")
        
        return metrics
    
    def get_metrics_history(self, metric_name: str = None, 
                           limit: int = 100) -> List[Dict[str, Any]]:
        """获取指标历史"""
        history = list(self.metrics_history)
        
        if metric_name:
            history = [m for m in history if m.name == metric_name]
        
        # 按时间倒序排列
        history.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [m.to_dict() for m in history[:limit]]
    
    def create_alert(self, title: str, message: str, level: AlertLevel, 
                     source: str, metadata: Dict[str, Any] = None) -> Alert:
        """创建告警"""
        alert_id = f"{source}_{int(time.time())}_{hash(title)}"
        
        alert = Alert(
            id=alert_id,
            title=title,
            message=message,
            level=level,
            source=source,
            metadata=metadata or {}
        )
        
        self.active_alerts[alert_id] = alert
        self.alerts_history.append(alert)
        
        logger.warning(f"创建告警: {title} - {message}")
        return alert
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolve()
            del self.active_alerts[alert_id]
            logger.info(f"告警已解决: {alert.title}")
            return True
        return False
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """获取活跃告警"""
        return [alert.to_dict() for alert in self.active_alerts.values()]
    
    def get_alerts_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取告警历史"""
        history = list(self.alerts_history)
        history.sort(key=lambda x: x.timestamp, reverse=True)
        return [alert.to_dict() for alert in history[:limit]]
    
    def check_thresholds(self):
        """检查阈值并创建告警"""
        try:
            # CPU使用率检查
            cpu_percent = psutil.cpu_percent()
            if cpu_percent > 90:
                self.create_alert(
                    title="CPU使用率过高",
                    message=f"CPU使用率达到 {cpu_percent:.1f}%",
                    level=AlertLevel.CRITICAL,
                    source="system_monitor",
                    metadata={"cpu_percent": cpu_percent}
                )
            elif cpu_percent > 80:
                self.create_alert(
                    title="CPU使用率警告",
                    message=f"CPU使用率达到 {cpu_percent:.1f}%",
                    level=AlertLevel.WARNING,
                    source="system_monitor",
                    metadata={"cpu_percent": cpu_percent}
                )
            
            # 内存使用率检查
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                self.create_alert(
                    title="内存使用率过高",
                    message=f"内存使用率达到 {memory.percent:.1f}%",
                    level=AlertLevel.CRITICAL,
                    source="system_monitor",
                    metadata={"memory_percent": memory.percent}
                )
            elif memory.percent > 80:
                self.create_alert(
                    title="内存使用率警告",
                    message=f"内存使用率达到 {memory.percent:.1f}%",
                    level=AlertLevel.WARNING,
                    source="system_monitor",
                    metadata={"memory_percent": memory.percent}
                )
            
            # 磁盘使用率检查
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > 95:
                self.create_alert(
                    title="磁盘空间不足",
                    message=f"磁盘使用率达到 {disk_percent:.1f}%",
                    level=AlertLevel.CRITICAL,
                    source="system_monitor",
                    metadata={"disk_percent": disk_percent}
                )
            elif disk_percent > 85:
                self.create_alert(
                    title="磁盘空间警告",
                    message=f"磁盘使用率达到 {disk_percent:.1f}%",
                    level=AlertLevel.WARNING,
                    source="system_monitor",
                    metadata={"disk_percent": disk_percent}
                )
            
        except Exception as e:
            logger.error(f"阈值检查失败: {str(e)}")


class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self.checks: Dict[str, HealthCheck] = {}
        self.executor = ThreadPoolExecutor(max_workers=5)
        self._running = False
        self._check_thread = None
        
        # 注册默认健康检查
        self._register_default_checks()
    
    def _register_default_checks(self):
        """注册默认健康检查"""
        # 数据库连接检查
        self.register_check(
            name="database",
            check_func=self._check_database,
            description="数据库连接检查",
            timeout=10,
            interval=30
        )
        
        # 系统资源检查
        self.register_check(
            name="system_resources",
            check_func=self._check_system_resources,
            description="系统资源检查",
            timeout=5,
            interval=60
        )
        
        # 磁盘空间检查
        self.register_check(
            name="disk_space",
            check_func=self._check_disk_space,
            description="磁盘空间检查",
            timeout=5,
            interval=300
        )
    
    def _check_database(self) -> bool:
        """检查数据库连接"""
        try:
            db = next(get_db())
            result = db.execute(text("SELECT 1"))
            return result.fetchone() is not None
        except Exception as e:
            logger.error(f"数据库健康检查失败: {str(e)}")
            return False
    
    def _check_system_resources(self) -> bool:
        """检查系统资源"""
        try:
            # 检查CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 95:
                return False
            
            # 检查内存使用率
            memory = psutil.virtual_memory()
            if memory.percent > 95:
                return False
            
            return True
        except Exception as e:
            logger.error(f"系统资源健康检查失败: {str(e)}")
            return False
    
    def _check_disk_space(self) -> bool:
        """检查磁盘空间"""
        try:
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            return disk_percent < 98
        except Exception as e:
            logger.error(f"磁盘空间健康检查失败: {str(e)}")
            return False
    
    def register_check(self, name: str, check_func: Callable[[], bool], 
                       description: str = "", timeout: int = 30, 
                       interval: int = 60, enabled: bool = True):
        """注册健康检查"""
        self.checks[name] = HealthCheck(
            name=name,
            check_func=check_func,
            description=description,
            timeout=timeout,
            interval=interval,
            enabled=enabled
        )
    
    def unregister_check(self, name: str) -> bool:
        """取消注册健康检查"""
        if name in self.checks:
            del self.checks[name]
            return True
        return False
    
    def run_check(self, name: str) -> Optional[Dict[str, Any]]:
        """运行单个健康检查"""
        if name not in self.checks:
            return None
        
        check = self.checks[name]
        if not check.enabled:
            return None
        
        return check.execute()
    
    def run_all_checks(self) -> Dict[str, Any]:
        """运行所有健康检查"""
        results = {}
        overall_status = HealthStatus.HEALTHY
        
        for name, check in self.checks.items():
            if not check.enabled:
                continue
            
            try:
                result = check.execute()
                results[name] = result
                
                # 更新整体状态
                if result["status"] == HealthStatus.CRITICAL.value:
                    overall_status = HealthStatus.CRITICAL
                elif result["status"] == HealthStatus.WARNING.value and overall_status != HealthStatus.CRITICAL:
                    overall_status = HealthStatus.WARNING
                    
            except Exception as e:
                logger.error(f"健康检查执行失败 {name}: {str(e)}")
                results[name] = {
                    "name": name,
                    "status": HealthStatus.CRITICAL.value,
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                overall_status = HealthStatus.CRITICAL
        
        return {
            "overall_status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "checks": results
        }
    
    def get_check_status(self, name: str) -> Optional[Dict[str, Any]]:
        """获取检查状态"""
        if name not in self.checks:
            return None
        
        check = self.checks[name]
        return {
            "name": check.name,
            "description": check.description,
            "enabled": check.enabled,
            "interval": check.interval,
            "timeout": check.timeout,
            "last_check": check.last_check.isoformat() if check.last_check else None,
            "last_status": check.last_status.value,
            "last_error": check.last_error,
            "check_count": check.check_count,
            "success_count": check.success_count,
            "success_rate": check.get_success_rate()
        }
    
    def get_all_checks_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有检查状态"""
        return {name: self.get_check_status(name) for name in self.checks.keys()}
    
    def start_periodic_checks(self):
        """启动定期检查"""
        if self._running:
            return
        
        self._running = True
        self._check_thread = threading.Thread(target=self._periodic_check_loop, daemon=True)
        self._check_thread.start()
        logger.info("健康检查定期任务已启动")
    
    def stop_periodic_checks(self):
        """停止定期检查"""
        self._running = False
        if self._check_thread:
            self._check_thread.join(timeout=5)
        logger.info("健康检查定期任务已停止")
    
    def _periodic_check_loop(self):
        """定期检查循环"""
        while self._running:
            try:
                current_time = datetime.now()
                
                for name, check in self.checks.items():
                    if not check.enabled:
                        continue
                    
                    # 检查是否需要执行
                    if (check.last_check is None or 
                        (current_time - check.last_check).total_seconds() >= check.interval):
                        
                        # 异步执行检查
                        self.executor.submit(check.execute)
                
                # 等待一段时间再检查
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"定期健康检查循环异常: {str(e)}")
                time.sleep(30)


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.request_times = deque(maxlen=1000)
        self.error_counts = defaultdict(int)
        self.endpoint_stats = defaultdict(lambda: {
            'count': 0,
            'total_time': 0,
            'min_time': float('inf'),
            'max_time': 0,
            'errors': 0
        })
    
    def record_request(self, endpoint: str, method: str, duration: float, 
                       status_code: int, error: str = None):
        """记录请求性能"""
        timestamp = datetime.now()
        
        # 记录请求时间
        self.request_times.append({
            'endpoint': endpoint,
            'method': method,
            'duration': duration,
            'status_code': status_code,
            'timestamp': timestamp,
            'error': error
        })
        
        # 更新端点统计
        key = f"{method} {endpoint}"
        stats = self.endpoint_stats[key]
        stats['count'] += 1
        stats['total_time'] += duration
        stats['min_time'] = min(stats['min_time'], duration)
        stats['max_time'] = max(stats['max_time'], duration)
        
        if status_code >= 400 or error:
            stats['errors'] += 1
            self.error_counts[status_code] += 1
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        if not self.request_times:
            return {
                'total_requests': 0,
                'avg_response_time': 0,
                'min_response_time': 0,
                'max_response_time': 0,
                'error_rate': 0,
                'requests_per_minute': 0
            }
        
        # 计算基本统计
        durations = [req['duration'] for req in self.request_times]
        total_requests = len(durations)
        avg_duration = sum(durations) / total_requests
        min_duration = min(durations)
        max_duration = max(durations)
        
        # 计算错误率
        error_count = sum(1 for req in self.request_times if req['status_code'] >= 400 or req['error'])
        error_rate = (error_count / total_requests) * 100 if total_requests > 0 else 0
        
        # 计算每分钟请求数
        now = datetime.now()
        recent_requests = [req for req in self.request_times 
                          if (now - req['timestamp']).total_seconds() <= 60]
        requests_per_minute = len(recent_requests)
        
        return {
            'total_requests': total_requests,
            'avg_response_time': round(avg_duration, 3),
            'min_response_time': round(min_duration, 3),
            'max_response_time': round(max_duration, 3),
            'error_rate': round(error_rate, 2),
            'requests_per_minute': requests_per_minute,
            'error_counts': dict(self.error_counts)
        }
    
    def get_endpoint_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取端点统计"""
        result = {}
        
        for endpoint, stats in self.endpoint_stats.items():
            if stats['count'] > 0:
                avg_time = stats['total_time'] / stats['count']
                error_rate = (stats['errors'] / stats['count']) * 100
                
                result[endpoint] = {
                    'count': stats['count'],
                    'avg_time': round(avg_time, 3),
                    'min_time': round(stats['min_time'], 3),
                    'max_time': round(stats['max_time'], 3),
                    'errors': stats['errors'],
                    'error_rate': round(error_rate, 2)
                }
        
        return result
    
    def get_slow_requests(self, threshold: float = 1.0, limit: int = 10) -> List[Dict[str, Any]]:
        """获取慢请求"""
        slow_requests = [req for req in self.request_times if req['duration'] > threshold]
        slow_requests.sort(key=lambda x: x['duration'], reverse=True)
        
        return [{
            'endpoint': req['endpoint'],
            'method': req['method'],
            'duration': req['duration'],
            'status_code': req['status_code'],
            'timestamp': req['timestamp'].isoformat(),
            'error': req['error']
        } for req in slow_requests[:limit]]


# 全局实例
system_monitor = SystemMonitor()
health_checker = HealthChecker()
performance_monitor = PerformanceMonitor()


# 装饰器
def monitor_performance(endpoint_name: str = None):
    """性能监控装饰器"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            endpoint = endpoint_name or func.__name__
            error = None
            status_code = 200
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                status_code = 500
                raise
            finally:
                duration = time.time() - start_time
                performance_monitor.record_request(
                    endpoint=endpoint,
                    method="ASYNC",
                    duration=duration,
                    status_code=status_code,
                    error=error
                )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            endpoint = endpoint_name or func.__name__
            error = None
            status_code = 200
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                status_code = 500
                raise
            finally:
                duration = time.time() - start_time
                performance_monitor.record_request(
                    endpoint=endpoint,
                    method="SYNC",
                    duration=duration,
                    status_code=status_code,
                    error=error
                )
        
        # 根据函数类型返回对应的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def health_check(name: str, description: str = "", timeout: int = 30):
    """健康检查装饰器"""
    def decorator(func):
        # 注册健康检查
        health_checker.register_check(
            name=name,
            check_func=func,
            description=description,
            timeout=timeout
        )
        return func
    
    return decorator


def alert_on_error(title: str, level: AlertLevel = AlertLevel.ERROR):
    """错误告警装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                system_monitor.create_alert(
                    title=title,
                    message=str(e),
                    level=level,
                    source=func.__name__,
                    metadata={
                        'function': func.__name__,
                        'args': str(args),
                        'kwargs': str(kwargs)
                    }
                )
                raise
        
        return wrapper
    return decorator


# 常用监控函数
def get_system_health() -> Dict[str, Any]:
    """获取系统健康状态"""
    return {
        'system_info': system_monitor.get_system_info(),
        'health_checks': health_checker.run_all_checks(),
        'performance': performance_monitor.get_performance_stats(),
        'active_alerts': system_monitor.get_active_alerts()
    }


def get_monitoring_dashboard() -> Dict[str, Any]:
    """获取监控仪表盘数据"""
    return {
        'timestamp': datetime.now().isoformat(),
        'system': {
            'info': system_monitor.get_system_info(),
            'metrics': [m.to_dict() for m in system_monitor.collect_metrics()]
        },
        'health': health_checker.run_all_checks(),
        'performance': {
            'stats': performance_monitor.get_performance_stats(),
            'endpoints': performance_monitor.get_endpoint_stats(),
            'slow_requests': performance_monitor.get_slow_requests()
        },
        'alerts': {
            'active': system_monitor.get_active_alerts(),
            'recent': system_monitor.get_alerts_history(limit=20)
        }
    }


def start_monitoring():
    """启动监控服务"""
    try:
        # 启动健康检查
        health_checker.start_periodic_checks()
        
        # 启动系统监控
        def monitor_loop():
            while True:
                try:
                    # 收集指标
                    system_monitor.collect_metrics()
                    
                    # 检查阈值
                    system_monitor.check_thresholds()
                    
                    # 等待下一次检查
                    time.sleep(60)
                    
                except Exception as e:
                    logger.error(f"监控循环异常: {str(e)}")
                    time.sleep(30)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        
        logger.info("监控服务已启动")
        
    except Exception as e:
        logger.error(f"启动监控服务失败: {str(e)}")


def stop_monitoring():
    """停止监控服务"""
    try:
        health_checker.stop_periodic_checks()
        logger.info("监控服务已停止")
    except Exception as e:
        logger.error(f"停止监控服务失败: {str(e)}")


# 自定义健康检查示例
@health_check(name="custom_service", description="自定义服务检查")
def check_custom_service() -> bool:
    """自定义服务健康检查示例"""
    try:
        # 这里可以添加自定义的检查逻辑
        # 例如：检查外部API、检查文件系统、检查缓存等
        return True
    except Exception:
        return False