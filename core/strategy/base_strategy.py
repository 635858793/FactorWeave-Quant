from loguru import logger
"""
策略基础框架 - 统一策略基类和接口规范

提供所有策略的基础接口和通用功能
"""

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import json
import hashlib
import uuid
from pathlib import Path

try:
    from core.events import EventBus, get_event_bus
    EVENT_BUS_AVAILABLE = True
except ImportError:
    EVENT_BUS_AVAILABLE = False


class StrategyType(Enum):
    """策略类型枚举"""
    TREND_FOLLOWING = "trend_following"      # 趋势跟踪
    MEAN_REVERSION = "mean_reversion"        # 均值回归
    MOMENTUM = "momentum"                    # 动量策略
    ARBITRAGE = "arbitrage"                  # 套利策略
    TECHNICAL = "technical"                  # 技术指标
    FUNDAMENTAL = "fundamental"              # 基本面
    QUANTITATIVE = "quantitative"            # 量化策略
    MACHINE_LEARNING = "machine_learning"    # 机器学习
    CUSTOM = "custom"                        # 自定义策略

class StrategyStatus(Enum):
    """策略状态枚举"""
    INACTIVE = "inactive"        # 未激活
    ACTIVE = "active"           # 激活中
    RUNNING = "running"         # 运行中
    PAUSED = "paused"          # 暂停
    STOPPED = "stopped"        # 已停止
    ERROR = "error"            # 错误状态
    COMPLETED = "completed"    # 已完成

class SignalType(Enum):
    """信号类型枚举"""
    BUY = "buy"                # 买入信号
    SELL = "sell"              # 卖出信号
    HOLD = "hold"              # 持有信号
    CLOSE_LONG = "close_long"  # 平多信号
    CLOSE_SHORT = "close_short"  # 平空信号

@dataclass
class StrategySignal:
    """策略信号数据类"""
    timestamp: datetime
    signal_type: SignalType
    price: float
    confidence: float
    strategy_name: str
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            'signal_type': self.signal_type.value if isinstance(self.signal_type, SignalType) else str(self.signal_type),
            'price': float(self.price),
            'confidence': float(self.confidence),
            'strategy_name': str(self.strategy_name),
            'reason': str(self.reason),
            'metadata': self.metadata,
            'stop_loss': float(self.stop_loss) if self.stop_loss is not None else None,
            'take_profit': float(self.take_profit) if self.take_profit is not None else None,
            'position_size': float(self.position_size) if self.position_size is not None else None
        }

@dataclass
class StrategyParameter:
    """策略参数定义"""
    name: str
    value: Any
    param_type: type
    description: str = ""
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    choices: Optional[List[Any]] = None
    required: bool = True

    def validate(self, value: Any) -> bool:
        """验证参数值"""
        try:
            # 类型检查
            if not isinstance(value, self.param_type):
                if self.param_type in (int, float) and isinstance(value, (int, float)):
                    value = self.param_type(value)
                else:
                    return False

            # 范围检查
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False

            # 选择检查
            if self.choices is not None and value not in self.choices:
                return False

            return True
        except:
            return False


