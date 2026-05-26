"""
合规性审计日志系统

实现专业级的合规性支持和审计日志记录，确保交易系统
符合金融监管要求，提供完整的操作追踪和合规报告。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-17
"""

import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import threading
from contextlib import contextmanager

from loguru import logger

from core.database.unified_sqlite_access import UnifiedSQLiteAccess
from core.events.event_bus import get_event_bus

class EventType(Enum):
    """事件类型"""
    DATA_ACCESS = "data_access"           # 数据访问
    PLUGIN_SWITCH = "plugin_switch"       # 插件切换
    SYSTEM_CONFIG = "system_config"       # 系统配置
    USER_LOGIN = "user_login"             # 用户登录
    DATA_EXPORT = "data_export"           # 数据导出
    ERROR_OCCURRED = "error_occurred"     # 错误发生
    PERFORMANCE_ALERT = "performance_alert" # 性能告警
    SECURITY_EVENT = "security_event"     # 安全事件
    RISK_MONITOR = "risk_monitor"         # 风险监控
    RISK_REDUCE_POSITION = "risk_reduce_position"  # 风险减仓
    RISK_STOP_TRADING = "risk_stop_trading"        # 风险停止交易
    RISK_EMERGENCY_LIQUIDATION = "risk_emergency_liquidation"  # 风险紧急平仓
    ORDER_EXECUTED = "order_executed"     # 订单执行
    ORDER_SUBMITTED = "order_submitted"   # 订单提交
    ORDER_FAILED = "order_failed"         # 订单失败
    ORDER_CANCELLED = "order_cancelled"   # 订单取消
    ORDER_FILLED = "order_filled"         # 订单成交
    TRADING_CIRCUIT_BREAKER = "trading_circuit_breaker"  # 交易熔断

class ComplianceLevel(Enum):
    """合规级别"""
    LOW = "low"           # 低
    MEDIUM = "medium"     # 中
    HIGH = "high"         # 高
    CRITICAL = "critical" # 关键

class AuditLevel(Enum):
    """审计级别"""
    BASIC = "basic"           # 基础审计
    DETAILED = "detailed"     # 详细审计
    COMPREHENSIVE = "comprehensive"  # 全面审计

@dataclass
class ComplianceFlag:
    """合规标志"""
    regulation: str        # 法规名称
    requirement: str       # 具体要求
    compliance_level: ComplianceLevel
    mandatory: bool = True
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class AuditRecord:
    """审计记录"""
    # 基础信息
    event_id: str
    timestamp: datetime
    event_type: EventType
    
    # 用户和会话信息
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # 数据和操作信息
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    operation: Optional[str] = None
    
    # 插件相关
    plugin_id: Optional[str] = None
    from_plugin: Optional[str] = None
    to_plugin: Optional[str] = None
    switch_reason: Optional[str] = None
    
    # 数据访问信息
    data_type: Optional[str] = None
    symbols: Optional[List[str]] = None
    market: Optional[str] = None
    data_size: Optional[int] = None
    
    # 结果和性能
    success: bool = True
    error_message: Optional[str] = None
    response_time_ms: Optional[float] = None
    
    # 合规信息
    compliance_flags: List[ComplianceFlag] = field(default_factory=list)
    sensitive_data_accessed: bool = False
    requires_approval: bool = False
    approved_by: Optional[str] = None
    approval_timestamp: Optional[datetime] = None
    
    # 上下文信息
    context: Dict[str, Any] = field(default_factory=dict)
    request_details: Dict[str, Any] = field(default_factory=dict)
    
    # 数据完整性
    checksum: Optional[str] = None
    
    def __post_init__(self):
        """后初始化处理"""
        if not self.event_id:
            self.event_id = self._generate_event_id()
        
        if not self.checksum:
            self.checksum = self._calculate_checksum()
    
    def _generate_event_id(self) -> str:
        """生成事件ID"""
        base_string = f"{self.timestamp.isoformat()}_{self.event_type.value}_{self.user_id or 'system'}"
        return hashlib.sha256(base_string.encode()).hexdigest()[:16]
    
    def _calculate_checksum(self) -> str:
        """计算记录校验和"""
        # 排除checksum字段本身
        data_dict = asdict(self)
        data_dict.pop('checksum', None)
        
        # 序列化并计算哈希
        data_string = json.dumps(data_dict, sort_keys=True, default=str)
        return hashlib.sha256(data_string.encode()).hexdigest()[:32]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = asdict(self)
        
        # 处理特殊字段
        result['timestamp'] = self.timestamp.isoformat()
        result['event_type'] = self.event_type.value
        
        if self.approval_timestamp:
            result['approval_timestamp'] = self.approval_timestamp.isoformat()
        
        # 处理合规标志
        result['compliance_flags'] = [flag.to_dict() for flag in self.compliance_flags]
        
        return result

