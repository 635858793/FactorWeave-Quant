#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UI状态同步器

实现UI状态与业务逻辑状态的双向同步，提供：
- 事件驱动的状态更新机制
- 状态变更的防抖和节流
- 状态冲突检测和解决
- 状态持久化和恢复

作者: FactorWeave-Quant团队
版本: 1.0
"""

import threading
import json
from typing import Dict, List, Any, Optional, Callable, Set, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
from collections import defaultdict, deque

from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QMutex, QMutexLocker
from PyQt5.QtWidgets import QApplication

# 导入事件系统
from loguru import logger
try:
    from core.events.event_bus import EventBus, get_event_bus, Event
    EVENT_BUS_AVAILABLE = True
except ImportError as e:
    EVENT_BUS_AVAILABLE = False
    logger.warning(f"事件总线不可用: {e}")

logger = logger.bind(module=__name__)

class StateChangeType(Enum):
    """状态变更类型"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SYNC = "sync"

class StateSyncDirection(Enum):
    """状态同步方向"""
    UI_TO_BUSINESS = "ui_to_business"
    BUSINESS_TO_UI = "business_to_ui"
    BIDIRECTIONAL = "bidirectional"

class StateConflictResolution(Enum):
    """状态冲突解决策略"""
    UI_WINS = "ui_wins"
    BUSINESS_WINS = "business_wins"
    MERGE = "merge"
    USER_DECIDE = "user_decide"

@dataclass
class StateChange:
    """状态变更记录"""
    id: str
    entity_type: str
    entity_id: str
    change_type: StateChangeType
    old_value: Any
    new_value: Any
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StateConflict:
    """状态冲突"""
    entity_type: str
    entity_id: str
    ui_value: Any
    business_value: Any
    ui_timestamp: datetime
    business_timestamp: datetime
    conflict_fields: List[str] = field(default_factory=list)

@dataclass
class SyncConfiguration:
    """同步配置"""
    entity_type: str
    sync_direction: StateSyncDirection = StateSyncDirection.BIDIRECTIONAL
    conflict_resolution: StateConflictResolution = StateConflictResolution.BUSINESS_WINS
    debounce_ms: int = 300  # 防抖延迟（毫秒）
    throttle_ms: int = 100  # 节流间隔（毫秒）
    enable_persistence: bool = True
    sync_fields: Optional[Set[str]] = None  # 需要同步的字段，None表示全部
    ignore_fields: Set[str] = field(default_factory=set)  # 忽略的字段

