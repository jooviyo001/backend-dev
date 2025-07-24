"""
雪花算法实现
用于生成分布式唯一ID

雪花算法ID结构（64位）：
- 1位符号位（固定为0）
- 41位时间戳（毫秒级，可使用69年）
- 10位机器ID（支持1024台机器）
- 12位序列号（每毫秒可生成4096个ID）
"""

import time
import threading
from typing import Optional


class SnowflakeGenerator:
    """雪花算法ID生成器"""
    
    # 时间戳起始点（2024-01-01 00:00:00 UTC）
    EPOCH = 1704067200000  # 毫秒时间戳
    
    # 各部分位数
    MACHINE_ID_BITS = 10
    SEQUENCE_BITS = 12
    
    # 最大值
    MAX_MACHINE_ID = (1 << MACHINE_ID_BITS) - 1  # 1023
    MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1      # 4095
    
    # 位移量
    MACHINE_ID_SHIFT = SEQUENCE_BITS
    TIMESTAMP_SHIFT = MACHINE_ID_BITS + SEQUENCE_BITS
    
    def __init__(self, machine_id: int = 1):
        """
        初始化雪花算法生成器
        
        Args:
            machine_id: 机器ID，范围0-1023
        """
        if machine_id < 0 or machine_id > self.MAX_MACHINE_ID:
            raise ValueError(f"机器ID必须在0-{self.MAX_MACHINE_ID}之间")
        
        self.machine_id = machine_id
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()
    
    def _current_timestamp(self) -> int:
        """获取当前毫秒时间戳"""
        return int(time.time() * 1000)
    
    def _wait_next_millis(self, last_timestamp: int) -> int:
        """等待下一毫秒"""
        timestamp = self._current_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self._current_timestamp()
        return timestamp
    
    def generate_id(self) -> int:
        """
        生成雪花算法ID
        
        Returns:
            int: 64位唯一ID
        """
        with self.lock:
            timestamp = self._current_timestamp()
            
            # 时钟回拨检查
            if timestamp < self.last_timestamp:
                raise RuntimeError(f"时钟回拨，拒绝生成ID。当前时间戳: {timestamp}, 上次时间戳: {self.last_timestamp}")
            
            # 同一毫秒内
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.MAX_SEQUENCE
                # 序列号溢出，等待下一毫秒
                if self.sequence == 0:
                    timestamp = self._wait_next_millis(self.last_timestamp)
            else:
                # 新的毫秒，序列号重置
                self.sequence = 0
            
            self.last_timestamp = timestamp
            
            # 组装ID
            snowflake_id = (
                ((timestamp - self.EPOCH) << self.TIMESTAMP_SHIFT) |
                (self.machine_id << self.MACHINE_ID_SHIFT) |
                self.sequence
            )
            
            return snowflake_id
    
    def parse_id(self, snowflake_id: int) -> dict:
        """
        解析雪花算法ID
        
        Args:
            snowflake_id: 雪花算法生成的ID
            
        Returns:
            dict: 包含时间戳、机器ID、序列号的字典
        """
        timestamp = ((snowflake_id >> self.TIMESTAMP_SHIFT) + self.EPOCH)
        machine_id = (snowflake_id >> self.MACHINE_ID_SHIFT) & self.MAX_MACHINE_ID
        sequence = snowflake_id & self.MAX_SEQUENCE
        
        return {
            'timestamp': timestamp,
            'machine_id': machine_id,
            'sequence': sequence,
            'datetime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp / 1000))
        }


# 全局雪花算法生成器实例
_snowflake_generator: Optional[SnowflakeGenerator] = None


def init_snowflake(machine_id: int = 1):
    """
    初始化全局雪花算法生成器
    
    Args:
        machine_id: 机器ID，范围0-1023
    """
    global _snowflake_generator
    _snowflake_generator = SnowflakeGenerator(machine_id)


from typing import Union

def generate_snowflake_id(prefix: Optional[str] = None) -> Union[int, str]:
    """
    生成雪花算法ID
    
    Returns:
        int: 64位唯一ID
    """
    global _snowflake_generator
    if _snowflake_generator is None:
        init_snowflake()
    generated_id = _snowflake_generator.generate_id()
    
    if prefix:
        return f"{prefix}_{generated_id}"
    else:
        return generated_id


def parse_snowflake_id(snowflake_id: int) -> dict:
    """
    解析雪花算法ID
    
    Args:
        snowflake_id: 雪花算法生成的ID
        
    Returns:
        dict: 包含时间戳、机器ID、序列号的字典
    """
    global _snowflake_generator
    if _snowflake_generator is None:
        init_snowflake()
    return _snowflake_generator.parse_id(snowflake_id)


# 便捷函数
def snowflake_id() -> int:
    """生成雪花算法ID的便捷函数"""
    return generate_snowflake_id()