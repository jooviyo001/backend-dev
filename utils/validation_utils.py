"""数据验证工具模块

提供全面的数据验证功能，包括字段验证、业务规则验证、数据完整性检查等
"""
import re
import json
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session
from functools import wraps

from utils.exceptions import ValidationException
from utils.status_codes import VALIDATION_ERROR


class ValidationRule:
    """验证规则基类"""
    
    def __init__(self, field_name: str, message: str = None):
        self.field_name = field_name
        self.message = message or f"{field_name}验证失败"
    
    def validate(self, value: Any) -> bool:
        """验证方法，子类需要实现"""
        raise NotImplementedError
    
    def get_error_message(self, value: Any) -> str:
        """获取错误消息"""
        return self.message


class RequiredRule(ValidationRule):
    """必填验证规则"""
    
    def validate(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False
        return True
    
    def get_error_message(self, value: Any) -> str:
        return f"{self.field_name}不能为空"


class LengthRule(ValidationRule):
    """长度验证规则"""
    
    def __init__(self, field_name: str, min_length: int = None, max_length: int = None, message: str = None):
        super().__init__(field_name, message)
        self.min_length = min_length
        self.max_length = max_length
    
    def validate(self, value: Any) -> bool:
        if value is None:
            return True  # 长度验证不检查None值
        
        length = len(str(value))
        if self.min_length is not None and length < self.min_length:
            return False
        if self.max_length is not None and length > self.max_length:
            return False
        return True
    
    def get_error_message(self, value: Any) -> str:
        if self.min_length and self.max_length:
            return f"{self.field_name}长度必须在{self.min_length}-{self.max_length}之间"
        elif self.min_length:
            return f"{self.field_name}长度不能少于{self.min_length}个字符"
        elif self.max_length:
            return f"{self.field_name}长度不能超过{self.max_length}个字符"
        return super().get_error_message(value)


class RegexRule(ValidationRule):
    """正则表达式验证规则"""
    
    def __init__(self, field_name: str, pattern: str, message: str = None):
        super().__init__(field_name, message)
        self.pattern = re.compile(pattern)
    
    def validate(self, value: Any) -> bool:
        if value is None:
            return True
        return bool(self.pattern.match(str(value)))
    
    def get_error_message(self, value: Any) -> str:
        return f"{self.field_name}格式不正确"


class EmailRule(RegexRule):
    """邮箱验证规则"""
    
    def __init__(self, field_name: str, message: str = None):
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        super().__init__(field_name, email_pattern, message)
    
    def get_error_message(self, value: Any) -> str:
        return f"{self.field_name}邮箱格式不正确"


class PhoneRule(RegexRule):
    """手机号验证规则"""
    
    def __init__(self, field_name: str, message: str = None):
        phone_pattern = r'^1[3-9]\d{9}$'
        super().__init__(field_name, phone_pattern, message)
    
    def get_error_message(self, value: Any) -> str:
        return f"{self.field_name}手机号格式不正确"


class RangeRule(ValidationRule):
    """数值范围验证规则"""
    
    def __init__(self, field_name: str, min_value: Union[int, float] = None, 
                 max_value: Union[int, float] = None, message: str = None):
        super().__init__(field_name, message)
        self.min_value = min_value
        self.max_value = max_value
    
    def validate(self, value: Any) -> bool:
        if value is None:
            return True
        
        try:
            num_value = float(value)
            if self.min_value is not None and num_value < self.min_value:
                return False
            if self.max_value is not None and num_value > self.max_value:
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    def get_error_message(self, value: Any) -> str:
        if self.min_value is not None and self.max_value is not None:
            return f"{self.field_name}必须在{self.min_value}-{self.max_value}之间"
        elif self.min_value is not None:
            return f"{self.field_name}不能小于{self.min_value}"
        elif self.max_value is not None:
            return f"{self.field_name}不能大于{self.max_value}"
        return super().get_error_message(value)


class DateRule(ValidationRule):
    """日期验证规则"""
    
    def __init__(self, field_name: str, date_format: str = '%Y-%m-%d', message: str = None):
        super().__init__(field_name, message)
        self.date_format = date_format
    
    def validate(self, value: Any) -> bool:
        if value is None:
            return True
        
        if isinstance(value, (datetime, date)):
            return True
        
        if isinstance(value, str):
            try:
                datetime.strptime(value, self.date_format)
                return True
            except ValueError:
                return False
        
        return False
    
    def get_error_message(self, value: Any) -> str:
        return f"{self.field_name}日期格式不正确，应为{self.date_format}"


class ChoiceRule(ValidationRule):
    """选择项验证规则"""
    
    def __init__(self, field_name: str, choices: List[Any], message: str = None):
        super().__init__(field_name, message)
        self.choices = choices
    
    def validate(self, value: Any) -> bool:
        if value is None:
            return True
        return value in self.choices
    
    def get_error_message(self, value: Any) -> str:
        return f"{self.field_name}必须是以下选项之一：{', '.join(map(str, self.choices))}"


class CustomRule(ValidationRule):
    """自定义验证规则"""
    
    def __init__(self, field_name: str, validator_func: Callable[[Any], bool], message: str = None):
        super().__init__(field_name, message)
        self.validator_func = validator_func
    
    def validate(self, value: Any) -> bool:
        try:
            return self.validator_func(value)
        except Exception:
            return False


class DataValidator:
    """数据验证器"""
    
    def __init__(self):
        self.rules: Dict[str, List[ValidationRule]] = {}
        self.errors: List[str] = []
    
    def add_rule(self, field_name: str, rule: ValidationRule) -> 'DataValidator':
        """添加验证规则"""
        if field_name not in self.rules:
            self.rules[field_name] = []
        self.rules[field_name].append(rule)
        return self
    
    def add_required(self, field_name: str, message: str = None) -> 'DataValidator':
        """添加必填验证"""
        return self.add_rule(field_name, RequiredRule(field_name, message))
    
    def add_length(self, field_name: str, min_length: int = None, 
                   max_length: int = None, message: str = None) -> 'DataValidator':
        """添加长度验证"""
        return self.add_rule(field_name, LengthRule(field_name, min_length, max_length, message))
    
    def add_email(self, field_name: str, message: str = None) -> 'DataValidator':
        """添加邮箱验证"""
        return self.add_rule(field_name, EmailRule(field_name, message))
    
    def add_phone(self, field_name: str, message: str = None) -> 'DataValidator':
        """添加手机号验证"""
        return self.add_rule(field_name, PhoneRule(field_name, message))
    
    def add_range(self, field_name: str, min_value: Union[int, float] = None, 
                  max_value: Union[int, float] = None, message: str = None) -> 'DataValidator':
        """添加数值范围验证"""
        return self.add_rule(field_name, RangeRule(field_name, min_value, max_value, message))
    
    def add_date(self, field_name: str, date_format: str = '%Y-%m-%d', 
                 message: str = None) -> 'DataValidator':
        """添加日期验证"""
        return self.add_rule(field_name, DateRule(field_name, date_format, message))
    
    def add_choice(self, field_name: str, choices: List[Any], 
                   message: str = None) -> 'DataValidator':
        """添加选择项验证"""
        return self.add_rule(field_name, ChoiceRule(field_name, choices, message))
    
    def add_custom(self, field_name: str, validator_func: Callable[[Any], bool], 
                   message: str = None) -> 'DataValidator':
        """添加自定义验证"""
        return self.add_rule(field_name, CustomRule(field_name, validator_func, message))
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """执行验证"""
        self.errors.clear()
        
        for field_name, rules in self.rules.items():
            field_value = data.get(field_name)
            
            for rule in rules:
                if not rule.validate(field_value):
                    self.errors.append(rule.get_error_message(field_value))
        
        return len(self.errors) == 0
    
    def get_errors(self) -> List[str]:
        """获取验证错误"""
        return self.errors.copy()
    
    def get_first_error(self) -> Optional[str]:
        """获取第一个验证错误"""
        return self.errors[0] if self.errors else None


class BusinessValidator:
    """业务规则验证器"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_unique_field(self, model_class, field_name: str, value: Any, 
                             exclude_id: str = None) -> bool:
        """验证字段唯一性"""
        if value is None:
            return True
        
        query = self.db.query(model_class).filter(getattr(model_class, field_name) == value)
        if exclude_id:
            query = query.filter(model_class.id != exclude_id)
        
        return query.first() is None
    
    def validate_foreign_key_exists(self, model_class, foreign_key_value: str) -> bool:
        """验证外键是否存在"""
        if foreign_key_value is None:
            return True
        
        return self.db.query(model_class).filter(model_class.id == foreign_key_value).first() is not None
    
    def validate_enum_value(self, enum_class, value: Any) -> bool:
        """验证枚举值"""
        if value is None:
            return True
        
        try:
            enum_class(value)
            return True
        except ValueError:
            return False
    
    def validate_json_format(self, value: Any) -> bool:
        """验证JSON格式"""
        if value is None:
            return True
        
        if isinstance(value, str):
            try:
                json.loads(value)
                return True
            except (json.JSONDecodeError, TypeError):
                return False
        
        return isinstance(value, (dict, list))


def validate_data(validator: DataValidator):
    """数据验证装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 尝试从参数中提取数据
            data = None
            if args and isinstance(args[0], dict):
                data = args[0]
            elif 'data' in kwargs:
                data = kwargs['data']
            elif len(args) > 1 and isinstance(args[1], dict):
                data = args[1]
            
            if data and not validator.validate(data):
                raise ValidationException(
                    message=validator.get_first_error(),
                    data={'errors': validator.get_errors()}
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def validate_pydantic_model(model_class: BaseModel):
    """Pydantic模型验证装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 查找需要验证的参数
            for i, arg in enumerate(args):
                if hasattr(arg, '__dict__') and not isinstance(arg, model_class):
                    try:
                        # 尝试验证数据
                        if isinstance(arg, dict):
                            model_class(**arg)
                        else:
                            model_class.model_validate(arg)
                    except ValidationError as e:
                        errors = []
                        for error in e.errors():
                            field = '.'.join(str(loc) for loc in error['loc'])
                            message = error['msg']
                            errors.append(f"{field}: {message}")
                        
                        raise ValidationException(
                            message=f"数据验证失败: {errors[0]}",
                            data={'errors': errors}
                        )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


class ValidationHelper:
    """验证辅助工具类"""
    
    @staticmethod
    def is_valid_snowflake_id(value: str) -> bool:
        """验证雪花ID格式"""
        if not value or not isinstance(value, str):
            return False
        
        # 雪花ID应该是数字字符串，长度通常在15-20位
        if not value.isdigit() or len(value) < 15 or len(value) > 25:
            return False
        
        return True
    
    @staticmethod
    def is_valid_password(password: str, min_length: int = 8) -> tuple[bool, str]:
        """验证密码强度"""
        if not password:
            return False, "密码不能为空"
        
        if len(password) < min_length:
            return False, f"密码长度不能少于{min_length}位"
        
        # 检查是否包含数字
        if not re.search(r'\d', password):
            return False, "密码必须包含至少一个数字"
        
        # 检查是否包含字母
        if not re.search(r'[a-zA-Z]', password):
            return False, "密码必须包含至少一个字母"
        
        return True, "密码强度合格"
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """清理文件名，移除非法字符"""
        if not filename:
            return ""
        
        # 移除非法字符
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # 移除前后空格和点
        filename = filename.strip(' .')
        
        # 限制长度
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            max_name_length = 255 - len(ext) - 1 if ext else 255
            filename = name[:max_name_length] + ('.' + ext if ext else '')
        
        return filename
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
        """验证文件扩展名"""
        if not filename or not allowed_extensions:
            return False
        
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        return file_ext in [ext.lower().lstrip('.') for ext in allowed_extensions]
    
    @staticmethod
    def validate_file_size(file_size: int, max_size_mb: int) -> bool:
        """验证文件大小"""
        if file_size <= 0:
            return False
        
        max_size_bytes = max_size_mb * 1024 * 1024
        return file_size <= max_size_bytes


# 预定义的常用验证器
def create_user_validator() -> DataValidator:
    """创建用户数据验证器"""
    return (DataValidator()
            .add_required('username', '用户名不能为空')
            .add_length('username', 3, 50, '用户名长度必须在3-50个字符之间')
            .add_required('email', '邮箱不能为空')
            .add_email('email', '邮箱格式不正确')
            .add_length('name', 1, 100, '姓名长度不能超过100个字符')
            .add_phone('phone', '手机号格式不正确'))


def create_project_validator() -> DataValidator:
    """创建项目数据验证器"""
    return (DataValidator()
            .add_required('name', '项目名称不能为空')
            .add_length('name', 1, 200, '项目名称长度不能超过200个字符')
            .add_length('description', 0, 2000, '项目描述长度不能超过2000个字符')
            .add_required('organization_id', '所属组织不能为空'))


def create_defect_validator() -> DataValidator:
    """创建缺陷数据验证器"""
    from models.enums import DefectStatus, DefectPriority, DefectType, DefectSeverity
    
    return (DataValidator()
            .add_required('title', '缺陷标题不能为空')
            .add_length('title', 1, 500, '缺陷标题长度不能超过500个字符')
            .add_length('description', 0, 5000, '缺陷描述长度不能超过5000个字符')
            .add_required('project_id', '所属项目不能为空')
            .add_choice('status', [status.value for status in DefectStatus], '缺陷状态不正确')
            .add_choice('priority', [priority.value for priority in DefectPriority], '缺陷优先级不正确')
            .add_choice('type', [type_.value for type_ in DefectType], '缺陷类型不正确')
            .add_choice('severity', [severity.value for severity in DefectSeverity], '缺陷严重程度不正确'))


def create_task_validator() -> DataValidator:
    """创建任务数据验证器"""
    from models.enums import TaskStatus, TaskPriority, TaskType
    
    return (DataValidator()
            .add_required('title', '任务标题不能为空')
            .add_length('title', 1, 500, '任务标题长度不能超过500个字符')
            .add_length('description', 0, 5000, '任务描述长度不能超过5000个字符')
            .add_required('project_id', '所属项目不能为空')
            .add_choice('status', [status.value for status in TaskStatus], '任务状态不正确')
            .add_choice('priority', [priority.value for priority in TaskPriority], '任务优先级不正确')
            .add_choice('type', [type_.value for type_ in TaskType], '任务类型不正确')
            .add_range('estimated_hours', 0, 1000, '预估工时必须在0-1000小时之间'))