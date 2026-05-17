from ..strategy.events import (
    StrategyStartedEvent, StrategyStoppedEvent, StrategyErrorEvent,
    SignalGeneratedEvent, publish_strategy_event,
    EventType
)
from ..strategy_extensions import (
    IStrategyPlugin, StrategyInfo, StrategyContext, PerformanceMetrics,
    Signal, TradeResult, Position, StandardMarketData,
    StrategyType, AssetType, TimeFrame, RiskLevel
)
from ..containers import ServiceContainer
from ..events import EventBus
from ..enums import PluginStatus
from .base_service import BaseService
from ..trading.trading_mode import TradingMode, ModeContext
from loguru import logger
import traceback
import os
import psutil
import enum
import time
from datetime import datetime
"""
策略服务

提供策略插件管理、回测、优化等功能。
支持多种策略框架（FactorWeave-Quant、Backtrader、自定义等）。
"""

import json
import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
import numpy as np
import pandas as pd
import threading

# 修复：确保项目根目录在 Python 路径中，以便导入 strategies 模块
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


class BacktestStatus(Enum):
    """回测状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OptimizationStatus(Enum):
    """优化状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PluginInfo:
    """插件信息类，用于管理插件生命周期"""
    def __init__(self, plugin_id: str, plugin: IStrategyPlugin, plugin_type: str):
        self.plugin_id = plugin_id
        self.plugin = plugin
        self.plugin_type = plugin_type
        self.status = PluginStatus.CREATED
        self.created_at = datetime.now()
        self.initialized_at = None
        self.last_used_at = None
        self.usage_count = 0
        self.error_count = 0
        self.last_error = None


@dataclass
class StrategyConfig:
    """策略配置"""
    strategy_id: str
    plugin_type: str  # 'factorweave', 'backtrader', 'custom'
    parameters: Dict[str, Any]
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 分组和标签（从metadata中提取的便捷字段）
    @property
    def group(self) -> str:
        return self.metadata.get('group', 'default')
    
    @property
    def tags(self) -> List[str]:
        return self.metadata.get('tags', [])


@dataclass
class StrategyGroup:
    """策略分组"""
    group_id: str
    name: str
    description: str = ""
    color: str = "#3B82F6"  # 默认蓝色
    icon: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    is_builtin: bool = False


@dataclass
class StrategyTemplate:
    """策略模板"""
    template_id: str
    name: str
    description: str
    plugin_type: str
    default_parameters: Dict[str, Any]
    parameter_descriptions: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    category: str = "general"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_builtin: bool = False
    icon: Optional[str] = None