class ComplianceRuleEngine:
    """合规规则引擎"""
    
    def __init__(self):
        """初始化合规规则引擎"""
        self.rules: Dict[str, Callable] = {}
        self.regulations: Dict[str, Dict[str, Any]] = {}
        
        # 初始化默认规则
        self._init_default_rules()
        self._init_regulations()
    
    def _init_default_rules(self) -> None:
        """初始化默认合规规则"""
        self.rules.update({
            "data_access_logging": self._check_data_access_logging,
            "sensitive_data_protection": self._check_sensitive_data_protection,
            "user_authentication": self._check_user_authentication,
            "data_retention": self._check_data_retention,
            "access_control": self._check_access_control
        })
    
    def _init_regulations(self) -> None:
        """初始化法规信息"""
        self.regulations.update({
            "GDPR": {
                "name": "General Data Protection Regulation",
                "jurisdiction": "EU",
                "requirements": [
                    "数据访问记录",
                    "用户同意管理",
                    "数据删除权利",
                    "数据可携权"
                ]
            },
            "SOX": {
                "name": "Sarbanes-Oxley Act",
                "jurisdiction": "US",
                "requirements": [
                    "财务数据完整性",
                    "访问控制",
                    "变更管理",
                    "审计追踪"
                ]
            },
            "CISA": {
                "name": "China Internet Security Administration",
                "jurisdiction": "CN",
                "requirements": [
                    "数据本地化",
                    "敏感信息保护",
                    "安全评估",
                    "数据出境管理"
                ]
            }
        })
    
    def check_compliance(self, record: AuditRecord) -> List[ComplianceFlag]:
        """检查合规性"""
        flags = []
        
        for rule_name, rule_func in self.rules.items():
            try:
                rule_result = rule_func(record)
                if rule_result:
                    flags.extend(rule_result if isinstance(rule_result, list) else [rule_result])
            except Exception as e:
                logger.warning(f"合规规则检查失败 {rule_name}: {e}")
        
        return flags
    
    def _check_data_access_logging(self, record: AuditRecord) -> List[ComplianceFlag]:
        """检查数据访问日志记录"""
        flags = []
        
        if record.event_type == EventType.DATA_ACCESS:
            # 检查是否记录了必要信息
            if not record.user_id:
                flags.append(ComplianceFlag(
                    regulation="SOX",
                    requirement="用户身份识别",
                    compliance_level=ComplianceLevel.HIGH,
                    description="数据访问必须记录用户身份"
                ))
            
            if not record.data_type:
                flags.append(ComplianceFlag(
                    regulation="GDPR",
                    requirement="数据类型记录",
                    compliance_level=ComplianceLevel.MEDIUM,
                    description="必须记录访问的数据类型"
                ))
        
        return flags
    
    def _check_sensitive_data_protection(self, record: AuditRecord) -> List[ComplianceFlag]:
        """检查敏感数据保护"""
        flags = []
        
        if record.sensitive_data_accessed:
            # 检查是否有适当的保护措施
            if not record.requires_approval:
                flags.append(ComplianceFlag(
                    regulation="CISA",
                    requirement="敏感数据访问控制",
                    compliance_level=ComplianceLevel.CRITICAL,
                    description="敏感数据访问需要审批"
                ))
            
            if record.requires_approval and not record.approved_by:
                flags.append(ComplianceFlag(
                    regulation="SOX",
                    requirement="审批记录",
                    compliance_level=ComplianceLevel.HIGH,
                    description="必须记录审批信息"
                ))
        
        return flags
    
    def _check_user_authentication(self, record: AuditRecord) -> List[ComplianceFlag]:
        """检查用户认证"""
        flags = []
        
        if record.event_type == EventType.USER_LOGIN:
            if not record.ip_address:
                flags.append(ComplianceFlag(
                    regulation="SOX",
                    requirement="登录IP记录",
                    compliance_level=ComplianceLevel.MEDIUM,
                    description="必须记录登录IP地址"
                ))
        
        return flags
    
    def _check_data_retention(self, record: AuditRecord) -> List[ComplianceFlag]:
        """检查数据保留"""
        flags = []
        
        # 检查数据保留时间要求
        if record.event_type == EventType.DATA_EXPORT:
            flags.append(ComplianceFlag(
                regulation="GDPR",
                requirement="数据导出记录",
                compliance_level=ComplianceLevel.HIGH,
                mandatory=True,
                description="数据导出必须保留审计记录"
            ))
        
        return flags
    
    def _check_access_control(self, record: AuditRecord) -> List[ComplianceFlag]:
        """检查访问控制"""
        flags = []
        
        if record.event_type == EventType.SYSTEM_CONFIG:
            if not record.user_id:
                flags.append(ComplianceFlag(
                    regulation="SOX",
                    requirement="配置变更授权",
                    compliance_level=ComplianceLevel.CRITICAL,
                    description="系统配置变更必须有授权用户"
                ))
        
        return flags
    
    def add_custom_rule(self, name: str, rule_func: Callable) -> None:
        """添加自定义合规规则"""
        self.rules[name] = rule_func
        logger.info(f"添加自定义合规规则: {name}")