class BaseStrategy(ABC):
    """策略基类 - 集成事件系统的统一策略接口"""

    def __init__(self, name: str, strategy_type: StrategyType = StrategyType.CUSTOM):
        """初始化策略

        Args:
            name: 策略名称
            strategy_type: 策略类型
        """
        self.name = name
        self.strategy_type = strategy_type
        self.status = StrategyStatus.INACTIVE
        self.parameters: Dict[str, StrategyParameter] = {}
        self.metadata: Dict[str, Any] = {}
        self.performance_metrics: Dict[str, Any] = {}
        self.created_at = datetime.now()
        self.last_updated = datetime.now()
        self._cache = {}

        # 事件系统相关
        self._event_bus: Optional[EventBus] = None
        self._event_handlers: Dict[str, List[Tuple[str, Callable]]] = {}

        # 初始化默认参数
        self._init_default_parameters()

    def _get_event_bus(self) -> Optional[EventBus]:
        """获取事件总线实例"""
        if self._event_bus is None and EVENT_BUS_AVAILABLE:
            try:
                self._event_bus = get_event_bus()
            except Exception:
                pass
        return self._event_bus

    def publish_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """发布事件

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if not EVENT_BUS_AVAILABLE:
            return

        bus = self._get_event_bus()
        if bus is None:
            return

        try:
            event = {
                'type': event_type,
                'timestamp': datetime.now().isoformat(),
                'strategy_name': self.name,
                'strategy_type': self.strategy_type.value,
                'data': data
            }
            bus.publish(f"strategy.{event_type}", event)
        except Exception:
            pass

    def subscribe_event(self, event_type: str, handler: Callable) -> str:
        """订阅事件

        Args:
            event_type: 事件类型
            handler: 事件处理函数

        Returns:
            订阅ID
        """
        subscription_id = str(uuid.uuid4())

        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append((subscription_id, handler))

        return subscription_id

    def unsubscribe_event(self, subscription_id: str) -> bool:
        """取消订阅事件

        Args:
            subscription_id: 订阅ID

        Returns:
            是否成功取消
        """
        for event_type, handlers in self._event_handlers.items():
            for i, (sub_id, _) in enumerate(handlers):
                if sub_id == subscription_id:
                    handlers.pop(i)
                    return True
        return False

    def _trigger_signal_generated_event(self, signals: List[StrategySignal]) -> None:
        """触发信号生成事件"""
        self.publish_event('signal_generated', {
            'signal_count': len(signals),
            'signals': [s.to_dict() for s in signals]
        })

    def _trigger_strategy_started_event(self) -> None:
        """触发策略启动事件"""
        self.publish_event('started', {
            'status': self.status.value,
            'parameters': self.get_parameters_dict()
        })

    def _trigger_strategy_stopped_event(self) -> None:
        """触发策略停止事件"""
        self.publish_event('stopped', {
            'status': self.status.value,
            'performance_metrics': self.performance_metrics
        })

    def _trigger_strategy_error_event(self, error: str) -> None:
        """触发策略错误事件"""
        self.publish_event('error', {
            'error': error,
            'status': self.status.value
        })

    @abstractmethod
    def _init_default_parameters(self):
        """初始化默认参数 - 子类必须实现"""
        pass

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """生成交易信号 - 子类必须实现

        Args:
            data: 市场数据DataFrame

        Returns:
            交易信号列表
        """
        pass

    def _generate_signals_with_event(self, data: pd.DataFrame) -> List[StrategySignal]:
        """生成交易信号（带事件触发）"""
        signals = self.generate_signals(data)
        self._trigger_signal_generated_event(signals)
        return signals

    def _start_with_event(self) -> bool:
        """启动策略（带事件触发）"""
        valid, errors = self.validate_parameters()
        if not valid:
            self._trigger_strategy_error_event(f"参数验证失败: {errors}")
            return False

        self.status = StrategyStatus.RUNNING
        self._trigger_strategy_started_event()
        return True

    def _stop_with_event(self) -> bool:
        """停止策略（带事件触发）"""
        self.status = StrategyStatus.STOPPED
        self._trigger_strategy_stopped_event()
        return True

    def add_parameter(self, name: str, value: Any, param_type: type,
                      description: str = "", min_value=None, max_value=None,
                      choices=None, required=True):
        """添加策略参数"""
        self.parameters[name] = StrategyParameter(
            name=name,
            value=value,
            param_type=param_type,
            description=description,
            min_value=min_value,
            max_value=max_value,
            choices=choices,
            required=required
        )

    def set_parameter(self, name: str, value: Any) -> bool:
        """设置参数值"""
        if name not in self.parameters:
            return False

        param = self.parameters[name]
        if param.validate(value):
            param.value = value
            self.last_updated = datetime.now()
            self._clear_cache()
            return True
        return False

    def get_parameter(self, name: str, default=None) -> Any:
        """获取参数值"""
        if name in self.parameters:
            return self.parameters[name].value
        return default

    def get_parameters_dict(self) -> Dict[str, Any]:
        """获取所有参数的字典"""
        return {name: param.value for name, param in self.parameters.items()}

    def validate_parameters(self) -> Tuple[bool, List[str]]:
        """验证所有参数"""
        errors = []
        for name, param in self.parameters.items():
            if param.required and param.value is None:
                errors.append(f"Required parameter '{name}' is missing")
            elif param.value is not None and not param.validate(param.value):
                errors.append(
                    f"Parameter '{name}' has invalid value: {param.value}")

        return len(errors) == 0, errors

    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算信号置信度 - 可被子类重写"""
        return 0.5  # 默认置信度

    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """数据预处理 - 可被子类重写"""
        return data.copy()

    def postprocess_signals(self, signals: List[StrategySignal]) -> List[StrategySignal]:
        """信号后处理 - 可被子类重写"""
        return signals

    def get_required_columns(self) -> List[str]:
        """获取策略所需的数据列 - 可被子类重写"""
        return ['open', 'high', 'low', 'close', 'volume']

    def validate_data(self, data: pd.DataFrame) -> Tuple[bool, List[str]]:
        """验证输入数据"""
        errors = []
        required_columns = self.get_required_columns()

        for col in required_columns:
            if col not in data.columns:
                errors.append(f"Required column '{col}' is missing")

        if len(data) == 0:
            errors.append("Data is empty")

        return len(errors) == 0, errors

    def get_strategy_info(self):
        """获取策略信息"""
        from core.strategy_extensions import StrategyInfo, ParameterDef, StrategyType as ExtStrategyType

        # 将 BaseStrategy 的参数转换为 ParameterDef 列表
        parameter_defs = []
        for name, param in self.parameters.items():
            parameter_defs.append(ParameterDef(
                name=name,
                type=param.param_type,
                default_value=param.value,
                description=param.description,
                min_value=param.min_value,
                max_value=param.max_value,
                choices=param.choices,
                required=param.required
            ))

        # 映射策略类型
        strategy_type_map = {
            StrategyType.TREND_FOLLOWING: ExtStrategyType.TREND_FOLLOWING,
            StrategyType.MEAN_REVERSION: ExtStrategyType.MEAN_REVERSION,
            StrategyType.MOMENTUM: ExtStrategyType.MOMENTUM,
            StrategyType.ARBITRAGE: ExtStrategyType.ARBITRAGE,
            StrategyType.TECHNICAL: ExtStrategyType.TECHNICAL,
            StrategyType.FUNDAMENTAL: ExtStrategyType.FUNDAMENTAL,
            StrategyType.QUANTITATIVE: ExtStrategyType.QUANTITATIVE,
            StrategyType.MACHINE_LEARNING: ExtStrategyType.MACHINE_LEARNING,
            StrategyType.CUSTOM: ExtStrategyType.CUSTOM,
        }

        ext_strategy_type = strategy_type_map.get(self.strategy_type, ExtStrategyType.CUSTOM)

        # 创建 StrategyInfo 对象
        strategy_info = StrategyInfo(
            name=self.name,
            display_name=self.name,
            description=self.metadata.get('description', ''),
            version=self.metadata.get('version', '1.0.0'),
            author=self.metadata.get('author', 'Unknown'),
            strategy_type=ext_strategy_type,
            parameters=parameter_defs,
            supported_assets=[],
            time_frames=[],
            tags=self.metadata.get('tags', []),
            created_at=self.created_at,
            updated_at=self.last_updated
        )

        return strategy_info

    def save_config(self, filepath: Union[str, Path]) -> bool:
        """保存策略配置"""
        try:
            config = {
                'name': self.name,
                'type': self.strategy_type.value,
                'parameters': {
                    name: {
                        'value': param.value,
                        'type': param.param_type.__name__,
                        'description': param.description,
                        'min_value': param.min_value,
                        'max_value': param.max_value,
                        'choices': param.choices,
                        'required': param.required
                    }
                    for name, param in self.parameters.items()
                },
                'metadata': self.metadata,
                'created_at': self.created_at.isoformat(),
                'last_updated': self.last_updated.isoformat()
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            logger.info(f"Failed to save strategy config: {e}")
            return False

    def load_config(self, filepath: Union[str, Path]) -> bool:
        """加载策略配置"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 加载参数
            for name, param_config in config.get('parameters', {}).items():
                if name in self.parameters:
                    self.parameters[name].value = param_config['value']

            # 加载元数据
            self.metadata.update(config.get('metadata', {}))

            self.last_updated = datetime.now()
            self._clear_cache()

            return True
        except Exception as e:
            logger.info(f"Failed to load strategy config: {e}")
            return False

    def get_cache_key(self, data: pd.DataFrame) -> str:
        """生成缓存键"""
        # 基于数据哈希和参数生成缓存键
        data_hash = hashlib.md5(
            str(data.values.tobytes()).encode()).hexdigest()[:8]
        params_hash = hashlib.md5(
            str(self.get_parameters_dict()).encode()).hexdigest()[:8]
        return f"{self.name}_{data_hash}_{params_hash}"

    def _clear_cache(self):
        """清空缓存"""
        self._cache.clear()

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', type='{self.strategy_type.value}', status='{self.status.value}')"

    def __repr__(self) -> str:
        return self.__str__()
