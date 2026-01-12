"""
错误收集器

提供统一的错误收集、分类和报告功能
用于改进系统的错误处理和用户体验
"""

from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json

from loguru import logger


class ErrorType(Enum):
    """错误类型"""
    DATA_FETCH = "data_fetch"           # 数据获取错误
    DATA_PARSE = "data_parse"           # 数据解析错误
    CALCULATION = "calculation"         # 计算错误
    STRATEGY = "strategy"               # 策略执行错误
    EXPLANATION = "explanation"         # 解释生成错误
    NETWORK = "network"                 # 网络错误
    DATABASE = "database"               # 数据库错误
    CACHE = "cache"                     # 缓存错误
    SERVICE = "service"                 # 服务错误
    UNKNOWN = "unknown"                 # 未知错误


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"                         # 低严重度：可以忽略
    MEDIUM = "medium"                   # 中严重度：需要关注
    HIGH = "high"                       # 高严重度：需要处理
    CRITICAL = "critical"               # 严重：需要立即处理


@dataclass
class ErrorInfo:
    """错误信息"""
    error_id: str                       # 错误ID
    error_type: ErrorType                # 错误类型
    severity: ErrorSeverity             # 严重程度
    stock_code: Optional[str]           # 股票代码
    error_message: str                  # 错误消息
    error_detail: Optional[str]         # 错误详情
    timestamp: datetime                # 时间戳
    stack_trace: Optional[str]         # 堆栈跟踪
    context: Dict[str, Any]           # 上下文信息
    is_handled: bool = False          # 是否已处理
    retry_count: int = 0              # 重试次数