class StateProvider(ABC):
    """状态提供者抽象基类"""

    @abstractmethod
    def get_state(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """获取状态"""
        pass

    @abstractmethod
    def set_state(self, entity_type: str, entity_id: str, state: Dict[str, Any]) -> bool:
        """设置状态"""
        pass

    @abstractmethod
    def delete_state(self, entity_type: str, entity_id: str) -> bool:
        """删除状态"""
        pass

    @abstractmethod
    def list_entities(self, entity_type: str) -> List[str]:
        """列出实体ID"""
        pass

class UIStateProvider(StateProvider):
    """UI状态提供者"""

    def __init__(self):
        self._states: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self._lock = threading.RLock()

    def get_state(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._states[entity_type].get(entity_id)

    def set_state(self, entity_type: str, entity_id: str, state: Dict[str, Any]) -> bool:
        with self._lock:
            self._states[entity_type][entity_id] = state.copy()
            return True

    def delete_state(self, entity_type: str, entity_id: str) -> bool:
        with self._lock:
            if entity_id in self._states[entity_type]:
                del self._states[entity_type][entity_id]
                return True
            return False

    def list_entities(self, entity_type: str) -> List[str]:
        with self._lock:
            return list(self._states[entity_type].keys())

class BusinessStateProvider(StateProvider):
    """业务逻辑状态提供者"""

    def __init__(self, adapter):
        self.adapter = adapter
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self._cache_duration = timedelta(seconds=30)

    def get_state(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        cache_key = f"{entity_type}:{entity_id}"
        current_time = datetime.now()

        # 检查缓存
        if cache_key in self._cache:
            expiry_time = self._cache_expiry.get(cache_key)
            if expiry_time and current_time < expiry_time:
                return self._cache[cache_key]

        # 从业务逻辑获取状态
        try:
            state = None
            if entity_type == 'task' and hasattr(self.adapter, 'get_task_details'):
                state = self.adapter.get_task_details(entity_id)
            elif entity_type == 'import_engine' and hasattr(self.adapter, 'get_import_engine_status'):
                state = self.adapter.get_import_engine_status()
            elif entity_type == 'ai_status' and hasattr(self.adapter, '_fetch_ai_status'):
                # 这里需要根据实际的业务逻辑API调整
                pass

            if state:
                self._cache[cache_key] = state
                self._cache_expiry[cache_key] = current_time + self._cache_duration

            return state
        except Exception as e:
            logger.error(f"获取业务状态失败 ({entity_type}:{entity_id}): {e}")
            return None

    def set_state(self, entity_type: str, entity_id: str, state: Dict[str, Any]) -> bool:
        # 业务逻辑状态通常通过特定的API设置
        try:
            if entity_type == 'task':
                # 更新任务状态
                if 'status' in state and hasattr(self.adapter, 'update_task_status'):
                    return self.adapter.update_task_status(entity_id, state['status'])
            elif entity_type == 'config':
                # 更新配置
                if hasattr(self.adapter, 'update_config'):
                    return self.adapter.update_config(entity_id, state)

            return False
        except Exception as e:
            logger.error(f"设置业务状态失败 ({entity_type}:{entity_id}): {e}")
            return False

    def delete_state(self, entity_type: str, entity_id: str) -> bool:
        try:
            if entity_type == 'task' and hasattr(self.adapter, 'cancel_import_task'):
                return self.adapter.cancel_import_task(entity_id)
            return False
        except Exception as e:
            logger.error(f"删除业务状态失败 ({entity_type}:{entity_id}): {e}")
            return False

    def list_entities(self, entity_type: str) -> List[str]:
        # 从业务逻辑获取实体列表
        try:
            if entity_type == 'task' and hasattr(self.adapter, 'get_all_tasks'):
                tasks = self.adapter.get_all_tasks()
                return [task.get('id', '') for task in tasks if task.get('id')]
            return []
        except Exception as e:
            logger.error(f"列出实体失败 ({entity_type}): {e}")
            return []

class UIStateSynchronizer(QObject):
    """UI状态同步器"""

    # 信号定义
    state_changed = pyqtSignal(str, str, object)  # entity_type, entity_id, new_state
    conflict_detected = pyqtSignal(object)  # StateConflict
    sync_completed = pyqtSignal(str, str)  # entity_type, entity_id
    sync_failed = pyqtSignal(str, str, str)  # entity_type, entity_id, error_message

    def __init__(self, ui_adapter=None, parent=None):
        super().__init__(parent)

        # 状态提供者
        self.ui_provider = UIStateProvider()
        self.business_provider = BusinessStateProvider(ui_adapter) if ui_adapter else None

        # 同步配置
        self.sync_configs: Dict[str, SyncConfiguration] = {}
        self.default_config = SyncConfiguration(entity_type="default")

        # 状态管理
        self._lock = QMutex()
        self._change_history: deque = deque(maxlen=1000)
        self._pending_syncs: Dict[str, QTimer] = {}
        self._sync_in_progress: Set[str] = set()

        # 事件总线
        self.event_bus = get_event_bus() if EVENT_BUS_AVAILABLE else None

        # 冲突处理
        self._conflicts: List[StateConflict] = []
        self._conflict_handlers: Dict[str, Callable] = {}

        # 初始化
        self._setup_default_configs()
        self._setup_event_handlers()

        logger.info("UI状态同步器初始化完成")

    def _setup_default_configs(self):
        """设置默认同步配置"""
        # 任务状态同步配置
        self.register_sync_config(SyncConfiguration(
            entity_type="task",
            sync_direction=StateSyncDirection.BIDIRECTIONAL,
            conflict_resolution=StateConflictResolution.BUSINESS_WINS,
            debounce_ms=500,
            ignore_fields={'internal_id', 'created_at'}
        ))

        # AI状态同步配置
        self.register_sync_config(SyncConfiguration(
            entity_type="ai_status",
            sync_direction=StateSyncDirection.BUSINESS_TO_UI,
            conflict_resolution=StateConflictResolution.BUSINESS_WINS,
            debounce_ms=1000
        ))

        # 性能指标同步配置
        self.register_sync_config(SyncConfiguration(
            entity_type="performance",
            sync_direction=StateSyncDirection.BUSINESS_TO_UI,
            conflict_resolution=StateConflictResolution.BUSINESS_WINS,
            debounce_ms=200
        ))

        # 配置同步配置
        self.register_sync_config(SyncConfiguration(
            entity_type="config",
            sync_direction=StateSyncDirection.BIDIRECTIONAL,
            conflict_resolution=StateConflictResolution.UI_WINS,
            debounce_ms=1000
        ))

    def _setup_event_handlers(self):
        """设置事件处理器"""
        if self.event_bus:
            # 监听业务逻辑事件 (R243-A-001 修复 2026-08-04)
            # Why: 原订阅名 (task.status_changed/ai.status_updated/performance.metrics_updated)
            #      在项目中无任何发布方, 真实发布方分别为:
            #      training.task.status_changed (model_training_service.py:575)
            #      ai_selection.completed       (ai_selection_integration_service.py:688)
            #      performance.metrics_collected (performance_service.py:267)
            #      -> 3 个订阅永远收不到事件, UI 状态同步静默失效
            # Fix: 订阅名与真实发布方对齐
            self.event_bus.subscribe('training.task.status_changed', self._on_business_task_changed)
            self.event_bus.subscribe('ai_selection.completed', self._on_business_ai_changed)
            self.event_bus.subscribe('performance.metrics_collected', self._on_business_performance_changed)

    def register_sync_config(self, config: SyncConfiguration):
        """注册同步配置"""
        self.sync_configs[config.entity_type] = config
        logger.debug(f"注册同步配置: {config.entity_type}")

    def get_sync_config(self, entity_type: str) -> SyncConfiguration:
        """获取同步配置"""
        return self.sync_configs.get(entity_type, self.default_config)

    def update_ui_state(self, entity_type: str, entity_id: str, state: Dict[str, Any],
                        source: str = "ui") -> bool:
        """更新UI状态"""
        try:
            with QMutexLocker(self._lock):
                # 获取旧状态
                old_state = self.ui_provider.get_state(entity_type, entity_id)

                # 更新UI状态
                success = self.ui_provider.set_state(entity_type, entity_id, state)

                if success:
                    # 记录变更
                    change = StateChange(
                        id=f"{entity_type}:{entity_id}:{datetime.now().timestamp()}",
                        entity_type=entity_type,
                        entity_id=entity_id,
                        change_type=StateChangeType.UPDATE if old_state else StateChangeType.CREATE,
                        old_value=old_state,
                        new_value=state,
                        source=source
                    )
                    self._change_history.append(change)

                    # 发射信号
                    self.state_changed.emit(entity_type, entity_id, state)

                    # 触发同步到业务逻辑
                    self._schedule_sync_to_business(entity_type, entity_id)

                return success

        except Exception as e:
            logger.error(f"更新UI状态失败: {e}")
            return False

    def _schedule_sync_to_business(self, entity_type: str, entity_id: str):
        """调度同步到业务逻辑"""
        config = self.get_sync_config(entity_type)

        # 检查同步方向
        if config.sync_direction not in [StateSyncDirection.UI_TO_BUSINESS, StateSyncDirection.BIDIRECTIONAL]:
            return

        sync_key = f"{entity_type}:{entity_id}"

        # 取消之前的同步任务（防抖）
        if sync_key in self._pending_syncs:
            self._pending_syncs[sync_key].stop()

        # 创建新的同步任务
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._sync_to_business(entity_type, entity_id))
        timer.start(config.debounce_ms)

        self._pending_syncs[sync_key] = timer

    def _sync_to_business(self, entity_type: str, entity_id: str):
        """同步到业务逻辑"""
        sync_key = f"{entity_type}:{entity_id}"

        try:
            # 检查是否正在同步
            if sync_key in self._sync_in_progress:
                return

            self._sync_in_progress.add(sync_key)

            # 获取UI状态
            ui_state = self.ui_provider.get_state(entity_type, entity_id)
            if not ui_state:
                return

            # 获取业务状态
            business_state = None
            if self.business_provider:
                business_state = self.business_provider.get_state(entity_type, entity_id)

            # 检测冲突
            if business_state:
                conflict = self._detect_conflict(entity_type, entity_id, ui_state, business_state)
                if conflict:
                    self._handle_conflict(conflict)
                    return

            # 执行同步
            if self.business_provider:
                success = self.business_provider.set_state(entity_type, entity_id, ui_state)
                if success:
                    self.sync_completed.emit(entity_type, entity_id)
                    logger.debug(f"同步到业务逻辑成功: {entity_type}:{entity_id}")
                else:
                    self.sync_failed.emit(entity_type, entity_id, "业务逻辑更新失败")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"同步到业务逻辑失败: {error_msg}")
            self.sync_failed.emit(entity_type, entity_id, error_msg)
        finally:
            self._sync_in_progress.discard(sync_key)
            # 清理定时器
            if sync_key in self._pending_syncs:
                del self._pending_syncs[sync_key]

    def _extract_event_data(self, event: Event) -> Dict[str, Any]:
        """从事件对象提取数据字典 (R243-A-001 修复 2026-08-04)

        Why: EventBus.publish(str, **kwargs) 生成动态属性对象 (event_bus.py:477-485),
             旧 handler 直接读 event.data -> AttributeError, 被 except 吞掉后同步静默失效
        Fix: 优先取 event.data (dict 形式), 否则取对象动态属性
        """
        data = getattr(event, 'data', None)
        if isinstance(data, dict):
            return data
        result = dict(getattr(event, '__dict__', None) or {})
        # P2-1 (2026-08-04): 过滤 EventBus 内部附加键, 避免混入业务状态
        result.pop('event_type', None)
        result.pop('priority', None)
        return result

    def _on_business_task_changed(self, event: Event):
        """处理业务任务变更事件 (R243-A-001: 适配 training.task.status_changed)"""
        try:
            task_data = self._extract_event_data(event)
            entity_id = task_data.get('task_id') or task_data.get('id')
            if entity_id:
                self._sync_from_business('task', entity_id, task_data)
        except Exception as e:
            logger.error(f"处理业务任务变更事件失败: {e}")

    def _on_business_ai_changed(self, event: Event):
        """处理业务AI选股变更事件 (R243-A-001: 适配 ai_selection.completed)"""
        try:
            ai_data = self._extract_event_data(event)
            self._sync_from_business('ai_status', 'global', ai_data)
        except Exception as e:
            logger.error(f"处理业务AI变更事件失败: {e}")

    def _on_business_performance_changed(self, event: Event):
        """处理业务性能指标变更事件 (R243-A-001: 适配 performance.metrics_collected)"""
        try:
            perf_data = self._extract_event_data(event)
            self._sync_from_business('performance', 'global', perf_data)
        except Exception as e:
            logger.error(f"处理业务性能变更事件失败: {e}")

    def _sync_from_business(self, entity_type: str, entity_id: str, business_state: Dict[str, Any]):
        """从业务逻辑同步"""
        config = self.get_sync_config(entity_type)

        # 检查同步方向
        if config.sync_direction not in [StateSyncDirection.BUSINESS_TO_UI, StateSyncDirection.BIDIRECTIONAL]:
            return

        try:
            # 获取UI状态
            ui_state = self.ui_provider.get_state(entity_type, entity_id)

            # 检测冲突
            if ui_state:
                conflict = self._detect_conflict(entity_type, entity_id, ui_state, business_state)
                if conflict:
                    self._handle_conflict(conflict)
                    return

            # 更新UI状态
            success = self.ui_provider.set_state(entity_type, entity_id, business_state)
            if success:
                self.state_changed.emit(entity_type, entity_id, business_state)
                logger.debug(f"从业务逻辑同步成功: {entity_type}:{entity_id}")

        except Exception as e:
            logger.error(f"从业务逻辑同步失败: {e}")

    def _detect_conflict(self, entity_type: str, entity_id: str,
                         ui_state: Dict[str, Any], business_state: Dict[str, Any]) -> Optional[StateConflict]:
        """检测状态冲突"""
        try:
            config = self.get_sync_config(entity_type)
            conflict_fields = []

            # 比较状态字段
            all_fields = set(ui_state.keys()) | set(business_state.keys())

            for field in all_fields:
                # 跳过忽略的字段
                if field in config.ignore_fields:
                    continue

                # 检查同步字段限制
                if config.sync_fields and field not in config.sync_fields:
                    continue

                ui_value = ui_state.get(field)
                business_value = business_state.get(field)

                # 比较值
                if ui_value != business_value:
                    conflict_fields.append(field)

            # 如果有冲突字段，创建冲突对象
            if conflict_fields:
                return StateConflict(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    ui_value=ui_state,
                    business_value=business_state,
                    ui_timestamp=datetime.now(),  # 实际应该从状态中获取
                    business_timestamp=datetime.now(),  # 实际应该从状态中获取
                    conflict_fields=conflict_fields
                )

            return None

        except Exception as e:
            logger.error(f"检测状态冲突失败: {e}")
            return None

    def _handle_conflict(self, conflict: StateConflict):
        """处理状态冲突"""
        try:
            config = self.get_sync_config(conflict.entity_type)
            resolution = config.conflict_resolution

            if resolution == StateConflictResolution.UI_WINS:
                # UI状态获胜
                if self.business_provider:
                    self.business_provider.set_state(
                        conflict.entity_type, conflict.entity_id, conflict.ui_value)

            elif resolution == StateConflictResolution.BUSINESS_WINS:
                # 业务逻辑状态获胜
                self.ui_provider.set_state(
                    conflict.entity_type, conflict.entity_id, conflict.business_value)
                self.state_changed.emit(conflict.entity_type, conflict.entity_id, conflict.business_value)

            elif resolution == StateConflictResolution.MERGE:
                # 合并状态
                merged_state = self._merge_states(conflict.ui_value, conflict.business_value)
                self.ui_provider.set_state(conflict.entity_type, conflict.entity_id, merged_state)
                if self.business_provider:
                    self.business_provider.set_state(conflict.entity_type, conflict.entity_id, merged_state)
                self.state_changed.emit(conflict.entity_type, conflict.entity_id, merged_state)

            elif resolution == StateConflictResolution.USER_DECIDE:
                # 用户决定
                self._conflicts.append(conflict)
                self.conflict_detected.emit(conflict)

            logger.debug(f"处理状态冲突: {conflict.entity_type}:{conflict.entity_id} -> {resolution.value}")

        except Exception as e:
            logger.error(f"处理状态冲突失败: {e}")

    def _merge_states(self, ui_state: Dict[str, Any], business_state: Dict[str, Any]) -> Dict[str, Any]:
        """合并状态"""
        # 简单的合并策略：业务状态为基础，UI状态覆盖
        merged = business_state.copy()
        merged.update(ui_state)
        return merged

    def resolve_conflict(self, conflict: StateConflict, resolution: StateConflictResolution):
        """手动解决冲突"""
        try:
            # 从冲突列表中移除
            if conflict in self._conflicts:
                self._conflicts.remove(conflict)

            # 应用解决方案
            if resolution == StateConflictResolution.UI_WINS:
                if self.business_provider:
                    self.business_provider.set_state(
                        conflict.entity_type, conflict.entity_id, conflict.ui_value)
            elif resolution == StateConflictResolution.BUSINESS_WINS:
                self.ui_provider.set_state(
                    conflict.entity_type, conflict.entity_id, conflict.business_value)
                self.state_changed.emit(conflict.entity_type, conflict.entity_id, conflict.business_value)

            logger.info(f"手动解决冲突: {conflict.entity_type}:{conflict.entity_id}")

        except Exception as e:
            logger.error(f"手动解决冲突失败: {e}")

    def get_pending_conflicts(self) -> List[StateConflict]:
        """获取待处理的冲突"""
        return self._conflicts.copy()

    def force_sync(self, entity_type: str, entity_id: str, direction: StateSyncDirection):
        """强制同步"""
        try:
            if direction == StateSyncDirection.UI_TO_BUSINESS:
                self._sync_to_business(entity_type, entity_id)
            elif direction == StateSyncDirection.BUSINESS_TO_UI:
                if self.business_provider:
                    business_state = self.business_provider.get_state(entity_type, entity_id)
                    if business_state:
                        self._sync_from_business(entity_type, entity_id, business_state)

        except Exception as e:
            logger.error(f"强制同步失败: {e}")

    def get_change_history(self, entity_type: Optional[str] = None,
                           entity_id: Optional[str] = None) -> List[StateChange]:
        """获取变更历史"""
        history = list(self._change_history)

        if entity_type:
            history = [change for change in history if change.entity_type == entity_type]

        if entity_id:
            history = [change for change in history if change.entity_id == entity_id]

        return history

    def clear_history(self):
        """清除变更历史"""
        self._change_history.clear()

    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return {
            'pending_syncs': len(self._pending_syncs),
            'syncs_in_progress': len(self._sync_in_progress),
            'pending_conflicts': len(self._conflicts),
            'change_history_size': len(self._change_history),
            'registered_configs': list(self.sync_configs.keys())
        }

# 全局同步器实例
_synchronizer_instance: Optional[UIStateSynchronizer] = None

def get_ui_synchronizer(ui_adapter=None) -> UIStateSynchronizer:
    """获取UI同步器实例（单例模式）"""
    global _synchronizer_instance

    if _synchronizer_instance is None:
        _synchronizer_instance = UIStateSynchronizer(ui_adapter)

    return _synchronizer_instance

def initialize_ui_synchronizer(ui_adapter) -> UIStateSynchronizer:
    """初始化UI同步器"""
    synchronizer = get_ui_synchronizer(ui_adapter)
    return synchronizer