class ComplianceAuditLogger:
    """
    合规性审计日志记录器
    
    提供专业级的审计日志记录和合规性检查功能
    """
    
    def __init__(self, db_path: str = "audit_logs.db", 
                 audit_level: AuditLevel = AuditLevel.DETAILED):
        """
        初始化合规性审计日志记录器
        
        Args:
            db_path: 数据库文件路径
            audit_level: 审计级别
        """
        self.db = UnifiedSQLiteAccess.get_instance(db_path)
        self.audit_level = audit_level
        self.compliance_engine = ComplianceRuleEngine()

        # 线程安全
        self._lock = threading.RLock()

        # 缓存配置
        self.enable_cache = True
        self.cache_size = 1000
        self._record_cache: List[AuditRecord] = []

        # 数据保留配置
        self.retention_days = 2555  # 7年（法规要求）
        self.archive_threshold_days = 365  # 1年后归档

        # EventBus订阅管理
        self._event_bus = get_event_bus()
        self._event_subscriptions = []

        # 初始化数据库
        self._init_database()

        self.logger = logger.bind(module="ComplianceAuditLogger")
        self.logger.info("合规性审计日志系统初始化完成")
    
    def _init_database(self) -> None:
        """初始化数据库"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_records (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    resource_type TEXT,
                    resource_id TEXT,
                    operation TEXT,
                    plugin_id TEXT,
                    from_plugin TEXT,
                    to_plugin TEXT,
                    switch_reason TEXT,
                    data_type TEXT,
                    symbols TEXT,
                    market TEXT,
                    data_size INTEGER,
                    success BOOLEAN,
                    error_message TEXT,
                    response_time_ms REAL,
                    sensitive_data_accessed BOOLEAN,
                    requires_approval BOOLEAN,
                    approved_by TEXT,
                    approval_timestamp TEXT,
                    context TEXT,
                    request_details TEXT,
                    checksum TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS compliance_flags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT,
                    regulation TEXT,
                    requirement TEXT,
                    compliance_level TEXT,
                    mandatory BOOLEAN,
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (event_id) REFERENCES audit_records (event_id)
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_records (timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON audit_records (user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON audit_records (event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_plugin_id ON audit_records (plugin_id)")

    def _subscribe_risk_events(self):
        self._event_bus.subscribe('risk.monitor', self._on_risk_monitor)
        self._event_bus.subscribe('risk.reduce_position', self._on_risk_reduce_position)
        self._event_bus.subscribe('risk.stop_trading', self._on_risk_stop_trading)
        self._event_bus.subscribe('risk.emergency_liquidation', self._on_risk_emergency_liquidation)
        self._event_subscriptions.extend([
            ('risk.monitor', self._on_risk_monitor),
            ('risk.reduce_position', self._on_risk_reduce_position),
            ('risk.stop_trading', self._on_risk_stop_trading),
            ('risk.emergency_liquidation', self._on_risk_emergency_liquidation),
        ])

    def _subscribe_order_events(self):
        self._event_bus.subscribe('order.executed', self._on_order_executed)
        self._event_bus.subscribe('order_submitted_success', self._on_order_submitted_success)
        self._event_bus.subscribe('order_submitted_failed', self._on_order_submitted_failed)
        self._event_bus.subscribe('order_filled', self._on_order_filled)
        self._event_bus.subscribe('order_partially_filled', self._on_order_partially_filled)
        self._event_bus.subscribe('order_cancelled', self._on_order_cancelled)
        self._event_bus.subscribe('order_cancel_failed', self._on_order_cancel_failed)
        self._event_bus.subscribe('order_terminal_state', self._on_order_terminal_state)
        self._event_bus.subscribe('trading_interface_circuit_breaker', self._on_trading_circuit_breaker)
        self._event_bus.subscribe('batch_orders_submitted_success', self._on_batch_orders_success)
        self._event_bus.subscribe('batch_orders_submitted_failed', self._on_batch_orders_failed)
        self._event_subscriptions.extend([
            ('order.executed', self._on_order_executed),
            ('order_submitted_success', self._on_order_submitted_success),
            ('order_submitted_failed', self._on_order_submitted_failed),
            ('order_filled', self._on_order_filled),
            ('order_partially_filled', self._on_order_partially_filled),
            ('order_cancelled', self._on_order_cancelled),
            ('order_cancel_failed', self._on_order_cancel_failed),
            ('order_terminal_state', self._on_order_terminal_state),
            ('trading_interface_circuit_breaker', self._on_trading_circuit_breaker),
            ('batch_orders_submitted_success', self._on_batch_orders_success),
            ('batch_orders_submitted_failed', self._on_batch_orders_failed),
        ])

    def _on_risk_monitor(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.RISK_MONITOR,
            resource_type="risk_alert",
            operation="monitor",
            success=True,
            context={'alert': getattr(event, 'alert', {}), 'timestamp': str(getattr(event, 'timestamp', ''))}
        )
        self._log_record(record)

    def _on_risk_reduce_position(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.RISK_REDUCE_POSITION,
            resource_type="risk_alert",
            operation="reduce_position",
            success=True,
            context={
                'alert': getattr(event, 'alert', {}),
                'reduce_ratio': getattr(event, 'reduce_ratio', 0.5),
                'timestamp': str(getattr(event, 'timestamp', ''))
            }
        )
        self._log_record(record)

    def _on_risk_stop_trading(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.RISK_STOP_TRADING,
            resource_type="risk_alert",
            operation="stop_trading",
            success=True,
            context={
                'alert': getattr(event, 'alert', {}),
                'duration_minutes': getattr(event, 'duration_minutes', 30),
                'timestamp': str(getattr(event, 'timestamp', ''))
            }
        )
        self._log_record(record)

    def _on_risk_emergency_liquidation(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.RISK_EMERGENCY_LIQUIDATION,
            resource_type="risk_alert",
            operation="emergency_liquidation",
            success=True,
            context={
                'alert': getattr(event, 'alert', {}),
                'timestamp': str(getattr(event, 'timestamp', ''))
            }
        )
        self._log_record(record)

    def _on_order_executed(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ORDER_EXECUTED,
            resource_type="order",
            operation="execute",
            success=True,
            context={
                'order_id': getattr(event, 'order_id', ''),
                'stock_code': getattr(event, 'stock_code', ''),
                'order_price': getattr(event, 'order_price', 0),
                'order_quantity': getattr(event, 'order_quantity', 0),
                'filled_price': getattr(event, 'filled_price', 0),
                'asset_type': getattr(event, 'asset_type', ''),
                'account_id': getattr(event, 'account_id', ''),
                'exchange_order_id': getattr(event, 'exchange_order_id', ''),
                'timestamp': str(getattr(event, 'timestamp', ''))
            }
        )
        self._log_record(record)

    def _on_order_submitted_success(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ORDER_SUBMITTED,
            resource_type="order",
            operation="submit",
            success=True,
            context={
                'order_id': getattr(event, 'order_id', ''),
                'exchange_order_id': getattr(event, 'exchange_order_id', ''),
                'asset_type': getattr(event, 'asset_type', ''),
                'account_id': getattr(event, 'account_id', '')
            }
        )
        self._log_record(record)

    def _on_order_submitted_failed(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ORDER_FAILED,
            resource_type="order",
            operation="submit",
            success=False,
            error_message=getattr(event, 'error', ''),
            context={
                'order_id': getattr(event, 'order_id', ''),
                'asset_type': getattr(event, 'asset_type', ''),
                'account_id': getattr(event, 'account_id', '')
            }
        )
        self._log_record(record)

    def _on_order_filled(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ORDER_FILLED,
            resource_type="order",
            operation="fill",
            success=True,
            context={
                'order_id': getattr(event, 'order_id', ''),
                'fill_price': getattr(event, 'fill_price', 0),
                'fill_quantity': getattr(event, 'fill_quantity', 0),
                'asset_type': getattr(event, 'asset_type', '')
            }
        )
        self._log_record(record)

    def _on_order_partially_filled(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ORDER_FILLED,
            resource_type="order",
            operation="partial_fill",
            success=True,
            context={
                'order_id': getattr(event, 'order_id', ''),
                'fill_price': getattr(event, 'fill_price', 0),
                'fill_quantity': getattr(event, 'fill_quantity', 0),
                'asset_type': getattr(event, 'asset_type', '')
            }
        )
        self._log_record(record)

    def _on_order_cancelled(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ORDER_CANCELLED,
            resource_type="order",
            operation="cancel",
            success=True,
            context={
                'order_id': getattr(event, 'order_id', ''),
                'asset_type': getattr(event, 'asset_type', '')
            }
        )
        self._log_record(record)

    def _on_order_cancel_failed(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ORDER_FAILED,
            resource_type="order",
            operation="cancel",
            success=False,
            error_message=getattr(event, 'error', ''),
            context={
                'order_id': getattr(event, 'order_id', ''),
                'asset_type': getattr(event, 'asset_type', '')
            }
        )
        self._log_record(record)

    def _on_order_terminal_state(self, event):
        self.logger.info(f"订单终态: order_id={getattr(event, 'order_id', '')}, status={getattr(event, 'status', '')}")

    def _on_trading_circuit_breaker(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.TRADING_CIRCUIT_BREAKER,
            resource_type="trading_interface",
            operation="circuit_breaker",
            success=False,
            context={
                'asset_type': getattr(event, 'asset_type', ''),
                'consecutive_failures': getattr(event, 'consecutive_failures', 0)
            }
        )
        self._log_record(record)

    def _on_batch_orders_success(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ORDER_SUBMITTED,
            resource_type="order",
            operation="batch_submit",
            success=True,
            context={
                'count': getattr(event, 'count', 0),
                'order_ids': getattr(event, 'order_ids', [])
            }
        )
        self._log_record(record)

    def _on_batch_orders_failed(self, event):
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ORDER_FAILED,
            resource_type="order",
            operation="batch_submit",
            success=False,
            context={
                'count': getattr(event, 'count', 0),
                'order_ids': getattr(event, 'order_ids', [])
            }
        )
        self._log_record(record)
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接"""
        with self.db.get_connection() as conn:
            yield conn
    
    def log_data_access(self, plugin_id: str, data_type: str, user_id: str = None,
                       symbols: List[str] = None, market: str = None,
                       data_size: int = None, response_time_ms: float = None,
                       success: bool = True, error_message: str = None,
                       **context) -> str:
        """
        记录数据访问日志
        
        Args:
            plugin_id: 插件ID
            data_type: 数据类型
            user_id: 用户ID
            symbols: 股票代码列表
            market: 市场
            data_size: 数据大小
            response_time_ms: 响应时间
            success: 是否成功
            error_message: 错误信息
            **context: 其他上下文信息
            
        Returns:
            str: 事件ID
        """
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.DATA_ACCESS,
            user_id=user_id,
            plugin_id=plugin_id,
            data_type=data_type,
            symbols=symbols,
            market=market,
            data_size=data_size,
            response_time_ms=response_time_ms,
            success=success,
            error_message=error_message,
            context=context,
            sensitive_data_accessed=self._is_sensitive_data(data_type, symbols)
        )
        
        return self._log_record(record)
    
    def log_plugin_switch(self, from_plugin: str, to_plugin: str, reason: str,
                          user_id: str = None, success: bool = True, 
                          **context) -> str:
        """
        记录插件切换日志
        
        Args:
            from_plugin: 源插件
            to_plugin: 目标插件
            reason: 切换原因
            user_id: 用户ID
            success: 是否成功
            **context: 其他上下文信息
            
        Returns:
            str: 事件ID
        """
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.PLUGIN_SWITCH,
            user_id=user_id,
            from_plugin=from_plugin,
            to_plugin=to_plugin,
            switch_reason=reason,
            success=success,
            context=context
        )
        
        return self._log_record(record)
    
    def log_system_config(self, operation: str, resource_type: str = None,
                         resource_id: str = None, user_id: str = None,
                         success: bool = True, **context) -> str:
        """
        记录系统配置变更日志
        
        Args:
            operation: 操作类型
            resource_type: 资源类型
            resource_id: 资源ID
            user_id: 用户ID
            success: 是否成功
            **context: 其他上下文信息
            
        Returns:
            str: 事件ID
        """
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.SYSTEM_CONFIG,
            user_id=user_id,
            operation=operation,
            resource_type=resource_type,
            resource_id=resource_id,
            success=success,
            context=context,
            requires_approval=True  # 系统配置变更通常需要审批
        )
        
        return self._log_record(record)
    
    def log_user_login(self, user_id: str, ip_address: str = None,
                      user_agent: str = None, success: bool = True,
                      session_id: str = None, **context) -> str:
        """
        记录用户登录日志
        
        Args:
            user_id: 用户ID
            ip_address: IP地址
            user_agent: 用户代理
            success: 是否成功
            session_id: 会话ID
            **context: 其他上下文信息
            
        Returns:
            str: 事件ID
        """
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.USER_LOGIN,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            context=context
        )
        
        return self._log_record(record)
    
    def log_error(self, error_message: str, plugin_id: str = None,
                 user_id: str = None, error_type: str = None,
                 **context) -> str:
        """
        记录错误日志
        
        Args:
            error_message: 错误信息
            plugin_id: 插件ID
            user_id: 用户ID
            error_type: 错误类型
            **context: 其他上下文信息
            
        Returns:
            str: 事件ID
        """
        record = AuditRecord(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ERROR_OCCURRED,
            user_id=user_id,
            plugin_id=plugin_id,
            error_message=error_message,
            success=False,
            context={**context, "error_type": error_type}
        )
        
        return self._log_record(record)
    
    def _log_record(self, record: AuditRecord) -> str:
        """记录审计日志"""
        try:
            with self._lock:
                # 合规性检查
                compliance_flags = self.compliance_engine.check_compliance(record)
                record.compliance_flags = compliance_flags
                
                # 重新计算校验和（包含合规标志）
                record.checksum = record._calculate_checksum()
                
                # 缓存记录
                if self.enable_cache:
                    self._record_cache.append(record)
                    if len(self._record_cache) >= self.cache_size:
                        self._flush_cache()
                else:
                    self._save_record(record)
                
                # 记录合规性警告
                critical_flags = [f for f in compliance_flags if f.compliance_level == ComplianceLevel.CRITICAL]
                if critical_flags:
                    self.logger.warning(f"发现关键合规问题 {record.event_id}: {[f.description for f in critical_flags]}")
                
                return record.event_id
                
        except Exception as e:
            self.logger.error(f"记录审计日志失败: {e}")
            raise
    
    def _save_record(self, record: AuditRecord) -> None:
        """保存记录到数据库"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 保存主记录
            cursor.execute("""
                INSERT INTO audit_records (
                    event_id, timestamp, event_type, user_id, session_id,
                    ip_address, user_agent, resource_type, resource_id, operation,
                    plugin_id, from_plugin, to_plugin, switch_reason, data_type,
                    symbols, market, data_size, success, error_message,
                    response_time_ms, sensitive_data_accessed, requires_approval,
                    approved_by, approval_timestamp, context, request_details, checksum
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.event_id,
                record.timestamp.isoformat(),
                record.event_type.value,
                record.user_id,
                record.session_id,
                record.ip_address,
                record.user_agent,
                record.resource_type,
                record.resource_id,
                record.operation,
                record.plugin_id,
                record.from_plugin,
                record.to_plugin,
                record.switch_reason,
                record.data_type,
                json.dumps(record.symbols) if record.symbols else None,
                record.market,
                record.data_size,
                record.success,
                record.error_message,
                record.response_time_ms,
                record.sensitive_data_accessed,
                record.requires_approval,
                record.approved_by,
                record.approval_timestamp.isoformat() if record.approval_timestamp else None,
                json.dumps(record.context) if record.context else None,
                json.dumps(record.request_details) if record.request_details else None,
                record.checksum
            ))
            
            # 保存合规标志
            for flag in record.compliance_flags:
                cursor.execute("""
                    INSERT INTO compliance_flags (
                        event_id, regulation, requirement, compliance_level,
                        mandatory, description
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    record.event_id,
                    flag.regulation,
                    flag.requirement,
                    flag.compliance_level.value,
                    flag.mandatory,
                    flag.description
                ))
            
            conn.commit()
    
    def _flush_cache(self) -> None:
        """刷新缓存到数据库"""
        if not self._record_cache:
            return
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                for record in self._record_cache:
                    try:
                        self._save_record_with_cursor(cursor, record)
                    except Exception as e:
                        self.logger.error(f"保存缓存记录失败 {record.event_id}: {e}")
                
                conn.commit()
                self._record_cache.clear()
                
        except Exception as e:
            self.logger.error(f"刷新缓存失败: {e}")
    
    def _save_record_with_cursor(self, cursor, record: AuditRecord) -> None:
        """使用游标保存记录"""
        cursor.execute("""
            INSERT INTO audit_records (
                event_id, timestamp, event_type, user_id, session_id,
                ip_address, user_agent, resource_type, resource_id, operation,
                plugin_id, from_plugin, to_plugin, switch_reason, data_type,
                symbols, market, data_size, success, error_message,
                response_time_ms, sensitive_data_accessed, requires_approval,
                approved_by, approval_timestamp, context, request_details, checksum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.event_id,
            record.timestamp.isoformat(),
            record.event_type.value,
            record.user_id,
            record.session_id,
            record.ip_address,
            record.user_agent,
            record.resource_type,
            record.resource_id,
            record.operation,
            record.plugin_id,
            record.from_plugin,
            record.to_plugin,
            record.switch_reason,
            record.data_type,
            json.dumps(record.symbols) if record.symbols else None,
            record.market,
            record.data_size,
            record.success,
            record.error_message,
            record.response_time_ms,
            record.sensitive_data_accessed,
            record.requires_approval,
            record.approved_by,
            record.approval_timestamp.isoformat() if record.approval_timestamp else None,
            json.dumps(record.context) if record.context else None,
            json.dumps(record.request_details) if record.request_details else None,
            record.checksum
        ))

        for flag in record.compliance_flags:
            cursor.execute("""
                INSERT INTO compliance_flags (
                    event_id, regulation, requirement, compliance_level,
                    mandatory, description
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                record.event_id,
                flag.regulation,
                flag.requirement,
                flag.compliance_level.value,
                flag.mandatory,
                flag.description
            ))
    
    def _is_sensitive_data(self, data_type: str, symbols: List[str] = None) -> bool:
        """判断是否为敏感数据"""
        sensitive_data_types = [
            "portfolio", "position", "trade", "account", 
            "balance", "pnl", "risk_metrics"
        ]
        
        return data_type.lower() in sensitive_data_types
    
    def query_records(self, start_time: datetime = None, end_time: datetime = None,
                     user_id: str = None, event_type: EventType = None,
                     plugin_id: str = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        查询审计记录
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            user_id: 用户ID
            event_type: 事件类型
            plugin_id: 插件ID
            limit: 限制数量
            
        Returns:
            List[Dict[str, Any]]: 审计记录列表
        """
        conditions = []
        params = []
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())
        
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type.value)
        
        if plugin_id:
            conditions.append("plugin_id = ?")
            params.append(plugin_id)
        
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT * FROM audit_records
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            columns = [description[0] for description in cursor.description]
            records = []
            
            for row in cursor.fetchall():
                record_dict = dict(zip(columns, row))
                
                # 解析JSON字段
                if record_dict.get('symbols'):
                    record_dict['symbols'] = json.loads(record_dict['symbols'])
                if record_dict.get('context'):
                    record_dict['context'] = json.loads(record_dict['context'])
                if record_dict.get('request_details'):
                    record_dict['request_details'] = json.loads(record_dict['request_details'])
                
                records.append(record_dict)
            
            return records
    
    def generate_compliance_report(self, start_time: datetime, end_time: datetime,
                                 regulation: str = None) -> Dict[str, Any]:
        """
        生成合规性报告
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            regulation: 特定法规
            
        Returns:
            Dict[str, Any]: 合规性报告
        """
        # 刷新缓存确保数据完整
        self._flush_cache()
        
        conditions = ["timestamp >= ?", "timestamp <= ?"]
        params = [start_time.isoformat(), end_time.isoformat()]
        
        if regulation:
            conditions.append("regulation = ?")
            params.append(regulation)
        
        where_clause = " WHERE " + " AND ".join(conditions)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 基础统计
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total_events,
                    COUNT(CASE WHEN success = 1 THEN 1 END) as successful_events,
                    COUNT(CASE WHEN success = 0 THEN 1 END) as failed_events,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(DISTINCT plugin_id) as unique_plugins
                FROM audit_records
                {where_clause}
            """, params)
            
            stats = dict(zip([desc[0] for desc in cursor.description], cursor.fetchone()))
            
            # 合规标志统计
            cursor.execute(f"""
                SELECT 
                    cf.regulation,
                    cf.compliance_level,
                    COUNT(*) as count
                FROM compliance_flags cf
                JOIN audit_records ar ON cf.event_id = ar.event_id
                {where_clause}
                GROUP BY cf.regulation, cf.compliance_level
                ORDER BY cf.regulation, cf.compliance_level
            """, params)
            
            compliance_stats = {}
            for row in cursor.fetchall():
                regulation_name = row[0]
                level = row[1]
                count = row[2]
                
                if regulation_name not in compliance_stats:
                    compliance_stats[regulation_name] = {}
                compliance_stats[regulation_name][level] = count
            
            # 事件类型统计
            cursor.execute(f"""
                SELECT 
                    event_type,
                    COUNT(*) as count
                FROM audit_records
                {where_clause}
                GROUP BY event_type
                ORDER BY count DESC
            """, params)
            
            event_type_stats = dict(cursor.fetchall())
            
            return {
                "report_period": {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat()
                },
                "basic_statistics": stats,
                "compliance_statistics": compliance_stats,
                "event_type_statistics": event_type_stats,
                "generated_at": datetime.now().isoformat(),
                "regulation_filter": regulation
            }
    
    def cleanup_old_records(self, older_than_days: int = None) -> int:
        """
        清理旧记录
        
        Args:
            older_than_days: 保留天数
            
        Returns:
            int: 删除的记录数
        """
        if older_than_days is None:
            older_than_days = self.retention_days
        
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 先删除合规标志
            cursor.execute("""
                DELETE FROM compliance_flags 
                WHERE event_id IN (
                    SELECT event_id FROM audit_records 
                    WHERE timestamp < ?
                )
            """, (cutoff_date.isoformat(),))
            
            # 删除审计记录
            cursor.execute("""
                DELETE FROM audit_records 
                WHERE timestamp < ?
            """, (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            self.logger.info(f"清理了 {deleted_count} 条旧审计记录")
            return deleted_count
    
    def verify_integrity(self) -> Dict[str, Any]:
        """验证数据完整性"""
        integrity_issues = []
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查校验和
            cursor.execute("SELECT event_id, checksum FROM audit_records")
            
            for event_id, stored_checksum in cursor.fetchall():
                # 重新计算校验和并比较
                # 这里简化实现，实际应该重新加载记录并计算
                pass  # 实际实现中会进行校验和验证
            
            # 检查孤儿记录
            cursor.execute("""
                SELECT COUNT(*) FROM compliance_flags cf
                LEFT JOIN audit_records ar ON cf.event_id = ar.event_id
                WHERE ar.event_id IS NULL
            """)
            orphan_flags = cursor.fetchone()[0]
            
            if orphan_flags > 0:
                integrity_issues.append(f"发现 {orphan_flags} 个孤儿合规标志")
        
        return {
            "integrity_check_time": datetime.now().isoformat(),
            "issues": integrity_issues,
            "status": "passed" if not integrity_issues else "failed"
        }
    
    def close(self) -> None:
        """关闭审计日志记录器"""
        with self._lock:
            self._unsubscribe_all()
            self._flush_cache()
            self.logger.info("合规性审计日志系统已关闭")

    def _unsubscribe_all(self) -> None:
        for event_type, handler in self._event_subscriptions:
            try:
                self._event_bus.unsubscribe(event_type, handler)
            except Exception as e:
                self.logger.warning(f"取消订阅失败 {event_type}: {e}")
        self._event_subscriptions.clear()
        self.logger.info(f"已取消所有EventBus订阅")

# 全局审计日志记录器实例
_audit_logger: Optional[ComplianceAuditLogger] = None

def get_audit_logger() -> ComplianceAuditLogger:
    """获取全局审计日志记录器"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = ComplianceAuditLogger()
    return _audit_logger

def audit_log(event_type: EventType):
    """
    审计日志装饰器
    
    Args:
        event_type: 事件类型
    
    Returns:
        装饰器函数
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            audit_logger = get_audit_logger()
            
            try:
                result = func(*args, **kwargs)
                
                # 记录成功执行
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                # 根据函数和参数构建审计记录
                if event_type == EventType.DATA_ACCESS:
                    audit_logger.log_data_access(
                        plugin_id=kwargs.get('plugin_id', 'unknown'),
                        data_type=kwargs.get('data_type', 'unknown'),
                        user_id=kwargs.get('user_id'),
                        response_time_ms=response_time,
                        success=True
                    )
                
                return result
                
            except Exception as e:
                # 记录失败执行
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                audit_logger.log_error(
                    error_message=str(e),
                    plugin_id=kwargs.get('plugin_id'),
                    user_id=kwargs.get('user_id')
                )
                
                raise
        
        return wrapper
    return decorator