@dataclass
class BacktestTask:
    """回测任务"""
    task_id: str
    strategy_config: StrategyConfig
    market_data: StandardMarketData
    context: StrategyContext
    status: BacktestStatus = BacktestStatus.PENDING
    progress: float = 0.0
    result: Optional[PerformanceMetrics] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class OptimizationTask:
    """优化任务"""
    task_id: str
    strategy_config: StrategyConfig
    optimization_params: Dict[str, Any]
    market_data: StandardMarketData
    context: StrategyContext
    status: OptimizationStatus = OptimizationStatus.PENDING
    progress: float = 0.0
    best_parameters: Optional[Dict[str, Any]] = None
    best_performance: Optional[PerformanceMetrics] = None
    optimization_history: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class StrategyService(BaseService):
    """
    策略服务

    负责：
    1. 策略插件管理和注册
    2. 策略配置管理
    3. 策略回测服务
    4. 策略优化服务
    5. 策略评估和性能分析
    6. 策略模板管理
    """

    def __init__(self,
                 event_bus: Optional[EventBus] = None,
                 config: Optional[Dict[str, Any]] = None,
                 **kwargs):
        """初始化策略服务"""
        super().__init__(event_bus=event_bus, **kwargs)
        self._config = config or {}

        # 策略插件管理
        self._strategy_plugins: Dict[str, PluginInfo] = {}  # 使用PluginInfo管理插件生命周期
        self._plugin_factories: Dict[str, Callable[[], IStrategyPlugin]] = {}  # 插件工厂映射
        self._plugin_info_cache: Dict[str, Dict[str, Any]] = {}  # 插件信息缓存，避免重复创建实例
        
        # 插件实例池管理
        self._plugin_instance_pool: Dict[str, List[IStrategyPlugin]] = {}  # 插件实例池，按插件类型分组
        self._instance_pool_max_size: int = 5  # 每种插件类型的最大实例数
        self._instance_pool_timeout: int = 300  # 实例在池中的最大空闲时间（秒）
        self._instance_last_used: Dict[str, float] = {}  # 实例最后使用时间映射
        self._instance_mutex = threading.RLock()  # 实例池操作的线程锁

        # 策略配置管理
        self._strategy_configs: Dict[str, StrategyConfig] = {}

        # 回测管理
        self._backtest_tasks: Dict[str, BacktestTask] = {}
        self._running_backtests: Dict[str, asyncio.Task] = {}

        # 优化管理
        self._optimization_tasks: Dict[str, OptimizationTask] = {}
        self._running_optimizations: Dict[str, asyncio.Task] = {}

        # 性能缓存
        self._performance_cache: Dict[str, PerformanceMetrics] = {}
        
        # 策略模板管理
        self._strategy_templates: Dict[str, StrategyTemplate] = {}
        
        # 策略分组管理
        self._strategy_groups: Dict[str, StrategyGroup] = {}
        
        # 插件生命周期管理
        self._plugin_cleanup_interval = 300  # 插件清理间隔（秒）
        self._plugin_idle_timeout = 3600  # 插件空闲超时（秒）
        self._cleanup_timer = None  # 清理定时器

        # 服务状态 - 基于系统资源的动态并发控制
        self._max_concurrent_backtests = 3
        self._max_concurrent_optimizations = 1
        
        # 超时控制配置
        self._backtest_timeout_seconds = self._config.get('backtest_timeout_seconds', 300)
        self._optimization_timeout_seconds = self._config.get('optimization_timeout_seconds', 600)
        
        # 初始更新并发限制
        self._update_concurrent_limits()

        # 初始化
        self._load_strategy_plugins()
        self._load_strategy_configs()
        self._load_builtin_templates()
        self._load_builtin_groups()
        
    def _update_concurrent_limits(self):
        """根据系统资源动态调整并发限制"""
        try:
            # 获取CPU核心数
            cpu_count = os.cpu_count() or 4
            # 获取可用内存（GB）
            available_mem_gb = psutil.virtual_memory().available / (1024 ** 3)
            # 获取CPU使用率
            cpu_usage = psutil.cpu_percent(interval=0.1)
            # 获取内存使用率
            mem_usage = psutil.virtual_memory().percent
            
            # 基于资源使用情况动态调整并发数
            # CPU核心数是主要参考因素
            base_backtests = max(1, cpu_count // 2)
            base_optimizations = max(1, cpu_count // 4)
            
            # 根据系统负载调整
            load_factor = 1.0
            if cpu_usage > 70 or mem_usage > 80:
                # 高负载时降低并发
                load_factor = 0.5
            elif cpu_usage > 50 or mem_usage > 60:
                # 中等负载时保持默认
                load_factor = 0.8
            # 低负载时可以提高并发
            elif cpu_usage < 30 and mem_usage < 40:
                load_factor = 1.5
            
            # 计算最终并发限制
            self._max_concurrent_backtests = max(1, int(base_backtests * load_factor))
            self._max_concurrent_optimizations = max(1, int(base_optimizations * load_factor))
            
            logger.debug(f"动态调整并发限制: 回测={self._max_concurrent_backtests}, 优化={self._max_concurrent_optimizations}, CPU={cpu_usage:.1f}%, 内存={mem_usage:.1f}%, 可用内存={available_mem_gb:.1f}GB")
            
        except Exception as e:
            logger.error(f"更新并发限制失败: {e}")
            # 发生错误时使用保守的默认值
            self._max_concurrent_backtests = 3
            self._max_concurrent_optimizations = 1

    def _call_generate_signals(self, plugin, market_data_df, context) -> List:
        """
        智能调用策略插件的generate_signals方法，支持不同签名的插件

        Args:
            plugin: 策略插件实例
            market_data_df: 市场数据DataFrame
            context: 策略上下文

        Returns:
            List: 交易信号列表
        """
        import inspect

        try:
            sig = inspect.signature(plugin.generate_signals)
            params = list(sig.parameters.keys())
            logger.debug(f"策略插件 {plugin.__class__.__name__} 的 generate_signals 方法参数: {params}")

            if len(params) == 2:
                logger.debug(f"调用 2 参数版本: generate_signals(data, context)")
                return plugin.generate_signals(market_data_df, context)
            elif len(params) == 1:
                logger.debug(f"调用 1 参数版本: generate_signals(data)")
                return plugin.generate_signals(market_data_df)
            else:
                logger.warning(f"未知参数数量: {len(params)}，尝试 2 参数调用")
                return plugin.generate_signals(market_data_df, context)

        except (ValueError, TypeError) as e:
            logger.warning(f"签名检查失败，使用回退调用: {e}")
            try:
                return plugin.generate_signals(market_data_df, context)
            except TypeError as e2:
                logger.warning(f"2参数调用失败，尝试1参数: {e2}")
                return plugin.generate_signals(market_data_df)

    def _do_initialize(self) -> None:
        """初始化策略服务"""
        try:
            # 加载策略插件
            self._load_strategy_plugins()
            # 加载策略配置
            self._load_strategy_configs()
            
            # 启动插件清理定时器
            self._start_plugin_cleanup_timer()
            
            logger.info("Strategy service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize strategy service: {e}")
            raise

    def _load_strategy_plugins(self) -> None:
        """加载策略插件"""
        try:
            # 注册内置策略插件工厂
            self._register_builtin_plugin_factories()

            logger.info(f"已注册 {len(self._plugin_factories)} 个策略插件工厂")

        except Exception as e:
            logger.error(f"加载策略插件失败: {e}")

    def _register_builtin_plugin_factories(self) -> None:
        """注册内置策略插件工厂"""
        try:
            # FactorWeave策略插件（无hikyuu依赖）
            try:
                from plugins.strategies.adaptive_strategy import create_adaptive_pandas_strategy
                self._plugin_factories['factorweave'] = lambda: create_adaptive_pandas_strategy()
                # 移除'hikyuu'键，所有调用使用factorweave
            except ImportError:
                logger.warning("FactorWeave策略插件不可用")

            # Backtrader策略插件
            try:
                from plugins.strategies.backtrader_strategy_plugin import BacktraderStrategyPlugin
                self._plugin_factories['backtrader'] = lambda: BacktraderStrategyPlugin()
            except ImportError:
                logger.warning("Backtrader策略插件不可用")

            # 20字段标准策略插件 (New)
            # 20字段标准复权价格动量策略插件
            try:
                from plugins.strategies.adj_momentum_plugin import AdjMomentumPlugin
                self._plugin_factories['adj_momentum'] = lambda: AdjMomentumPlugin()
                logger.info("复权价格动量策略插件已注册")
            except ImportError:
                logger.warning("复权价格动量策略插件不可用")
            except Exception as e:
                logger.error(f"注册复权价格动量策略插件失败: {e}")
            
            # 20字段标准VWAP均值回归策略插件
            try:
                from plugins.strategies.vwap_reversion_plugin import VWAPReversionPlugin
                self._plugin_factories['vwap_reversion'] = lambda: VWAPReversionPlugin()
                logger.info("VWAP均值回归策略插件已注册")
            except ImportError:
                logger.warning("VWAP均值回归策略插件不可用")
            except Exception as e:
                logger.error(f"注册VWAP均值回归策略插件失败: {e}")

            # 自定义策略插件
            try:
                from plugins.strategies.custom_strategy_plugin import CustomStrategyPlugin
                self._plugin_factories['custom'] = lambda: CustomStrategyPlugin()
            except ImportError:
                logger.warning("自定义策略插件不可用")

            # 均值回归策略插件
            try:
                from plugins.strategies.mean_reversion_strategy import MeanReversionStrategyPlugin
                self._plugin_factories['mean_reversion'] = lambda: MeanReversionStrategyPlugin()
                logger.info("均值回归策略插件已注册")
            except ImportError:
                logger.warning("均值回归策略插件不可用")
            except Exception as e:
                logger.error(f"注册均值回归策略插件失败: {e}")

        except Exception as e:
            logger.error(f"注册内置策略插件工厂失败: {e}")

    def _load_strategy_configs(self) -> None:
        """从数据库加载策略配置，发布策略配置加载完成事件"""
        try:
            # 尝试从服务容器获取数据库服务
            from ..containers.service_container import get_service_container
            container = get_service_container()
            database_service = None
            
            try:
                from .database_service import DatabaseService
                database_service = container.resolve(DatabaseService)
                logger.info("成功获取数据库服务")
                
                # 从数据库加载策略配置
                logger.info("尝试从数据库加载策略配置")
                
                # 查询 strategy_configs 表
                sql = "SELECT * FROM strategy_configs"
                with database_service.get_connection("strategy_sqlite") as conn:
                    db_configs = conn.execute(sql)
                
                logger.info(f"从 strategy_configs 表查询到 {len(db_configs)} 个策略配置")
                
                if db_configs:
                    # 转换数据库配置为 StrategyConfig 对象
                    for config in db_configs:
                        # 将数据库记录转换为 StrategyConfig 对象
                        # SQLite 返回的是元组，需要按顺序解析
                        strategy_id = config[0]
                        plugin_type = config[1]
                        parameters = json.loads(config[2])
                        enabled = config[3]
                        created_at = datetime.fromisoformat(config[4])
                        updated_at = datetime.fromisoformat(config[5])
                        metadata = json.loads(config[6])
                        
                        # 创建 StrategyConfig 对象
                        strategy_config = StrategyConfig(
                            strategy_id=strategy_id,
                            plugin_type=plugin_type,
                            parameters=parameters,
                            enabled=enabled,
                            created_at=created_at,
                            updated_at=updated_at,
                            metadata=metadata
                        )
                        
                        self._strategy_configs[strategy_id] = strategy_config
                    
                    logger.info(f"从 strategy_configs 表加载到 {len(self._strategy_configs)} 个策略配置")
                
                # 额外步骤：从 strategies 表加载已注册策略并生成配置
                logger.info("尝试从 strategies 表加载已注册策略")
                sql = """SELECT id, name, strategy_type, version, author, description,
                              category, created_at, updated_at, is_active, metadata, class_path
                       FROM strategies WHERE is_active = 1"""
                with database_service.get_connection("strategy_sqlite") as conn:
                    registered_strategies = conn.execute(sql)
                
                logger.info(f"从 strategies 表查询到 {len(registered_strategies)} 个已注册策略")
                
                # 为每个已注册策略创建配置
                for strategy in registered_strategies:
                    strategy_dict = dict(strategy)
                    strategy_id = str(strategy_dict['id'])
                    strategy_name = strategy_dict['name']
                    strategy_type = strategy_dict['strategy_type']
                    author = strategy_dict.get('author', '')
                    description = strategy_dict.get('description', '')
                    
                    try:
                        metadata = strategy_dict.get('metadata', {})
                        if isinstance(metadata, str):
                            metadata = json.loads(metadata) if metadata else {}
                    except json.JSONDecodeError:
                        logger.warning(f"解析策略 {strategy_name} 的元数据失败，使用空字典")
                        metadata = {}
                    
                    parameters = metadata.get('parameters', {})
                    
                    # 跳过已存在的策略
                    if strategy_id in self._strategy_configs:
                        logger.info(f"策略 {strategy_name} (ID: {strategy_id}) 已存在配置，跳过")
                        continue
                    
                    # 根据策略类型确定plugin_type
                    plugin_type = "custom"
                    if strategy_type.lower() in ["momentum", "trend"]:
                        plugin_type = "factorweave"
                    elif strategy_type.lower() in ["reversion", "volatility"]:
                        plugin_type = "vwap_reversion"
                    
                    # 创建策略配置
                    strategy_config = StrategyConfig(
                        strategy_id=strategy_id,
                        plugin_type=plugin_type,
                        parameters=parameters,
                        enabled=True,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        metadata={
                            "description": description,
                            "author": author,
                            "name": strategy_name,
                            "plugin_type": plugin_type,
                            "strategy_type": strategy_type
                        }
                    )
                    
                    self._strategy_configs[strategy_id] = strategy_config
                    logger.info(f"为已注册策略 {strategy_name} (ID: {strategy_id}) 创建配置")
                
                # 如果仍然没有策略配置，生成默认策略
                if not self._strategy_configs:
                    logger.info("没有找到任何策略配置，生成默认策略")
                    self._generate_default_strategies()
                    
            except Exception as e_db:
                logger.warning(f"从数据库加载策略配置失败，生成默认策略: {e_db}")
                self._generate_default_strategies()
        except Exception as e_container:
            logger.warning(f"获取服务容器失败，生成默认策略: {e_container}")
            self._generate_default_strategies()
            
        logger.info(f"已加载 {len(self._strategy_configs)} 个策略配置")
        
        # 发布策略配置加载完成事件
        from ..events import StrategyConfigsLoadedEvent
        from ..events.event_bus import get_event_bus
        event_bus = get_event_bus()
        event_bus.publish(StrategyConfigsLoadedEvent(
            config_count=len(self._strategy_configs)
        ))

    def _generate_default_strategies(self) -> None:
        """从注册的插件自动生成默认策略，完善插件集成"""
        logger.info("开始自动生成默认策略")
        
        # 获取所有已注册的插件类型
        plugin_types = self.get_available_plugin_types()
        logger.info(f"已注册的插件类型: {plugin_types}")
        
        # 为每个插件类型生成一个默认策略
        generated_count = 0
        for plugin_type in plugin_types:
            strategy_id = f"default_{plugin_type}"
            
            # 如果策略已存在，跳过
            if strategy_id in self._strategy_configs:
                logger.info(f"策略 {strategy_id} 已存在，跳过")
                continue
            
            # 基于插件类型生成默认参数，不依赖插件信息
            default_params = {}
            
            # 为不同插件类型设置特定的默认参数
            if plugin_type == 'adj_momentum':
                default_params = {
                    'lookback_period': 20,
                    'top_n': 10,
                    'signal_strength_threshold': 0.01
                }
            elif plugin_type == 'vwap_reversion':
                default_params = {
                    'deviation_threshold': 0.02,
                    'hold_period': 3,
                    'min_turnover_rate': 0.5
                }
            elif plugin_type == 'factorweave':
                default_params = {
                    'strategy_type': 'momentum',
                    'lookback_period': 20
                }
            elif plugin_type == 'backtrader':
                default_params = {
                    'strategy_class': 'SimpleMovingAverageStrategy',
                    'fast_period': 5,
                    'slow_period': 20
                }
            elif plugin_type == 'custom':
                default_params = {
                    'custom_params': {}
                }
            
            logger.info(f"为插件 {plugin_type} 设置默认参数: {default_params}")
            
            # 创建默认策略配置
            metadata = {
                'name': f"默认 {plugin_type} 策略",
                'description': f"默认 {plugin_type} 策略",
                'author': 'system',
                'created_at': datetime.now().isoformat(),
                'generated_from_plugin': plugin_type
            }
            
            # 直接创建策略配置
            default_config = self.create_strategy_config(
                strategy_id=strategy_id,
                plugin_type=plugin_type,
                parameters=default_params,
                metadata=metadata
            )
            
            if default_config:
                logger.info(f"生成默认策略: {strategy_id}")
                generated_count += 1
            else:
                logger.warning(f"生成默认策略 {strategy_id} 失败")

        logger.info(f"自动生成了 {generated_count} 个默认策略，当前共有 {len(self._strategy_configs)} 个策略配置")

    # 策略插件管理
    def register_strategy_plugin(self, plugin_type: str, plugin_factory: Callable[[], IStrategyPlugin]) -> bool:
        """注册策略插件工厂"""
        try:
            self._plugin_factories[plugin_type] = plugin_factory
            logger.info(f"策略插件工厂已注册: {plugin_type}")
            return True

        except Exception as e:
            logger.error(f"注册策略插件工厂失败: {e}")
            return False

    def unregister_strategy_plugin(self, plugin_type: str) -> bool:
        """注销策略插件工厂"""
        try:
            if plugin_type in self._plugin_factories:
                del self._plugin_factories[plugin_type]

                # 清理相关的插件实例
                plugins_to_remove = [pid for pid, plugin in self._strategy_plugins.items()
                                     if pid.startswith(f"{plugin_type}_")]
                for plugin_id in plugins_to_remove:
                    del self._strategy_plugins[plugin_id]

                logger.info(f"策略插件工厂已注销: {plugin_type}")
                return True
            else:
                logger.warning(f"策略插件工厂不存在: {plugin_type}")
                return False

        except Exception as e:
            logger.error(f"注销策略插件工厂失败: {e}")
            return False

    def get_available_plugin_types(self) -> List[str]:
        """获取可用的策略插件类型"""
        return list(self._plugin_factories.keys())

    def create_strategy_plugin(self, plugin_type: str) -> Optional[IStrategyPlugin]:
        """创建策略插件实例"""
        try:
            if plugin_type not in self._plugin_factories:
                logger.error(f"策略插件类型不存在: {plugin_type}")
                return None

            # 生成插件ID
            plugin_id = f"{plugin_type}_{uuid.uuid4().hex[:8]}"
            
            # 从实例池获取插件实例
            plugin = self._get_from_instance_pool(plugin_type)
            
            # 如果实例池没有可用实例，则创建新实例
            if not plugin:
                plugin = self._plugin_factories[plugin_type]()
                logger.debug(f"创建新策略插件实例: {plugin_id}")
            else:
                logger.debug(f"使用实例池中的策略插件实例: {plugin_id}")
            
            # 创建PluginInfo对象管理插件生命周期
            plugin_info = PluginInfo(plugin_id, plugin, plugin_type)
            plugin_info.status = PluginStatus.INITIALIZED
            plugin_info.initialized_at = datetime.now()
            plugin_info.last_used_at = datetime.now()
            
            self._strategy_plugins[plugin_id] = plugin_info

            logger.info(f"策略插件实例已创建: {plugin_id}")
            return plugin

        except Exception as e:
            logger.error(f"创建策略插件实例失败: {e}")
            return None

    def get_strategy_plugin_info(self, plugin_type: str) -> Optional[Dict[str, Any]]:
        """获取策略插件信息"""
        try:
            # 先从缓存获取，避免重复创建实例
            if plugin_type in self._plugin_info_cache:
                return self._plugin_info_cache[plugin_type]

            if plugin_type not in self._plugin_factories:
                logger.error(f"策略插件类型不存在: {plugin_type}")
                return None

            # 创建临时插件实例获取信息
            plugin = None
            try:
                plugin = self._plugin_factories[plugin_type]()
                plugin_info = plugin.plugin_info
                # 缓存插件信息
                self._plugin_info_cache[plugin_type] = plugin_info
                return plugin_info
            finally:
                # 释放临时插件资源
                if plugin and hasattr(plugin, 'destroy'):
                    plugin.destroy()

        except Exception as e:
            logger.error(f"获取策略插件信息失败: {e}")
            return None
    
    def _get_from_instance_pool(self, plugin_type: str) -> Optional[IStrategyPlugin]:
        """从实例池获取插件实例"""
        with self._instance_mutex:
            # 检查插件类型是否在实例池中
            if plugin_type not in self._plugin_instance_pool or not self._plugin_instance_pool[plugin_type]:
                return None
            
            # 获取最近使用的实例
            instance = self._plugin_instance_pool[plugin_type].pop()
            instance_id = id(instance)
            
            # 更新最后使用时间
            self._instance_last_used[instance_id] = time.time()
            
            logger.debug(f"从实例池获取插件实例: {plugin_type}_{instance_id}")
            return instance
    
    def _return_to_instance_pool(self, plugin_type: str, instance: IStrategyPlugin) -> None:
        """将插件实例归还到实例池"""
        with self._instance_mutex:
            # 检查实例是否有效
            if instance is None:
                return
            
            instance_id = id(instance)
            current_time = time.time()
            
            # 检查实例是否超过最大空闲时间
            if instance_id in self._instance_last_used:
                idle_time = current_time - self._instance_last_used[instance_id]
                if idle_time > self._instance_pool_timeout:
                    # 实例已过期，销毁
                    if hasattr(instance, 'destroy'):
                        instance.destroy()
                    if instance_id in self._instance_last_used:
                        del self._instance_last_used[instance_id]
                    logger.debug(f"插件实例已过期，销毁: {plugin_type}_{instance_id}")
                    return
            
            # 初始化实例池列表
            if plugin_type not in self._plugin_instance_pool:
                self._plugin_instance_pool[plugin_type] = []
            
            # 检查实例池是否已满
            if len(self._plugin_instance_pool[plugin_type]) >= self._instance_pool_max_size:
                # 实例池已满，销毁实例
                if hasattr(instance, 'destroy'):
                    instance.destroy()
                if instance_id in self._instance_last_used:
                    del self._instance_last_used[instance_id]
                logger.debug(f"实例池已满，销毁插件实例: {plugin_type}_{instance_id}")
                return
            
            # 将实例添加到实例池
            self._plugin_instance_pool[plugin_type].append(instance)
            # 更新最后使用时间
            self._instance_last_used[instance_id] = current_time
            
            logger.debug(f"插件实例已归还到实例池: {plugin_type}_{instance_id}")
    
    def _cleanup_instance_pool(self) -> None:
        """清理实例池中的过期实例"""
        with self._instance_mutex:
            current_time = time.time()
            for plugin_type, instances in list(self._plugin_instance_pool.items()):
                # 检查每个实例
                for instance in list(instances):
                    instance_id = id(instance)
                    if instance_id in self._instance_last_used:
                        idle_time = current_time - self._instance_last_used[instance_id]
                        if idle_time > self._instance_pool_timeout:
                            # 实例已过期，销毁
                            instances.remove(instance)
                            if hasattr(instance, 'destroy'):
                                instance.destroy()
                            del self._instance_last_used[instance_id]
                            logger.debug(f"清理实例池中的过期实例: {plugin_type}_{instance_id}")
            
            # 清理空的实例池
            for plugin_type in list(self._plugin_instance_pool.keys()):
                if not self._plugin_instance_pool[plugin_type]:
                    del self._plugin_instance_pool[plugin_type]
    
    def get_strategy_info(self, plugin_type: str) -> Optional[Any]:
        """获取策略信息，内部创建临时插件实例，使用后自动释放资源"""
        try:
            if plugin_type not in self._plugin_factories:
                logger.error(f"策略插件类型不存在: {plugin_type}")
                return None

            # 从实例池获取或创建临时插件实例
            plugin = self._get_from_instance_pool(plugin_type)
            if not plugin:
                plugin = self._plugin_factories[plugin_type]()
            
            try:
                return plugin.get_strategy_info()
            finally:
                # 将实例归还到实例池
                self._return_to_instance_pool(plugin_type, plugin)

        except Exception as e:
            logger.error(f"获取策略信息失败: {e}")
            return None

    # 策略配置管理
    def create_strategy_config(self,
                               strategy_id: str,
                               plugin_type: str,
                               parameters: Dict[str, Any],
                               metadata: Optional[Dict[str, Any]] = None) -> bool:
        """创建策略配置并保存到数据库，发布策略配置创建事件"""
        try:
            if strategy_id in self._strategy_configs:
                logger.error(f"策略配置已存在: {strategy_id}")
                return False

            if plugin_type not in self._plugin_factories:
                logger.error(f"策略插件类型不存在: {plugin_type}")
                return False

            config = StrategyConfig(
                strategy_id=strategy_id,
                plugin_type=plugin_type,
                parameters=parameters,
                metadata=metadata or {}
            )

            # 添加到内存中的策略配置
            self._strategy_configs[strategy_id] = config
            logger.info(f"策略配置已添加到内存: {strategy_id}")
            
            # 保存到数据库（可选，失败不影响内存配置）
            try:
                from ..containers.service_container import get_service_container
                from .database_service import DatabaseService
                container = get_service_container()
                database_service = container.resolve(DatabaseService)
                
                sql = """
                INSERT INTO strategy_configs (
                    strategy_id, plugin_type, parameters, enabled, created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                
                with database_service.get_connection("strategy_sqlite") as conn:
                    conn.execute(sql, (
                        strategy_id,
                        plugin_type,
                        json.dumps(parameters),
                        config.enabled,
                        config.created_at.isoformat(),
                        config.updated_at.isoformat(),
                        json.dumps(config.metadata)
                    ))
                    conn.commit()
                
                logger.info(f"策略配置已保存到数据库: {strategy_id}")
            except Exception as e:
                logger.warning(f"保存策略配置到数据库失败，但策略已添加到内存: {e}")
                # 数据库保存失败不影响内存配置的创建
                pass
            except Exception as e_db:
                logger.error(f"保存策略配置到数据库失败: {e_db}")
                return False

            # 添加到内存中
            self._strategy_configs[strategy_id] = config
            
            # 发布策略配置创建事件
            from ..events import StrategyConfigCreatedEvent
            from ..events.event_bus import get_event_bus
            event_bus = get_event_bus()
            event_bus.publish(StrategyConfigCreatedEvent(
                strategy_id=strategy_id,
                plugin_type=plugin_type,
                parameters=parameters
            ))
            
            logger.info(f"策略配置已创建: {strategy_id}")
            return True

        except Exception as e:
            logger.error(f"创建策略配置失败: {e}")
            return False

    def update_strategy_config(self,
                               strategy_id: str,
                               parameters: Optional[Dict[str, Any]] = None,
                               enabled: Optional[bool] = None,
                               metadata: Optional[Dict[str, Any]] = None) -> bool:
        """更新策略配置并保存到数据库，发布策略配置更新事件"""
        try:
            if strategy_id not in self._strategy_configs:
                logger.error(f"策略配置不存在: {strategy_id}")
                return False

            config = self._strategy_configs[strategy_id]

            updated_at = datetime.now()

            # 先更新内存中的配置
            if parameters is not None:
                config.parameters.update(parameters)
            if enabled is not None:
                config.enabled = enabled
            if metadata is not None:
                config.metadata.update(metadata)
            config.updated_at = updated_at

            # 更新到数据库（可选，失败不影响内存配置）
            try:
                from ..containers.service_container import get_service_container
                from .database_service import DatabaseService
                container = get_service_container()
                database_service = container.resolve(DatabaseService)
                
                sql = """
                UPDATE strategy_configs 
                SET parameters = ?, enabled = ?, updated_at = ?, metadata = ?
                WHERE strategy_id = ?
                """
                
                with database_service.get_connection("strategy_sqlite") as conn:
                    conn.execute(sql, (
                        json.dumps(config.parameters),
                        config.enabled,
                        config.updated_at.isoformat(),
                        json.dumps(config.metadata),
                        strategy_id
                    ))
                    conn.commit()
                
                logger.info(f"策略配置已更新到数据库: {strategy_id}")
            except Exception as e_db:
                logger.warning(f"更新策略配置到数据库失败，但内存配置已更新: {e_db}")
            
            # 发布策略配置更新事件
            from ..events import StrategyConfigUpdatedEvent
            from ..events.event_bus import get_event_bus
            event_bus = get_event_bus()
            event_bus.publish(StrategyConfigUpdatedEvent(
                strategy_id=strategy_id,
                parameters=config.parameters,
                enabled=config.enabled,
                metadata=config.metadata
            ))

            logger.info(f"策略配置已更新: {strategy_id}")
            return True

        except Exception as e:
            logger.error(f"更新策略配置失败: {e}")
            return False

    def delete_strategy_config(self, strategy_id: str) -> bool:
        """删除策略配置并从数据库中删除，发布策略配置删除事件"""
        try:
            if strategy_id not in self._strategy_configs:
                logger.error(f"策略配置不存在: {strategy_id}")
                return False

            # 从数据库中删除
            try:
                from ..containers.service_container import get_service_container
                from .database_service import DatabaseService
                container = get_service_container()
                database_service = container.resolve(DatabaseService)
                
                sql = "DELETE FROM strategy_configs WHERE strategy_id = ?"
                
                with database_service.get_connection("strategy_sqlite") as conn:
                    conn.execute(sql, (strategy_id,))
                    conn.commit()
                
                logger.info(f"策略配置已从数据库中删除: {strategy_id}")
            except Exception as e_db:
                logger.error(f"从数据库中删除策略配置失败: {e_db}")
                return False

            # 从内存中删除
            del self._strategy_configs[strategy_id]

            # 清理相关的回测和优化任务
            self._cleanup_strategy_tasks(strategy_id)
            
            # 发布策略配置删除事件
            from ..events import StrategyConfigDeletedEvent
            from ..events.event_bus import get_event_bus
            event_bus = get_event_bus()
            event_bus.publish(StrategyConfigDeletedEvent(
                strategy_id=strategy_id
            ))

            logger.info(f"策略配置已删除: {strategy_id}")
            return True

        except Exception as e:
            logger.error(f"删除策略配置失败: {e}")
            return False

    def get_strategy_config(self, strategy_id: str) -> Optional[StrategyConfig]:
        """获取策略配置"""
        return self._strategy_configs.get(strategy_id)

    def get_all_strategy_configs(self) -> List[StrategyConfig]:
        """获取所有策略配置"""
        return list(self._strategy_configs.values())

    def get_all_backtest_tasks(self) -> Dict[str, BacktestTask]:
        """获取所有回测任务"""
        return self._backtest_tasks.copy()

    def clone_strategy_config(self, source_strategy_id: str, new_strategy_id: str) -> bool:
        """克隆策略配置"""
        try:
            if source_strategy_id not in self._strategy_configs:
                logger.error(f"源策略配置不存在: {source_strategy_id}")
                return False

            if new_strategy_id in self._strategy_configs:
                logger.error(f"目标策略配置已存在: {new_strategy_id}")
                return False

            source_config = self._strategy_configs[source_strategy_id]

            new_config = StrategyConfig(
                strategy_id=new_strategy_id,
                plugin_type=source_config.plugin_type,
                parameters=source_config.parameters.copy(),
                metadata=source_config.metadata.copy()
            )

            self._strategy_configs[new_strategy_id] = new_config

            logger.info(f"策略配置已克隆: {source_strategy_id} -> {new_strategy_id}")
            return True

        except Exception as e:
            logger.error(f"克隆策略配置失败: {e}")
            return False

    # 回测服务
    async def run_backtest(self,
                           strategy_id: str,
                           market_data: StandardMarketData,
                           context: StrategyContext,
                           mode: TradingMode = TradingMode.BACKTEST) -> str:
        """运行回测"""
        try:
            if strategy_id not in self._strategy_configs:
                raise ValueError(f"策略配置不存在: {strategy_id}")

            # 动态更新并发限制
            self._update_concurrent_limits()
            
            # 检查并发限制
            current_backtests = len(self._running_backtests)
            if current_backtests >= self._max_concurrent_backtests:
                raise ValueError(f"回测任务数量超限，最大允许 {self._max_concurrent_backtests} 个，当前运行中: {current_backtests} 个。请等待当前任务完成后再提交新任务。")

            # 创建回测任务
            task_id = f"backtest_{strategy_id}_{uuid.uuid4().hex[:8]}"

            backtest_task = BacktestTask(
                task_id=task_id,
                strategy_config=self._strategy_configs[strategy_id],
                market_data=market_data,
                context=context
            )

            
            self._backtest_tasks[task_id] = backtest_task

            # 创建模式上下文并传递给策略
            mode_context = ModeContext.create_backtest(
                start_date=context.start_date.isoformat() if hasattr(context.start_date, 'isoformat') else str(context.start_date),
                end_date=context.end_date.isoformat() if hasattr(context.end_date, 'isoformat') else str(context.end_date),
                mode=mode.value,
                use_full_data=mode == TradingMode.BACKTEST,
                performance_critical=mode == TradingMode.LIVE,
            )
            
            logger.info(f"创建模式上下文：{mode.value}, 策略：{strategy_id}, 时间范围：{context.start_date} 至 {context.end_date}")

            # 启动回测任务（带超时控制）
            try:
                async_task = asyncio.create_task(
                    asyncio.wait_for(
                        self._execute_backtest(task_id, mode_context),
                        timeout=self._backtest_timeout_seconds
                    )
                )
                self._running_backtests[task_id] = async_task
            except asyncio.TimeoutError:
                backtest_task.status = BacktestStatus.FAILED
                backtest_task.error_message = f"回测任务超时，已超过 {self._backtest_timeout_seconds} 秒"
                backtest_task.completed_at = datetime.now()
                logger.error(f"回测任务超时: {task_id}, 超时时间: {self._backtest_timeout_seconds}秒")
                raise ValueError(backtest_task.error_message)

            logger.info(f"回测任务已启动: {task_id}, 策略: {strategy_id}, 市场数据: {market_data.symbol}, 时间范围: {context.start_date} 至 {context.end_date}")
            return task_id

        except Exception as e:
            logger.error(f"启动回测失败: {e}, 策略ID: {strategy_id}, 错误类型: {type(e).__name__}")
            logger.error(f"回测请求上下文: market_data={market_data.symbol}, context={context.symbol} - {context.start_date} 至 {context.end_date}")
            raise

    async def _execute_backtest(self, task_id: str, mode_context: ModeContext = None) -> None:
        """执行回测"""
        backtest_task = self._backtest_tasks[task_id]
        strategy_id = backtest_task.strategy_config.strategy_id
        plugin_type = backtest_task.strategy_config.plugin_type

        try:
            backtest_task.status = BacktestStatus.RUNNING
            backtest_task.started_at = datetime.now()
            logger.info(f"开始执行回测任务: {task_id}, 策略: {strategy_id}, 插件类型: {plugin_type}")
            
            # 发布策略启动事件
            try:
                start_event = StrategyStartedEvent(
                    timestamp=datetime.now(),
                    strategy_id=strategy_id,
                    context=backtest_task.context,
                    parameters=backtest_task.strategy_config.parameters
                )
                publish_strategy_event(start_event)
            except Exception as e:
                logger.warning(f"发布策略启动事件失败: {e}")

            # 创建策略插件实例
            plugin = self.create_strategy_plugin(plugin_type)
            if not plugin:
                error_msg = f"无法创建策略插件: {plugin_type}"
                logger.error(f"回测任务 {task_id} 失败: {error_msg}")
                raise ValueError(error_msg)

            # 设置策略的模式上下文
            if mode_context and hasattr(plugin, 'mode_context'):
                plugin.mode_context = mode_context
                logger.info(f"已为策略 {strategy_id} 设置模式上下文：{mode_context.mode.value}")
            
            # 更新插件使用时间
            self._update_plugin_last_used(plugin)
            # 更新插件状态为RUNNING
            for plugin_id, plugin_info in self._strategy_plugins.items():
                if plugin_info.plugin is plugin:
                    plugin_info.status = PluginStatus.RUNNING
                    break
            
            # 补全缺失的必填参数
            strategy_info = plugin.get_strategy_info()
            updated_parameters = dict(backtest_task.strategy_config.parameters)
            
            for param_def in strategy_info.parameters:
                param_name = param_def.name
                if param_def.required and param_name not in updated_parameters:
                    updated_parameters[param_name] = param_def.default_value
                    logger.debug(f"为策略 {strategy_id} 补全必填参数: {param_name} = {param_def.default_value}")
            
            # 初始化策略
            logger.debug(f"初始化策略: {strategy_id}, 参数: {updated_parameters}")
            if not plugin.initialize_strategy(backtest_task.context, updated_parameters):
                error_msg = f"策略初始化失败: {strategy_id}, 插件: {plugin_type}"
                logger.error(f"回测任务 {task_id} 失败: {error_msg}")
                raise ValueError(error_msg)

            # 设置策略的模式上下文
            if mode_context and hasattr(plugin, 'mode_context'):
                plugin.mode_context = mode_context
                logger.info(f"已为策略 {strategy_id} 设置模式上下文：{mode_context.mode.value}")
            
            # 更新插件使用时间
            self._update_plugin_last_used(plugin)
            
            # 执行回测 - 生成信号
            logger.debug(f"生成交易信号: {strategy_id}, 市场数据大小: {len(backtest_task.market_data.datetime)}")
            
            # 获取市场数据的DataFrame格式
            market_data_df = backtest_task.market_data.to_dataframe()
            
            # 设置当前symbol属性，供插件使用
            current_symbol = backtest_task.market_data.symbol
            if hasattr(plugin, '_current_symbol'):
                plugin._current_symbol = current_symbol
            
            signals = self._call_generate_signals(plugin, market_data_df, backtest_task.context)
            backtest_task.progress = 0.5
            logger.debug(f"信号生成完成: {strategy_id}, 信号数量: {len(signals)}")
            
            # 发布信号生成事件
            if signals:
                try:
                    signal_event = SignalGeneratedEvent(
                        timestamp=datetime.now(),
                        strategy_id=strategy_id,
                        signals=signals,
                        symbol=backtest_task.market_data.symbol
                    )
                    publish_strategy_event(signal_event)
                except Exception as e:
                    logger.warning(f"发布信号生成事件失败: {e}")

            # 设置策略的模式上下文
            if mode_context and hasattr(plugin, 'mode_context'):
                plugin.mode_context = mode_context
                logger.info(f"已为策略 {strategy_id} 设置模式上下文：{mode_context.mode.value}")
            
            # 更新插件使用时间
            self._update_plugin_last_used(plugin)
            
            # 模拟交易执行和性能计算
            logger.debug(f"计算策略性能: {strategy_id}")
            performance = plugin.calculate_performance(backtest_task.context)
            backtest_task.progress = 1.0
            logger.debug(f"性能计算完成: {strategy_id}, 性能指标: {performance}")
            
            # 计算收益曲线和回撤曲线
            equity_curve, drawdown_curve = self._calculate_equity_curves(
                backtest_task.market_data, 
                backtest_task.context,
                performance
            )
            performance.equity_curve = equity_curve
            performance.drawdown_curve = drawdown_curve
            
            # 更新插件状态为IDLE
            self._update_plugin_last_used(plugin)

            # 保存结果
            backtest_task.result = performance
            backtest_task.status = BacktestStatus.COMPLETED
            backtest_task.completed_at = datetime.now()

            # 计算执行时间
            execution_time = (backtest_task.completed_at - backtest_task.started_at).total_seconds()
            
            # 缓存性能结果
            cache_key = f"{strategy_id}_{hash(str(backtest_task.strategy_config.parameters))}"
            self._performance_cache[cache_key] = performance

            logger.info(f"回测任务完成: {task_id}, 策略: {strategy_id}, 执行时间: {execution_time:.2f}秒, 信号数量: {len(signals)}")
            
            # 发布策略停止事件（成功完成）
            try:
                stop_event = StrategyStoppedEvent(
                    timestamp=datetime.now(),
                    strategy_id=strategy_id,
                    reason="completed",
                    performance=performance
                )
                publish_strategy_event(stop_event)
            except Exception as e:
                logger.warning(f"发布策略停止事件失败: {e}")

        except Exception as e:
            backtest_task.status = BacktestStatus.FAILED
            backtest_task.error_message = str(e)
            backtest_task.completed_at = datetime.now()
            
            # 记录详细错误信息
            logger.error(f"回测任务失败: {task_id}, 策略: {strategy_id}, 插件: {plugin_type}, 错误类型: {type(e).__name__}, 错误信息: {e}")
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            logger.error(f"回测上下文: {backtest_task.context}")
            
            # 发布策略错误事件
            try:
                error_event = StrategyErrorEvent(
                    timestamp=datetime.now(),
                    strategy_id=strategy_id,
                    error_message=str(e),
                    error=e,
                    stack_trace=traceback.format_exc()
                )
                publish_strategy_event(error_event)
            except Exception as event_error:
                logger.warning(f"发布策略错误事件失败: {event_error}")

        finally:
            # 清理运行中的任务
            if task_id in self._running_backtests:
                del self._running_backtests[task_id]
                logger.debug(f"清理运行中的回测任务: {task_id}")

    def _calculate_equity_curves(self, market_data: StandardMarketData, 
                                  context: StrategyContext, 
                                  performance: PerformanceMetrics) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
        """计算收益曲线和回撤曲线"""
        try:
            if not market_data or market_data.datetime is None or len(market_data.datetime) == 0:
                return None, None
            
            dates = market_data.datetime
            n_days = len(dates)
            
            if n_days == 0:
                return None, None
            
            total_return = performance.total_return

            if hasattr(total_return, 'iloc'):
                try:
                    if hasattr(total_return, 'empty'):
                        is_empty = total_return.empty
                        if not is_empty:
                            total_return = float(total_return.iloc[0])
                        else:
                            total_return = 0.0
                    elif len(total_return) > 0:
                        total_return = float(total_return.iloc[0])
                    else:
                        total_return = 0.0
                except (TypeError, ValueError, IndexError):
                    total_return = 0.0
            elif total_return is not None:
                try:
                    total_return = float(total_return)
                except (TypeError, ValueError):
                    total_return = 0.0
            else:
                total_return = 0.0
            
            daily_return = total_return / n_days if n_days > 0 else 0.0
            
            cumulative_returns = []
            for i in range(n_days):
                daily_return_with_noise = daily_return

                if i == 0:
                    cumulative_returns.append(daily_return_with_noise)
                else:
                    cumulative_returns.append(cumulative_returns[-1] + daily_return_with_noise)
            
            equity_curve = pd.Series(cumulative_returns, index=dates)
            
            if len(equity_curve) == 0:
                return None, None
            
            drawdown_curve = self._calculate_drawdown_curve(equity_curve)
            
            return equity_curve, drawdown_curve
            
        except Exception as e:
            logger.error(f"计算收益曲线失败: {e}")
            return None, None
    
    def _calculate_drawdown_curve(self, equity_curve: pd.Series) -> pd.Series:
        """计算回撤曲线"""
        try:
            if equity_curve is None or len(equity_curve) == 0:
                return pd.Series()
            
            cumulative_max = equity_curve.cummax()
            
            if len(cumulative_max) == 0:
                return pd.Series()
            
            abs_cumulative_max = cumulative_max.abs()
            
            min_value = abs_cumulative_max.abs().min()
            if pd.isna(min_value) or min_value == 0:
                abs_cumulative_max = abs_cumulative_max.replace(0, 1.0)
            
            drawdown = (equity_curve - cumulative_max) / abs_cumulative_max
            
            all_na = drawdown.isna().all()
            if all_na:
                return pd.Series()
            
            return drawdown
            
        except Exception as e:
            logger.error(f"计算回撤曲线失败: {e}")
            return pd.Series()

    def get_backtest_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取回测状态"""
        if task_id not in self._backtest_tasks:
            return None

        task = self._backtest_tasks[task_id]
        return {
            'task_id': task_id,
            'status': task.status.value,
            'progress': task.progress,
            'created_at': task.created_at,
            'started_at': task.started_at,
            'completed_at': task.completed_at,
            'error_message': task.error_message
        }

    def get_backtest_result(self, task_id: str) -> Optional[PerformanceMetrics]:
        """获取回测结果"""
        if task_id not in self._backtest_tasks:
            return None

        task = self._backtest_tasks[task_id]
        return task.result

    def cancel_backtest(self, task_id: str) -> bool:
        """取消回测"""
        try:
            if task_id in self._running_backtests:
                self._running_backtests[task_id].cancel()
                del self._running_backtests[task_id]

            if task_id in self._backtest_tasks:
                self._backtest_tasks[task_id].status = BacktestStatus.CANCELLED

            logger.info(f"回测任务已取消: {task_id}")
            return True

        except Exception as e:
            logger.error(f"取消回测任务失败: {e}")
            return False

    def get_batch_backtest_status(self, task_ids: List[str]) -> List[Dict[str, Any]]:
        """获取批量回测状态"""
        try:
            status_list = []
            for task_id in task_ids:
                if task_id in self._backtest_tasks:
                    task = self._backtest_tasks[task_id]
                    status_list.append({
                        'task_id': task_id,
                        'status': task.status.value,
                        'progress': task.progress,
                        'error_message': task.error_message
                    })
                else:
                    status_list.append({
                        'task_id': task_id,
                        'status': 'not_found',
                        'progress': 0,
                        'error_message': '任务不存在'
                    })
            return status_list
        except Exception as e:
            logger.error(f"获取批量回测状态失败: {e}")
            return []

    def cancel_batch_backtest(self, task_ids: List[str]) -> bool:
        """取消批量回测"""
        try:
            success_count = 0
            for task_id in task_ids:
                if self.cancel_backtest(task_id):
                    success_count += 1
            logger.info(f"批量取消回测任务: {success_count}/{len(task_ids)} 成功")
            return success_count == len(task_ids)
        except Exception as e:
            logger.error(f"批量取消回测任务失败: {e}")
            return False

    # 优化服务
    async def run_optimization(self,
                               strategy_id: str,
                               optimization_params: Dict[str, Any],
                               market_data: StandardMarketData,
                               context: StrategyContext) -> str:
        """运行策略优化"""
        try:
            if strategy_id not in self._strategy_configs:
                raise ValueError(f"策略配置不存在: {strategy_id}")

            # 动态更新并发限制
            self._update_concurrent_limits()
            
            # 检查并发限制
            current_optimizations = len(self._running_optimizations)
            if current_optimizations >= self._max_concurrent_optimizations:
                raise ValueError(f"优化任务数量超限，最大允许 {self._max_concurrent_optimizations} 个，当前运行中: {current_optimizations} 个。优化任务资源消耗较大，请等待当前任务完成后再提交新任务。")

            # 创建优化任务
            task_id = f"optimization_{strategy_id}_{uuid.uuid4().hex[:8]}"

            optimization_task = OptimizationTask(
                task_id=task_id,
                strategy_config=self._strategy_configs[strategy_id],
                optimization_params=optimization_params,
                market_data=market_data,
                context=context
            )

            self._optimization_tasks[task_id] = optimization_task

            # 启动优化任务（带超时控制）
            try:
                async_task = asyncio.create_task(
                    asyncio.wait_for(
                        self._execute_optimization(task_id),
                        timeout=self._optimization_timeout_seconds
                    )
                )
                self._running_optimizations[task_id] = async_task
            except asyncio.TimeoutError:
                optimization_task.status = OptimizationStatus.FAILED
                optimization_task.error_message = f"优化任务超时，已超过 {self._optimization_timeout_seconds} 秒"
                optimization_task.completed_at = datetime.now()
                logger.error(f"优化任务超时: {task_id}, 超时时间: {self._optimization_timeout_seconds}秒")
                raise ValueError(optimization_task.error_message)

            logger.info(f"优化任务已启动: {task_id}")
            return task_id

        except Exception as e:
            logger.error(f"启动优化失败: {e}")
            raise

    async def _execute_optimization(self, task_id: str) -> None:
        """执行优化"""
        optimization_task = self._optimization_tasks[task_id]
        strategy_id = optimization_task.strategy_config.strategy_id

        try:
            optimization_task.status = OptimizationStatus.RUNNING
            optimization_task.started_at = datetime.now()

            # 发布优化启动事件
            try:
                start_event = StrategyStartedEvent(
                    timestamp=datetime.now(),
                    strategy_id=strategy_id,
                    context=optimization_task.context,
                    parameters=optimization_task.optimization_params
                )
                publish_strategy_event(start_event)
            except Exception as e:
                logger.warning(f"发布优化启动事件失败: {e}")

            # 获取优化参数
            opt_params = optimization_task.optimization_params
            algorithm = opt_params.get('algorithm', 'grid_search')
            target_metric = opt_params.get('target_metric', 'total_return')
            param_ranges = opt_params.get('parameter_ranges', {})

            # 执行优化算法
            if algorithm == 'grid_search':
                await self._grid_search_optimization(optimization_task, param_ranges, target_metric)
            elif algorithm == 'random_search':
                await self._random_search_optimization(optimization_task, param_ranges, target_metric)
            elif algorithm == 'bayesian':
                await self._bayesian_optimization(optimization_task, param_ranges, target_metric)
            else:
                raise ValueError(f"不支持的优化算法: {algorithm}")

            optimization_task.status = OptimizationStatus.COMPLETED
            optimization_task.completed_at = datetime.now()

            logger.info(f"优化任务完成: {task_id}")
            
            # 发布优化停止事件
            try:
                stop_event = StrategyStoppedEvent(
                    timestamp=datetime.now(),
                    strategy_id=strategy_id,
                    reason="optimization_completed",
                    performance=optimization_task.best_performance
                )
                publish_strategy_event(stop_event)
            except Exception as e:
                logger.warning(f"发布优化停止事件失败: {e}")

        except Exception as e:
            optimization_task.status = OptimizationStatus.FAILED
            optimization_task.error_message = str(e)
            optimization_task.completed_at = datetime.now()

            logger.error(f"优化任务失败: {task_id}, 错误: {e}")
            
            # 发布优化错误事件
            try:
                error_event = StrategyErrorEvent(
                    timestamp=datetime.now(),
                    strategy_id=strategy_id,
                    error_message=str(e),
                    error=e,
                    stack_trace=traceback.format_exc()
                )
                publish_strategy_event(error_event)
            except Exception as event_error:
                logger.warning(f"发布优化错误事件失败: {event_error}")

        finally:
            # 清理运行中的任务
            if task_id in self._running_optimizations:
                del self._running_optimizations[task_id]

    async def _grid_search_optimization(self,
                                        optimization_task: OptimizationTask,
                                        param_ranges: Dict[str, Any],
                                        target_metric: str) -> None:
        """网格搜索优化"""
        # 生成参数组合
        param_combinations = self._generate_parameter_combinations(param_ranges)
        total_combinations = len(param_combinations)

        best_score = float('-inf')
        best_params = None
        best_performance = None

        for i, params in enumerate(param_combinations):
            try:
                # 更新策略参数
                test_params = optimization_task.strategy_config.parameters.copy()
                test_params.update(params)

                # 运行回测
                plugin = self.create_strategy_plugin(optimization_task.strategy_config.plugin_type)
                if plugin and plugin.initialize_strategy(optimization_task.context, test_params):
                    market_data_df = optimization_task.market_data.to_dataframe()
                    
                    # 设置当前symbol属性，供插件使用
                    if hasattr(plugin, '_current_symbol'):
                        plugin._current_symbol = optimization_task.market_data.symbol
                    
                    signals = self._call_generate_signals(plugin, market_data_df, optimization_task.context)
                    performance = plugin.calculate_performance(optimization_task.context)

                    # 评估性能
                    score = self._evaluate_performance(performance, target_metric)

                    # 记录历史
                    optimization_task.optimization_history.append({
                        'iteration': i + 1,
                        'parameters': params.copy(),
                        'performance': performance,
                        'score': score
                    })

                    # 更新最佳结果
                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                        best_performance = performance
                else:
                    self.logger.warning(f"参数组合 {params} 初始化失败")

                # 更新进度
                optimization_task.progress = (i + 1) / total_combinations

                # 避免CPU占用过高
                if i % 10 == 0:
                    await asyncio.sleep(0.01)

            except Exception as e:
                logger.warning(f"优化迭代失败: {e}")
                continue

        # 保存最佳结果
        optimization_task.best_parameters = best_params
        optimization_task.best_performance = best_performance

    async def _random_search_optimization(self,
                                          optimization_task: OptimizationTask,
                                          param_ranges: Dict[str, Any],
                                          target_metric: str) -> None:
        """随机搜索优化"""
        max_iterations = optimization_task.optimization_params.get('max_iterations', 100)

        best_score = float('-inf')
        best_params = None
        best_performance = None

        for i in range(max_iterations):
            try:
                # 随机生成参数
                params = self._generate_random_parameters(param_ranges)

                # 更新策略参数
                test_params = optimization_task.strategy_config.parameters.copy()
                test_params.update(params)

                # 运行回测
                plugin = self.create_strategy_plugin(optimization_task.strategy_config.plugin_type)
                if plugin and plugin.initialize_strategy(optimization_task.context, test_params):
                    market_data_df = optimization_task.market_data.to_dataframe()
                    
                    # 设置当前symbol属性，供插件使用
                    if hasattr(plugin, '_current_symbol'):
                        plugin._current_symbol = optimization_task.market_data.symbol
                    
                    signals = self._call_generate_signals(plugin, market_data_df, optimization_task.context)
                    performance = plugin.calculate_performance(optimization_task.context)

                    # 评估性能
                    score = self._evaluate_performance(performance, target_metric)

                    # 记录历史
                    optimization_task.optimization_history.append({
                        'iteration': i + 1,
                        'parameters': params.copy(),
                        'performance': performance,
                        'score': score
                    })

                    # 更新最佳结果
                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                        best_performance = performance
                else:
                    self.logger.warning(f"参数组合 {params} 初始化失败")

                # 更新进度
                optimization_task.progress = (i + 1) / max_iterations

                # 避免CPU占用过高
                if i % 10 == 0:
                    await asyncio.sleep(0.01)

            except Exception as e:
                logger.warning(f"优化迭代失败: {e}")
                continue

        # 保存最佳结果
        optimization_task.best_parameters = best_params
        optimization_task.best_performance = best_performance

    async def _bayesian_optimization(self,
                                     optimization_task: OptimizationTask,
                                     param_ranges: Dict[str, Any],
                                     target_metric: str) -> None:
        """贝叶斯优化（简化实现）"""
        # 这里是简化的贝叶斯优化实现
        # 实际应用中可以使用scikit-optimize等库
        max_iterations = optimization_task.optimization_params.get('max_iterations', 50)

        # 先进行少量随机搜索作为初始样本
        await self._random_search_optimization(optimization_task, param_ranges, target_metric)

        # 简化处理：使用随机搜索结果作为贝叶斯优化结果
        optimization_task.progress = 1.0

    def _generate_parameter_combinations(self, param_ranges: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成参数组合"""
        combinations = []

        # 简化实现：为每个参数生成几个值
        param_values = {}
        for param_name, param_range in param_ranges.items():
            if isinstance(param_range, dict):
                min_val = param_range.get('min', 1)
                max_val = param_range.get('max', 10)
                step = param_range.get('step', 1)
                
                # 修复：处理浮点数参数
                if isinstance(min_val, float) or isinstance(max_val, float) or isinstance(step, float):
                    # 使用numpy.arange处理浮点数
                    import numpy as np
                    # 生成浮点数序列，然后转换为列表
                    param_values[param_name] = np.arange(min_val, max_val + step / 2, step).tolist()
                else:
                    # 整数参数使用range
                    param_values[param_name] = list(range(min_val, max_val + 1, step))
            elif isinstance(param_range, list):
                param_values[param_name] = param_range

        # 生成笛卡尔积
        import itertools
        keys = list(param_values.keys())
        values = list(param_values.values())

        for combination in itertools.product(*values):
            combinations.append(dict(zip(keys, combination)))

        return combinations

    def _generate_random_parameters(self, param_ranges: Dict[str, Any]) -> Dict[str, Any]:
        """生成随机参数"""
        import random

        params = {}
        for param_name, param_range in param_ranges.items():
            if isinstance(param_range, dict):
                min_val = param_range.get('min', 1)
                max_val = param_range.get('max', 10)
                if isinstance(min_val, int) and isinstance(max_val, int):
                    params[param_name] = random.randint(min_val, max_val)
                else:
                    params[param_name] = random.uniform(min_val, max_val)
            elif isinstance(param_range, list):
                params[param_name] = random.choice(param_range)

        return params

    def _evaluate_performance(self, performance: PerformanceMetrics, target_metric: str) -> float:
        """评估性能指标"""
        def _safe_float(value):
            """安全地将值转换为 float，处理 pandas Series 等情况"""
            if value is None:
                return 0.0
            if hasattr(value, 'iloc'):
                try:
                    if hasattr(value, 'empty') and not value.empty:
                        return float(value.iloc[0])
                    elif len(value) > 0:
                        return float(value.iloc[0])
                    else:
                        return 0.0
                except (TypeError, ValueError, IndexError):
                    return 0.0
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0
        
        if target_metric == 'total_return':
            return _safe_float(performance.total_return)
        elif target_metric == 'sharpe_ratio':
            return _safe_float(performance.sharpe_ratio)
        elif target_metric == 'max_drawdown':
            return -_safe_float(performance.max_drawdown)  # 负值，因为回撤越小越好
        elif target_metric == 'win_rate':
            return _safe_float(performance.win_rate)
        elif target_metric == 'profit_factor':
            return _safe_float(performance.profit_factor)
        else:
            # 默认使用总收益率
            return _safe_float(performance.total_return)

    def get_optimization_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取优化状态"""
        if task_id not in self._optimization_tasks:
            return None

        task = self._optimization_tasks[task_id]
        return {
            'task_id': task_id,
            'status': task.status.value,
            'progress': task.progress,
            'created_at': task.created_at,
            'started_at': task.started_at,
            'completed_at': task.completed_at,
            'error_message': task.error_message,
            'iterations_completed': len(task.optimization_history)
        }

    def get_optimization_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取优化结果"""
        if task_id not in self._optimization_tasks:
            return None

        task = self._optimization_tasks[task_id]
        return {
            'best_parameters': task.best_parameters,
            'best_performance': task.best_performance,
            'optimization_history': task.optimization_history
        }

    def cancel_optimization(self, task_id: str) -> bool:
        """取消优化"""
        try:
            if task_id in self._running_optimizations:
                self._running_optimizations[task_id].cancel()
                del self._running_optimizations[task_id]

            if task_id in self._optimization_tasks:
                self._optimization_tasks[task_id].status = OptimizationStatus.CANCELLED

            logger.info(f"优化任务已取消: {task_id}")
            return True

        except Exception as e:
            logger.error(f"取消优化任务失败: {e}")
            return False

    def get_optimization_results(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取优化结果"""
        try:
            if task_id not in self._optimization_tasks:
                logger.warning(f"优化任务不存在: {task_id}")
                return None

            task = self._optimization_tasks[task_id]
            
            if task.status != OptimizationStatus.COMPLETED:
                logger.warning(f"优化任务未完成: {task_id}, 状态: {task.status}")
                return None

            # 提取优化结果
            results = {
                'task_id': task_id,
                'strategy_id': task.strategy_config.strategy_id,
                'status': task.status.value,
                'best_params': task.best_params,
                'best_metric_value': task.best_metric_value,
                'target_metric': task.optimization_params.get('target_metric', 'total_return'),
                'total_iterations': len(task.iteration_history),
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'duration_seconds': (task.completed_at - task.started_at).total_seconds() if task.started_at and task.completed_at else None
            }

            logger.info(f"获取优化结果成功: {task_id}")
            return results

        except Exception as e:
            logger.error(f"获取优化结果失败: {e}")
            return None

    def apply_strategy_parameters(self, strategy_id: str, parameters: Dict[str, Any]) -> bool:
        """应用策略参数"""
        try:
            if strategy_id not in self._strategy_configs:
                logger.error(f"策略配置不存在: {strategy_id}")
                return False

            # 更新策略配置的参数
            strategy_config = self._strategy_configs[strategy_id]
            strategy_config.parameters.update(parameters)

            logger.info(f"成功应用参数到策略 {strategy_id}: {parameters}")
            return True

        except Exception as e:
            logger.error(f"应用策略参数失败: {e}")
            return False

    # 策略评估服务
    def evaluate_strategy_performance(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """评估策略性能"""
        try:
            if strategy_id not in self._strategy_configs:
                return None

            # 获取该策略的所有回测结果
            strategy_backtests = [task for task in self._backtest_tasks.values()
                                  if task.strategy_config.strategy_id == strategy_id
                                  and task.status == BacktestStatus.COMPLETED]

            if not strategy_backtests:
                return None

            # 计算统计指标
            performances = [task.result for task in strategy_backtests if task.result]

            if not performances:
                return None

            def _safe_float(value):
                """安全地将值转换为 float，处理 pandas Series 等情况"""
                if value is None:
                    return 0.0
                if hasattr(value, 'iloc'):
                    try:
                        if hasattr(value, 'empty') and not value.empty:
                            return float(value.iloc[0])
                        elif len(value) > 0:
                            return float(value.iloc[0])
                        else:
                            return 0.0
                    except (TypeError, ValueError, IndexError):
                        return 0.0
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return 0.0

            total_returns = [_safe_float(p.total_return) for p in performances]
            sharpe_ratios = [_safe_float(p.sharpe_ratio) for p in performances]
            max_drawdowns = [_safe_float(p.max_drawdown) for p in performances]
            win_rates = [_safe_float(p.win_rate) for p in performances]

            evaluation = {
                'strategy_id': strategy_id,
                'total_backtests': len(performances),
                'performance_stats': {
                    'avg_total_return': np.mean(total_returns),
                    'std_total_return': np.std(total_returns),
                    'min_total_return': np.min(total_returns),
                    'max_total_return': np.max(total_returns),
                    'avg_sharpe_ratio': np.mean(sharpe_ratios),
                    'avg_max_drawdown': np.mean(max_drawdowns),
                    'avg_win_rate': np.mean(win_rates),
                },
                'consistency_score': 1 - (np.std(total_returns) / np.mean(total_returns)) if np.mean(total_returns) != 0 else 0,
                'risk_adjusted_return': np.mean(total_returns) / (np.mean(max_drawdowns) + 0.01),  # 避免除零
                'evaluation_date': datetime.now()
            }

            return evaluation

        except Exception as e:
            logger.error(f"评估策略性能失败: {e}")
            return None

    def compare_strategies(self, strategy_ids: List[str]) -> Optional[Dict[str, Any]]:
        """比较多个策略"""
        try:
            evaluations = {}

            for strategy_id in strategy_ids:
                evaluation = self.evaluate_strategy_performance(strategy_id)
                if evaluation:
                    evaluations[strategy_id] = evaluation

            if not evaluations:
                return None

            # 生成比较报告
            comparison = {
                'strategies': evaluations,
                'rankings': {
                    'by_total_return': sorted(evaluations.keys(),
                                              key=lambda s: evaluations[s]['performance_stats']['avg_total_return'],
                                              reverse=True),
                    'by_sharpe_ratio': sorted(evaluations.keys(),
                                              key=lambda s: evaluations[s]['performance_stats']['avg_sharpe_ratio'],
                                              reverse=True),
                    'by_consistency': sorted(evaluations.keys(),
                                             key=lambda s: evaluations[s]['consistency_score'],
                                             reverse=True),
                    'by_risk_adjusted_return': sorted(evaluations.keys(),
                                                      key=lambda s: evaluations[s]['risk_adjusted_return'],
                                                      reverse=True)
                },
                'comparison_date': datetime.now()
            }

            return comparison

        except Exception as e:
            logger.error(f"比较策略失败: {e}")
            return None

    # 辅助方法
    def _cleanup_strategy_tasks(self, strategy_id: str) -> None:
        """清理策略相关的任务"""
        # 清理回测任务
        backtest_tasks_to_remove = [task_id for task_id, task in self._backtest_tasks.items()
                                    if task.strategy_config.strategy_id == strategy_id]
        for task_id in backtest_tasks_to_remove:
            self.cancel_backtest(task_id)
            del self._backtest_tasks[task_id]

        # 清理优化任务
        optimization_tasks_to_remove = [task_id for task_id, task in self._optimization_tasks.items()
                                        if task.strategy_config.strategy_id == strategy_id]
        for task_id in optimization_tasks_to_remove:
            self.cancel_optimization(task_id)
            del self._optimization_tasks[task_id]

    def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            'service_name': 'StrategyService',
            'status': 'running',
            'plugin_types_count': len(self._plugin_factories),
            'strategy_configs_count': len(self._strategy_configs),
            'active_backtests': len(self._running_backtests),
            'active_optimizations': len(self._running_optimizations),
            'total_backtest_tasks': len(self._backtest_tasks),
            'total_optimization_tasks': len(self._optimization_tasks),
            'performance_cache_size': len(self._performance_cache),
            'last_update': datetime.now().isoformat()
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能监控指标"""
        try:
            # 系统资源指标
            cpu_usage = psutil.cpu_percent(interval=0.1)
            mem_usage = psutil.virtual_memory().percent
            available_mem_gb = psutil.virtual_memory().available / (1024 ** 3)
            
            # 任务执行统计
            backtest_stats = self._calculate_task_statistics(self._backtest_tasks, BacktestStatus)
            optimization_stats = self._calculate_task_statistics(self._optimization_tasks, OptimizationStatus)
            
            # 插件使用统计
            plugin_stats = self._calculate_plugin_statistics()
            
            # 性能阈值检查
            threshold_checks = self._check_performance_thresholds(cpu_usage, mem_usage, available_mem_gb)
            
            return {
                'system_metrics': {
                    'cpu_usage': cpu_usage,
                    'memory_usage': mem_usage,
                    'available_memory_gb': available_mem_gb,
                    'cpu_count': os.cpu_count() or 4,
                    'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
                },
                'task_metrics': {
                    'backtest': backtest_stats,
                    'optimization': optimization_stats
                },
                'plugin_metrics': plugin_stats,
                'concurrency_metrics': {
                    'max_concurrent_backtests': self._max_concurrent_backtests,
                    'max_concurrent_optimizations': self._max_concurrent_optimizations,
                    'current_backtests': len(self._running_backtests),
                    'current_optimizations': len(self._running_optimizations)
                },
                'cache_metrics': {
                    'performance_cache_size': len(self._performance_cache),
                    'plugin_info_cache_size': len(self._plugin_info_cache),
                    'instance_pool_size': sum(len(pool) for pool in self._plugin_instance_pool.values())
                },
                'threshold_checks': threshold_checks,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取性能指标失败: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def _calculate_task_statistics(self, tasks: Dict, status_enum) -> Dict[str, Any]:
        """计算任务统计信息"""
        try:
            total = len(tasks)
            if total == 0:
                return {
                    'total': 0,
                    'by_status': {},
                    'avg_duration_seconds': 0,
                    'success_rate': 0
                }
            
            # 按状态统计
            by_status = {}
            for status in status_enum:
                count = sum(1 for task in tasks.values() if task.status == status)
                if count > 0:
                    by_status[status.value] = count
            
            # 计算平均执行时间
            completed_tasks = [task for task in tasks.values() 
                              if task.status == status_enum.COMPLETED 
                              and task.started_at 
                              and task.completed_at]
            
            avg_duration = 0
            if completed_tasks:
                durations = [(task.completed_at - task.started_at).total_seconds() 
                           for task in completed_tasks]
                avg_duration = sum(durations) / len(durations)
            
            # 计算成功率
            success_count = len(completed_tasks)
            failed_count = sum(1 for task in tasks.values() 
                             if task.status == status_enum.FAILED)
            success_rate = success_count / (success_count + failed_count) if (success_count + failed_count) > 0 else 0
            
            return {
                'total': total,
                'by_status': by_status,
                'avg_duration_seconds': round(avg_duration, 2),
                'success_rate': round(success_rate, 4)
            }
        except Exception as e:
            logger.error(f"计算任务统计失败: {e}")
            return {'error': str(e)}

    def _calculate_plugin_statistics(self) -> Dict[str, Any]:
        """计算插件统计信息"""
        try:
            plugin_stats = {
                'total_plugins': len(self._strategy_plugins),
                'by_status': {},
                'by_type': {},
                'total_usage_count': 0,
                'total_error_count': 0,
                'instance_pool_stats': {}
            }
            
            # 按状态统计
            for status in PluginStatus:
                count = sum(1 for plugin in self._strategy_plugins.values() 
                          if plugin.status == status)
                if count > 0:
                    plugin_stats['by_status'][status.value] = count
            
            # 按类型统计
            for plugin_info in self._strategy_plugins.values():
                plugin_type = plugin_info.plugin_type
                if plugin_type not in plugin_stats['by_type']:
                    plugin_stats['by_type'][plugin_type] = 0
                plugin_stats['by_type'][plugin_type] += 1
                plugin_stats['total_usage_count'] += plugin_info.usage_count
                plugin_stats['total_error_count'] += plugin_info.error_count
            
            # 实例池统计
            for plugin_type, pool in self._plugin_instance_pool.items():
                plugin_stats['instance_pool_stats'][plugin_type] = {
                    'pool_size': len(pool),
                    'max_size': self._instance_pool_max_size
                }
            
            return plugin_stats
        except Exception as e:
            logger.error(f"计算插件统计失败: {e}")
            return {'error': str(e)}

    def _check_performance_thresholds(self, cpu_usage: float, mem_usage: float, available_mem_gb: float) -> Dict[str, Any]:
        """检查性能阈值"""
        try:
            warnings = []
            alerts = []
            
            # CPU使用率检查
            if cpu_usage > 90:
                alerts.append({
                    'type': 'cpu_usage',
                    'severity': 'critical',
                    'current_value': cpu_usage,
                    'threshold': 90,
                    'message': f'CPU使用率过高: {cpu_usage:.1f}%'
                })
            elif cpu_usage > 75:
                warnings.append({
                    'type': 'cpu_usage',
                    'severity': 'warning',
                    'current_value': cpu_usage,
                    'threshold': 75,
                    'message': f'CPU使用率较高: {cpu_usage:.1f}%'
                })
            
            # 内存使用率检查
            if mem_usage > 90:
                alerts.append({
                    'type': 'memory_usage',
                    'severity': 'critical',
                    'current_value': mem_usage,
                    'threshold': 90,
                    'message': f'内存使用率过高: {mem_usage:.1f}%'
                })
            elif mem_usage > 80:
                warnings.append({
                    'type': 'memory_usage',
                    'severity': 'warning',
                    'current_value': mem_usage,
                    'threshold': 80,
                    'message': f'内存使用率较高: {mem_usage:.1f}%'
                })
            
            # 可用内存检查
            if available_mem_gb < 1.0:
                alerts.append({
                    'type': 'available_memory',
                    'severity': 'critical',
                    'current_value': available_mem_gb,
                    'threshold': 1.0,
                    'message': f'可用内存不足: {available_mem_gb:.2f}GB'
                })
            elif available_mem_gb < 2.0:
                warnings.append({
                    'type': 'available_memory',
                    'severity': 'warning',
                    'current_value': available_mem_gb,
                    'threshold': 2.0,
                    'message': f'可用内存较低: {available_mem_gb:.2f}GB'
                })
            
            # 任务队列检查
            pending_backtests = sum(1 for task in self._backtest_tasks.values() 
                                 if task.status == BacktestStatus.PENDING)
            if pending_backtests > 10:
                warnings.append({
                    'type': 'pending_tasks',
                    'severity': 'warning',
                    'current_value': pending_backtests,
                    'threshold': 10,
                    'message': f'待处理回测任务过多: {pending_backtests}'
                })
            
            # 插件错误率检查
            total_usage = sum(plugin.usage_count for plugin in self._strategy_plugins.values())
            total_errors = sum(plugin.error_count for plugin in self._strategy_plugins.values())
            if total_usage > 0:
                error_rate = total_errors / total_usage
                if error_rate > 0.1:  # 错误率超过10%
                    alerts.append({
                        'type': 'plugin_error_rate',
                        'severity': 'critical',
                        'current_value': error_rate,
                        'threshold': 0.1,
                        'message': f'插件错误率过高: {error_rate*100:.1f}%'
                    })
                elif error_rate > 0.05:  # 错误率超过5%
                    warnings.append({
                        'type': 'plugin_error_rate',
                        'severity': 'warning',
                        'current_value': error_rate,
                        'threshold': 0.05,
                        'message': f'插件错误率较高: {error_rate*100:.1f}%'
                    })
            
            return {
                'status': 'healthy' if not alerts and not warnings else 'warning' if not alerts else 'critical',
                'warnings_count': len(warnings),
                'alerts_count': len(alerts),
                'warnings': warnings,
                'alerts': alerts
            }
        except Exception as e:
            logger.error(f"检查性能阈值失败: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        try:
            metrics = self.get_performance_metrics()
            
            # 生成性能评分
            system_score = self._calculate_system_score(metrics)
            task_score = self._calculate_task_score(metrics)
            plugin_score = self._calculate_plugin_score(metrics)
            
            overall_score = (system_score + task_score + plugin_score) / 3
            
            # 生成建议
            recommendations = self._generate_performance_recommendations(metrics)
            
            return {
                'overall_score': round(overall_score, 2),
                'component_scores': {
                    'system': round(system_score, 2),
                    'tasks': round(task_score, 2),
                    'plugins': round(plugin_score, 2)
                },
                'performance_grade': self._get_performance_grade(overall_score),
                'metrics': metrics,
                'recommendations': recommendations,
                'report_time': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"生成性能报告失败: {e}")
            return {
                'error': str(e),
                'report_time': datetime.now().isoformat()
            }

    def _calculate_system_score(self, metrics: Dict[str, Any]) -> float:
        """计算系统资源评分"""
        try:
            system_metrics = metrics.get('system_metrics', {})
            cpu_usage = system_metrics.get('cpu_usage', 50)
            mem_usage = system_metrics.get('memory_usage', 50)
            available_mem = system_metrics.get('available_memory_gb', 8)
            
            # CPU评分（使用率越低越好）
            cpu_score = max(0, 100 - cpu_usage)
            
            # 内存评分（使用率越低越好）
            mem_score = max(0, 100 - mem_usage)
            
            # 可用内存评分（越多越好，8GB为满分）
            mem_available_score = min(100, available_mem * 12.5)
            
            return (cpu_score + mem_score + mem_available_score) / 3
        except Exception as e:
            logger.error(f"计算系统评分失败: {e}")
            return 50.0

    def _calculate_task_score(self, metrics: Dict[str, Any]) -> float:
        """计算任务执行评分"""
        try:
            task_metrics = metrics.get('task_metrics', {})
            backtest_stats = task_metrics.get('backtest', {})
            optimization_stats = task_metrics.get('optimization', {})
            
            # 成功率评分
            backtest_success_rate = backtest_stats.get('success_rate', 0.9)
            optimization_success_rate = optimization_stats.get('success_rate', 0.9)
            success_score = (backtest_success_rate + optimization_success_rate) / 2 * 100
            
            # 待处理任务评分（越少越好）
            pending_backtests = backtest_stats.get('by_status', {}).get('pending', 0)
            pending_optimizations = optimization_stats.get('by_status', {}).get('pending', 0)
            pending_penalty = min(30, (pending_backtests + pending_optimizations) * 3)
            
            return max(0, success_score - pending_penalty)
        except Exception as e:
            logger.error(f"计算任务评分失败: {e}")
            return 50.0

    def _calculate_plugin_score(self, metrics: Dict[str, Any]) -> float:
        """计算插件健康度评分"""
        try:
            plugin_metrics = metrics.get('plugin_metrics', {})
            total_errors = plugin_metrics.get('total_error_count', 0)
            total_usage = plugin_metrics.get('total_usage_count', 1)
            
            # 错误率评分（错误率越低越好）
            error_rate = total_errors / total_usage if total_usage > 0 else 0
            error_score = max(0, 100 - error_rate * 1000)
            
            return error_score
        except Exception as e:
            logger.error(f"计算插件评分失败: {e}")
            return 50.0

    def _get_performance_grade(self, score: float) -> str:
        """获取性能等级"""
        if score >= 90:
            return 'A+ (优秀)'
        elif score >= 80:
            return 'A (良好)'
        elif score >= 70:
            return 'B (中等)'
        elif score >= 60:
            return 'C (一般)'
        else:
            return 'D (需改进)'

    def _generate_performance_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """生成性能优化建议"""
        recommendations = []
        
        try:
            threshold_checks = metrics.get('threshold_checks', {})
            alerts = threshold_checks.get('alerts', [])
            warnings = threshold_checks.get('warnings', [])
            
            # 处理告警
            for alert in alerts:
                alert_type = alert.get('type')
                if alert_type == 'cpu_usage':
                    recommendations.append("建议：减少并发回测任务数量，或升级CPU资源")
                elif alert_type == 'memory_usage' or alert_type == 'available_memory':
                    recommendations.append("建议：清理缓存，减少数据加载量，或增加内存")
                elif alert_type == 'plugin_error_rate':
                    recommendations.append("建议：检查插件实现，修复错误，或更换插件")
            
            # 处理警告
            for warning in warnings:
                warning_type = warning.get('type')
                if warning_type == 'cpu_usage':
                    recommendations.append("建议：监控CPU使用率，避免长时间高负载")
                elif warning_type == 'memory_usage' or warning_type == 'available_memory':
                    recommendations.append("建议：优化内存使用，定期清理无用数据")
                elif warning_type == 'pending_tasks':
                    recommendations.append("建议：增加并发处理能力，或优化任务调度")
                elif warning_type == 'plugin_error_rate':
                    recommendations.append("建议：检查插件日志，优化插件性能")
            
            # 系统资源建议
            system_metrics = metrics.get('system_metrics', {})
            cpu_usage = system_metrics.get('cpu_usage', 0)
            mem_usage = system_metrics.get('memory_usage', 0)
            
            if cpu_usage < 30 and mem_usage < 40:
                recommendations.append("系统资源充足，可以考虑增加并发任务数量")
            
            # 缓存建议
            cache_metrics = metrics.get('cache_metrics', {})
            if cache_metrics.get('performance_cache_size', 0) > 1000:
                recommendations.append("建议：定期清理性能缓存，避免占用过多内存")
            
            if not recommendations:
                recommendations.append("系统运行状态良好，无需特殊优化")
            
        except Exception as e:
            logger.error(f"生成性能建议失败: {e}")
            recommendations.append("无法生成性能建议")
        
        return recommendations

    # ===========================================
    # 策略模板管理
    # ===========================================
    
    def _load_builtin_templates(self) -> None:
        """加载内置策略模板"""
        try:
            # 定义内置模板
            builtin_templates = [
                StrategyTemplate(
                    template_id="ma_crossover",
                    name="MA交叉策略",
                    description="基于移动平均线的经典交叉策略，适合趋势明显的市场",
                    plugin_type="factorweave",
                    default_parameters={
                        "fast_period": 10,
                        "slow_period": 20,
                        "signal_period": 5
                    },
                    parameter_descriptions={
                        "fast_period": "快速移动平均线周期",
                        "slow_period": "慢速移动平均线周期",
                        "signal_period": "信号平滑周期"
                    },
                    tags=["趋势", "经典", "适合新手"],
                    category="trend",
                    is_builtin=True
                ),
                StrategyTemplate(
                    template_id="macd_strategy",
                    name="MACD策略",
                    description="基于MACD指标的动量策略，捕捉趋势转折点",
                    plugin_type="factorweave",
                    default_parameters={
                        "fast_period": 12,
                        "slow_period": 26,
                        "signal_period": 9
                    },
                    parameter_descriptions={
                        "fast_period": "快速EMA周期",
                        "slow_period": "慢速EMA周期",
                        "signal_period": "信号线周期"
                    },
                    tags=["动量", "经典", "趋势跟踪"],
                    category="momentum",
                    is_builtin=True
                ),
                StrategyTemplate(
                    template_id="rsi_strategy",
                    name="RSI策略",
                    description="基于RSI指标的超买超卖策略，适合震荡市场",
                    plugin_type="factorweave",
                    default_parameters={
                        "rsi_period": 14,
                        "overbought": 70,
                        "oversold": 30
                    },
                    parameter_descriptions={
                        "rsi_period": "RSI计算周期",
                        "overbought": "超买阈值",
                        "oversold": "超卖阈值"
                    },
                    tags=["震荡", "反转", "风险控制"],
                    category="reversion",
                    is_builtin=True
                ),
                StrategyTemplate(
                    template_id="vwap_reversion",
                    name="VWAP均值回归策略",
                    description="基于VWAP的均值回归策略，适合日内交易",
                    plugin_type="vwap_reversion",
                    default_parameters={
                        "lookback_period": 20,
                        "entry_threshold": 0.02,
                        "exit_threshold": 0.01
                    },
                    parameter_descriptions={
                        "lookback_period": "回望周期",
                        "entry_threshold": "入场阈值（相对于VWAP的偏差）",
                        "exit_threshold": "出场阈值"
                    },
                    tags=["日内", "均值回归", "高频"],
                    category="intraday",
                    is_builtin=True
                ),
                StrategyTemplate(
                    template_id="adj_momentum",
                    name="复权价格动量策略",
                    description="基于复权价格的动量策略，捕捉强势股票",
                    plugin_type="adj_momentum",
                    default_parameters={
                        "lookback_period": 20,
                        "momentum_threshold": 0.05,
                        "top_n": 10
                    },
                    parameter_descriptions={
                        "lookback_period": "动量计算周期",
                        "momentum_threshold": "动量阈值",
                        "top_n": "选股数量"
                    },
                    tags=["动量", "选股", "趋势"],
                    category="momentum",
                    is_builtin=True
                )
            ]
            
            # 加载内置模板
            for template in builtin_templates:
                self._strategy_templates[template.template_id] = template
            
            logger.info(f"已加载 {len(builtin_templates)} 个内置策略模板")
            
        except Exception as e:
            logger.error(f"加载内置策略模板失败: {e}")
    
    def get_all_templates(self) -> List[StrategyTemplate]:
        """获取所有策略模板"""
        return list(self._strategy_templates.values())
    
    def get_template(self, template_id: str) -> Optional[StrategyTemplate]:
        """获取指定模板"""
        return self._strategy_templates.get(template_id)
    
    def get_templates_by_category(self, category: str) -> List[StrategyTemplate]:
        """按分类获取模板"""
        return [t for t in self._strategy_templates.values() if t.category == category]
    
    def get_templates_by_tags(self, tags: List[str]) -> List[StrategyTemplate]:
        """按标签获取模板"""
        return [t for t in self._strategy_templates.values() 
                if any(tag in t.tags for tag in tags)]
    
    def create_template(self, template: StrategyTemplate) -> bool:
        """创建新模板"""
        try:
            if template.template_id in self._strategy_templates:
                logger.warning(f"模板 {template.template_id} 已存在")
                return False
            
            self._strategy_templates[template.template_id] = template
            logger.info(f"创建策略模板: {template.name}")
            return True
            
        except Exception as e:
            logger.error(f"创建策略模板失败: {e}")
            return False
    
    def update_template(self, template_id: str, template: StrategyTemplate) -> bool:
        """更新模板"""
        try:
            if template_id not in self._strategy_templates:
                logger.warning(f"模板 {template_id} 不存在")
                return False
            
            # 更新时间戳
            template.updated_at = datetime.now()
            self._strategy_templates[template_id] = template
            logger.info(f"更新策略模板: {template.name}")
            return True
            
        except Exception as e:
            logger.error(f"更新策略模板失败: {e}")
            return False
    
    def delete_template(self, template_id: str) -> bool:
        """删除模板"""
        try:
            if template_id not in self._strategy_templates:
                logger.warning(f"模板 {template_id} 不存在")
                return False
            
            template = self._strategy_templates[template_id]
            if template.is_builtin:
                logger.warning(f"不能删除内置模板: {template_id}")
                return False
            
            del self._strategy_templates[template_id]
            logger.info(f"删除策略模板: {template_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除策略模板失败: {e}")
            return False
    
    def apply_template(self, template_id: str, strategy_id: str = None) -> Optional[StrategyConfig]:
        """应用模板创建策略配置"""
        try:
            template = self.get_template(template_id)
            if not template:
                logger.warning(f"模板 {template_id} 不存在")
                return None
            
            # 生成策略ID
            if not strategy_id:
                strategy_id = f"{template.template_id}_{int(datetime.now().timestamp())}"
            
            # 创建策略配置
            config = StrategyConfig(
                strategy_id=strategy_id,
                plugin_type=template.plugin_type,
                parameters=template.default_parameters.copy(),
                enabled=True,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata={
                    "template_id": template.template_id,
                    "template_name": template.name,
                    "description": template.description,
                    "category": template.category,
                    "tags": template.tags
                }
            )
            
            logger.info(f"应用模板 {template.name} 创建策略: {strategy_id}")
            return config
            
        except Exception as e:
            logger.error(f"应用模板失败: {e}")
            return None
    
    def export_template(self, template_id: str, file_path: str) -> bool:
        """导出模板到文件"""
        try:
            template = self.get_template(template_id)
            if not template:
                logger.warning(f"模板 {template_id} 不存在")
                return False
            
            # 转换为字典
            template_dict = {
                'template_id': template.template_id,
                'name': template.name,
                'description': template.description,
                'plugin_type': template.plugin_type,
                'default_parameters': template.default_parameters,
                'parameter_descriptions': template.parameter_descriptions,
                'tags': template.tags,
                'category': template.category,
                'is_builtin': template.is_builtin,
                'exported_at': datetime.now().isoformat()
            }
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(template_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"导出模板 {template.name} 到 {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出模板失败: {e}")
            return False
    
    def import_template(self, file_path: str) -> Optional[StrategyTemplate]:
        """从文件导入模板"""
        try:
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                template_dict = json.load(f)
            
            # 创建模板对象
            template = StrategyTemplate(
                template_id=template_dict.get('template_id', f"imported_{int(datetime.now().timestamp())}"),
                name=template_dict.get('name', '未命名模板'),
                description=template_dict.get('description', ''),
                plugin_type=template_dict.get('plugin_type', 'factorweave'),
                default_parameters=template_dict.get('default_parameters', {}),
                parameter_descriptions=template_dict.get('parameter_descriptions', {}),
                tags=template_dict.get('tags', []),
                category=template_dict.get('category', 'general'),
                is_builtin=False
            )
            
            # 保存模板
            if self.create_template(template):
                logger.info(f"从 {file_path} 导入模板: {template.name}")
                return template
            else:
                return None
            
        except Exception as e:
            logger.error(f"导入模板失败: {e}")
            return None

    # ===========================================
    # 策略分组和标签管理
    # ===========================================
    
    def _load_builtin_groups(self) -> None:
        """加载内置策略分组"""
        try:
            # 定义内置分组
            builtin_groups = [
                StrategyGroup(
                    group_id="trend",
                    name="趋势策略",
                    description="基于趋势跟踪的策略",
                    color="#3B82F6",  # 蓝色
                    icon="📈",
                    is_builtin=True
                ),
                StrategyGroup(
                    group_id="momentum",
                    name="动量策略",
                    description="基于价格动量的策略",
                    color="#8B5CF6",  # 紫色
                    icon="🚀",
                    is_builtin=True
                ),
                StrategyGroup(
                    group_id="reversion",
                    name="均值回归策略",
                    description="基于均值回归的策略",
                    color="#10B981",  # 绿色
                    icon="🔄",
                    is_builtin=True
                ),
                StrategyGroup(
                    group_id="intraday",
                    name="日内策略",
                    description="适合日内交易的策略",
                    color="#F59E0B",  # 橙色
                    icon="⏱️",
                    is_builtin=True
                ),
                StrategyGroup(
                    group_id="custom",
                    name="自定义策略",
                    description="用户自定义的策略",
                    color="#6B7280",  # 灰色
                    icon="⚙️",
                    is_builtin=True
                ),
                StrategyGroup(
                    group_id="favorite",
                    name="收藏策略",
                    description="用户收藏的策略",
                    color="#EF4444",  # 红色
                    icon="⭐",
                    is_builtin=True
                )
            ]
            
            # 加载内置分组
            for group in builtin_groups:
                self._strategy_groups[group.group_id] = group
            
            logger.info(f"已加载 {len(builtin_groups)} 个内置策略分组")
            
        except Exception as e:
            logger.error(f"加载内置策略分组失败: {e}")
    
    def get_all_groups(self) -> List[StrategyGroup]:
        """获取所有策略分组"""
        return list(self._strategy_groups.values())
    
    def get_group(self, group_id: str) -> Optional[StrategyGroup]:
        """获取指定分组"""
        return self._strategy_groups.get(group_id)
    
    def create_group(self, group: StrategyGroup) -> bool:
        """创建新分组"""
        try:
            if group.group_id in self._strategy_groups:
                logger.warning(f"分组 {group.group_id} 已存在")
                return False
            
            self._strategy_groups[group.group_id] = group
            logger.info(f"创建策略分组: {group.name}")
            return True
            
        except Exception as e:
            logger.error(f"创建策略分组失败: {e}")
            return False
    
    def update_group(self, group_id: str, group: StrategyGroup) -> bool:
        """更新分组"""
        try:
            if group_id not in self._strategy_groups:
                logger.warning(f"分组 {group_id} 不存在")
                return False
            
            existing_group = self._strategy_groups[group_id]
            if existing_group.is_builtin:
                logger.warning(f"不能修改内置分组: {group_id}")
                return False
            
            self._strategy_groups[group_id] = group
            logger.info(f"更新策略分组: {group.name}")
            return True
            
        except Exception as e:
            logger.error(f"更新策略分组失败: {e}")
            return False
    
    def delete_group(self, group_id: str) -> bool:
        """删除分组"""
        try:
            if group_id not in self._strategy_groups:
                logger.warning(f"分组 {group_id} 不存在")
                return False
            
            group = self._strategy_groups[group_id]
            if group.is_builtin:
                logger.warning(f"不能删除内置分组: {group_id}")
                return False
            
            # 将该分组下的策略移到默认分组
            for strategy_id, config in self._strategy_configs.items():
                if config.group == group_id:
                    config.metadata['group'] = 'default'
            
            del self._strategy_groups[group_id]
            logger.info(f"删除策略分组: {group_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除策略分组失败: {e}")
            return False
    
    def assign_strategy_to_group(self, strategy_id: str, group_id: str) -> bool:
        """将策略分配到分组"""
        try:
            if strategy_id not in self._strategy_configs:
                logger.warning(f"策略 {strategy_id} 不存在")
                return False
            
            if group_id not in self._strategy_groups:
                logger.warning(f"分组 {group_id} 不存在")
                return False
            
            self._strategy_configs[strategy_id].metadata['group'] = group_id
            logger.info(f"将策略 {strategy_id} 分配到分组 {group_id}")
            return True
            
        except Exception as e:
            logger.error(f"分配策略到分组失败: {e}")
            return False
    
    def get_strategies_by_group(self, group_id: str) -> List[StrategyConfig]:
        """获取指定分组下的所有策略"""
        return [config for config in self._strategy_configs.values() 
                if config.group == group_id]
    
    def add_strategy_tags(self, strategy_id: str, tags: List[str]) -> bool:
        """为策略添加标签"""
        try:
            if strategy_id not in self._strategy_configs:
                logger.warning(f"策略 {strategy_id} 不存在")
                return False
            
            current_tags = self._strategy_configs[strategy_id].tags
            # 合并标签，去重
            new_tags = list(set(current_tags + tags))
            self._strategy_configs[strategy_id].metadata['tags'] = new_tags
            
            logger.info(f"为策略 {strategy_id} 添加标签: {tags}")
            return True
            
        except Exception as e:
            logger.error(f"添加策略标签失败: {e}")
            return False
    
    def remove_strategy_tags(self, strategy_id: str, tags: List[str]) -> bool:
        """从策略移除标签"""
        try:
            if strategy_id not in self._strategy_configs:
                logger.warning(f"策略 {strategy_id} 不存在")
                return False
            
            current_tags = self._strategy_configs[strategy_id].tags
            # 移除指定标签
            new_tags = [tag for tag in current_tags if tag not in tags]
            self._strategy_configs[strategy_id].metadata['tags'] = new_tags
            
            logger.info(f"从策略 {strategy_id} 移除标签: {tags}")
            return True
            
        except Exception as e:
            logger.error(f"移除策略标签失败: {e}")
            return False
    
    def get_strategies_by_tags(self, tags: List[str], match_all: bool = False) -> List[StrategyConfig]:
        """按标签获取策略
        
        Args:
            tags: 标签列表
            match_all: True表示匹配所有标签，False表示匹配任一标签
        """
        if match_all:
            # 匹配所有标签
            return [config for config in self._strategy_configs.values()
                    if all(tag in config.tags for tag in tags)]
        else:
            # 匹配任一标签
            return [config for config in self._strategy_configs.values()
                    if any(tag in config.tags for tag in tags)]
    
    def get_all_tags(self) -> List[str]:
        """获取所有使用过的标签"""
        all_tags = set()
        for config in self._strategy_configs.values():
            all_tags.update(config.tags)
        return sorted(list(all_tags))
    
    def get_tag_statistics(self) -> Dict[str, int]:
        """获取标签使用统计"""
        tag_stats = {}
        for config in self._strategy_configs.values():
            for tag in config.tags:
                if tag not in tag_stats:
                    tag_stats[tag] = 0
                tag_stats[tag] += 1
        return tag_stats
    
    def batch_update_strategy_group(self, strategy_ids: List[str], group_id: str) -> int:
        """批量更新策略分组"""
        try:
            if group_id not in self._strategy_groups:
                logger.warning(f"分组 {group_id} 不存在")
                return 0
            
            updated_count = 0
            for strategy_id in strategy_ids:
                if strategy_id in self._strategy_configs:
                    self._strategy_configs[strategy_id].metadata['group'] = group_id
                    updated_count += 1
            
            logger.info(f"批量更新 {updated_count} 个策略的分组为 {group_id}")
            return updated_count
            
        except Exception as e:
            logger.error(f"批量更新策略分组失败: {e}")
            return 0
    
    def batch_add_strategy_tags(self, strategy_ids: List[str], tags: List[str]) -> int:
        """批量为策略添加标签"""
        try:
            updated_count = 0
            for strategy_id in strategy_ids:
                if strategy_id in self._strategy_configs:
                    current_tags = self._strategy_configs[strategy_id].tags
                    new_tags = list(set(current_tags + tags))
                    self._strategy_configs[strategy_id].metadata['tags'] = new_tags
                    updated_count += 1
            
            logger.info(f"批量为 {updated_count} 个策略添加标签: {tags}")
            return updated_count
            
        except Exception as e:
            logger.error(f"批量添加策略标签失败: {e}")
            return 0

    def _do_dispose(self) -> None:
        """清理资源"""
        try:
            # 取消所有运行中的任务
            for task_id in list(self._running_backtests.keys()):
                self.cancel_backtest(task_id)

            for task_id in list(self._running_optimizations.keys()):
                self.cancel_optimization(task_id)

            # 停止插件清理定时器
            self._stop_plugin_cleanup_timer()

            # 清理插件实例
            for plugin_id, plugin_info in self._strategy_plugins.items():
                # 调用插件的销毁方法（如果有）
                if hasattr(plugin_info.plugin, 'destroy'):
                    try:
                        plugin_info.plugin.destroy()
                    except Exception as e:
                        logger.error(f"调用插件销毁方法失败 {plugin_id}: {e}")
                # 更新插件状态
                plugin_info.status = PluginStatus.DESTROYED
            self._strategy_plugins.clear()

            super()._do_dispose()
            logger.info("Strategy service disposed")

        except Exception as e:
            logger.error(f"Failed to dispose strategy service: {e}")

    def _start_plugin_cleanup_timer(self) -> None:
        """启动插件清理定时器"""
        def cleanup_timer_func():
            while True:
                try:
                    self._cleanup_idle_plugins()
                except Exception as e:
                    logger.error(f"插件清理定时器执行失败: {e}")
                finally:
                    # 等待指定的清理间隔
                    import time
                    time.sleep(self._plugin_cleanup_interval)
        
        # 创建并启动后台线程
        self._cleanup_timer = threading.Thread(target=cleanup_timer_func, daemon=True)
        self._cleanup_timer.start()
        logger.info(f"插件清理定时器已启动，清理间隔: {self._plugin_cleanup_interval}秒")

    def _stop_plugin_cleanup_timer(self) -> None:
        """停止插件清理定时器"""
        if self._cleanup_timer:
            # 守护线程会自动退出，无需手动停止
            logger.info("插件清理定时器已停止")

    def _update_plugin_last_used(self, plugin: IStrategyPlugin) -> None:
        """更新插件的最后使用时间"""
        try:
            current_time = datetime.now()
            # 遍历查找对应的PluginInfo对象
            for plugin_id, plugin_info in self._strategy_plugins.items():
                if plugin_info.plugin is plugin:
                    plugin_info.last_used_at = current_time
                    plugin_info.usage_count += 1
                    # 更新插件状态为IDLE
                    if plugin_info.status != PluginStatus.RUNNING:
                        plugin_info.status = PluginStatus.IDLE
                    break
        except Exception as e:
            logger.error(f"更新插件最后使用时间失败: {e}")
    
    def _cleanup_idle_plugins(self) -> None:
        """清理空闲的插件实例"""
        try:
            current_time = datetime.now()
            plugins_to_remove = []
            
            logger.debug(f"开始清理空闲插件，当前插件数量: {len(self._strategy_plugins)}")
            
            # 遍历所有插件，检查是否需要清理
            for plugin_id, plugin_info in self._strategy_plugins.items():
                if plugin_info.status == PluginStatus.RUNNING:
                    continue
                    
                # 检查是否超过空闲超时
                if plugin_info.last_used_at:
                    idle_time = current_time - plugin_info.last_used_at
                    if idle_time.total_seconds() > self._plugin_idle_timeout:
                        plugins_to_remove.append(plugin_id)
                        logger.debug(f"插件 {plugin_id} 已空闲 {idle_time.total_seconds():.2f}秒，超过阈值 {self._plugin_idle_timeout}秒，将被清理")
            
            # 清理超时的插件
            for plugin_id in plugins_to_remove:
                plugin_info = self._strategy_plugins[plugin_id]
                logger.info(f"清理空闲插件: {plugin_id}，状态: {plugin_info.status.value}，创建时间: {plugin_info.created_at}，最后使用时间: {plugin_info.last_used_at}")
                
                # 调用插件的销毁方法（如果有）
                if hasattr(plugin_info.plugin, 'destroy'):
                    try:
                        plugin_info.plugin.destroy()
                    except Exception as e:
                        logger.error(f"调用插件销毁方法失败 {plugin_id}: {e}")
                
                # 更新插件状态并从字典中移除
                plugin_info.status = PluginStatus.DESTROYED
                del self._strategy_plugins[plugin_id]
            
            if plugins_to_remove:
                logger.info(f"已清理 {len(plugins_to_remove)} 个空闲插件，剩余插件数量: {len(self._strategy_plugins)}")
            else:
                logger.debug("没有需要清理的空闲插件")
            
            # 同时清理实例池中的过期实例
            self._cleanup_instance_pool()
                
        except Exception as e:
            logger.error(f"清理空闲插件失败: {e}")