class ErrorCollector:
    """错误收集器
    
    收集、分类和报告错误信息
    """
    
    def __init__(self, max_errors: int = 1000):
        """初始化错误收集器
        
        Args:
            max_errors: 最大错误数量
        """
        self._errors: List[ErrorInfo] = []
        self._max_errors = max_errors
        self._error_stats = defaultdict(int)
        self._error_by_type = defaultdict(list)
        self._error_by_severity = defaultdict(list)
        self._affected_stocks: Set[str] = set()
        self._start_time = datetime.now()
        
    def add_error(
        self,
        error_type: ErrorType,
        error_message: str,
        stock_code: Optional[str] = None,
        error_detail: Optional[str] = None,
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ) -> str:
        """添加错误
        
        Args:
            error_type: 错误类型
            error_message: 错误消息
            stock_code: 股票代码
            error_detail: 错误详情
            stack_trace: 堆栈跟踪
            context: 上下文信息
            severity: 严重程度
            
        Returns:
            错误ID
        """
        import uuid
        
        error_id = str(uuid.uuid4())
        
        error_info = ErrorInfo(
            error_id=error_id,
            error_type=error_type,
            severity=severity,
            stock_code=stock_code,
            error_message=error_message,
            error_detail=error_detail,
            timestamp=datetime.now(),
            stack_trace=stack_trace,
            context=context or {}
        )
        
        # 添加到错误列表
        self._errors.append(error_info)
        
        # 更新统计信息
        self._error_stats[error_type.value] += 1
        self._error_by_type[error_type].append(error_info)
        self._error_by_severity[severity].append(error_info)
        
        if stock_code:
            self._affected_stocks.add(stock_code)
        
        # 限制错误数量
        if len(self._errors) > self._max_errors:
            removed = self._errors.pop(0)
            self._error_stats[removed.error_type.value] -= 1
        
        # 记录日志
        self._log_error(error_info)
        
        return error_id
    
    def _log_error(self, error_info: ErrorInfo):
        """记录错误日志"""
        log_message = f"[{error_info.error_id}] {error_info.error_type.value}: {error_info.error_message}"
        
        if error_info.stock_code:
            log_message += f" (股票: {error_info.stock_code})"
        
        if error_info.error_detail:
            log_message += f" - {error_info.error_detail}"
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif error_info.severity == ErrorSeverity.HIGH:
            logger.error(log_message)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        if error_info.stack_trace:
            logger.debug(f"堆栈跟踪:\n{error_info.stack_trace}")
    
    def get_errors(
        self,
        error_type: Optional[ErrorType] = None,
        severity: Optional[ErrorSeverity] = None,
        stock_code: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[ErrorInfo]:
        """获取错误列表
        
        Args:
            error_type: 错误类型过滤
            severity: 严重程度过滤
            stock_code: 股票代码过滤
            limit: 限制数量
            
        Returns:
            错误列表
        """
        errors = self._errors
        
        if error_type:
            errors = [e for e in errors if e.error_type == error_type]
        
        if severity:
            errors = [e for e in errors if e.severity == severity]
        
        if stock_code:
            errors = [e for e in errors if e.stock_code == stock_code]
        
        if limit:
            errors = errors[-limit:]
        
        return errors
    
    def get_summary(self) -> Dict[str, Any]:
        """获取错误摘要
        
        Returns:
            错误摘要字典
        """
        duration = (datetime.now() - self._start_time).total_seconds()
        
        return {
            'total_errors': len(self._errors),
            'duration_seconds': duration,
            'errors_per_second': len(self._errors) / duration if duration > 0 else 0,
            'errors_by_type': self._group_by_type(),
            'errors_by_severity': self._group_by_severity(),
            'affected_stocks_count': len(self._affected_stocks),
            'affected_stocks': list(self._affected_stocks),
            'latest_errors': [self._error_to_dict(e) for e in self._errors[-10:]],
            'critical_errors': [self._error_to_dict(e) for e in self._error_by_severity.get(ErrorSeverity.CRITICAL, [])],
            'high_errors': [self._error_to_dict(e) for e in self._error_by_severity.get(ErrorSeverity.HIGH, [])]
        }
    
    def _group_by_type(self) -> Dict[str, int]:
        """按类型分组"""
        return dict(self._error_stats)
    
    def _group_by_severity(self) -> Dict[str, int]:
        """按严重程度分组"""
        result = {}
        for severity, errors in self._error_by_severity.items():
            result[severity.value] = len(errors)
        return result
    
    def _error_to_dict(self, error_info: ErrorInfo) -> Dict[str, Any]:
        """转换错误信息为字典"""
        return {
            'error_id': error_info.error_id,
            'error_type': error_info.error_type.value,
            'severity': error_info.severity.value,
            'stock_code': error_info.stock_code,
            'error_message': error_info.error_message,
            'error_detail': error_info.error_detail,
            'timestamp': error_info.timestamp.isoformat(),
            'context': error_info.context,
            'is_handled': error_info.is_handled,
            'retry_count': error_info.retry_count
        }
    
    def clear(self):
        """清除所有错误"""
        self._errors.clear()
        self._error_stats.clear()
        self._error_by_type.clear()
        self._error_by_severity.clear()
        self._affected_stocks.clear()
        self._start_time = datetime.now()
        logger.info("错误收集器已清空")
    
    def get_error_count(self, error_type: Optional[ErrorType] = None) -> int:
        """获取错误数量
        
        Args:
            error_type: 错误类型
            
        Returns:
            错误数量
        """
        if error_type:
            return len(self._error_by_type.get(error_type, []))
        return len(self._errors)
    
    def has_critical_errors(self) -> bool:
        """是否有严重错误"""
        return len(self._error_by_severity.get(ErrorSeverity.CRITICAL, [])) > 0
    
    def has_high_errors(self) -> bool:
        """是否有高严重度错误"""
        return len(self._error_by_severity.get(ErrorSeverity.HIGH, [])) > 0
    
    def should_continue(self, max_errors: int = 10) -> bool:
        """判断是否应该继续
        
        Args:
            max_errors: 最大错误数
            
        Returns:
            是否继续
        """
        # 如果有严重错误，停止
        if self.has_critical_errors():
            return False
        
        # 如果错误数超过阈值，停止
        if len(self._errors) >= max_errors:
            return False
        
        return True
    
    def export_to_json(self) -> str:
        """导出为JSON
        
        Returns:
            JSON字符串
        """
        summary = self.get_summary()
        summary['errors'] = [self._error_to_dict(e) for e in self._errors]
        return json.dumps(summary, ensure_ascii=False, indent=2)
    
    def export_to_file(self, file_path: str):
        """导出到文件
        
        Args:
            file_path: 文件路径
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.export_to_json())
        logger.info(f"错误报告已导出到: {file_path}")
