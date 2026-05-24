"""
策略热重载管理器

提供策略的动态加载、卸载和重载功能，支持不重启系统的情况下更新策略
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import importlib
import sys
import threading
from pathlib import Path
from datetime import datetime

class ReloadStatus(Enum):
    """重载状态"""
    IDLE = "idle"
    LOADING = "loading"
    RELOADING = "reloading"
    UNLOADING = "unloading"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class ReloadResult:
    """重载结果"""
    strategy_name: str
    status: ReloadStatus
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[Exception] = None


@dataclass
class StrategyReloadInfo:
    """策略重载信息"""
    strategy_name: str
    module_path: str
    class_name: str
    version: str = "1.0.0"
    loaded_at: Optional[datetime] = None
    reloaded_count: int = 0
    is_active: bool = False


class StrategyHotReloader:
    """策略热重载器"""
    
    def __init__(self):
        self._strategies: Dict[str, StrategyReloadInfo] = {}
        self._reload_history: List[ReloadResult] = []
        self._reload_listeners: List[Callable[[ReloadResult], None]] = []
        self._lock = threading.RLock()
        self._status = ReloadStatus.IDLE
        
        logger.info("策略热重载器初始化完成")
    
    def register_strategy(self, strategy_name: str, module_path: str, 
                      class_name: str, version: str = "1.0.0"):
        """注册策略
        
        Args:
            strategy_name: 策略名称
            module_path: 模块路径
            class_name: 类名
            version: 策略版本
        """
        with self._lock:
            info = StrategyReloadInfo(
                strategy_name=strategy_name,
                module_path=module_path,
                class_name=class_name,
                version=version,
                loaded_at=datetime.now(),
                reloaded_count=0,
                is_active=False
            )
            self._strategies[strategy_name] = info
            logger.info(f"注册策略: {strategy_name} v{version}")
    
    def unregister_strategy(self, strategy_name: str):
        """取消注册策略
        
        Args:
            strategy_name: 策略名称
        """
        with self._lock:
            if strategy_name in self._strategies:
                del self._strategies[strategy_name]
                logger.info(f"取消注册策略: {strategy_name}")
    
    def reload_strategy(self, strategy_name: str) -> ReloadResult:
        """重载单个策略
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            ReloadResult: 重载结果
        """
        with self._lock:
            if strategy_name not in self._strategies:
                return ReloadResult(
                    strategy_name=strategy_name,
                    status=ReloadStatus.FAILED,
                    message=f"策略 {strategy_name} 未注册"
                )
            
            info = self._strategies[strategy_name]
            self._status = ReloadStatus.RELOADING
        
        try:
            logger.info(f"开始重载策略: {strategy_name}")
            
            step1_result = self._unload_strategy(strategy_name)
            if step1_result.status != ReloadStatus.SUCCESS:
                return step1_result
            
            step2_result = self._load_strategy(strategy_name)
            if step2_result.status != ReloadStatus.SUCCESS:
                return step2_result
            
            with self._lock:
                info = self._strategies[strategy_name]
                info.reloaded_count += 1
                info.loaded_at = datetime.now()
            
            result = ReloadResult(
                strategy_name=strategy_name,
                status=ReloadStatus.SUCCESS,
                message=f"策略 {strategy_name} 重载成功",
                timestamp=datetime.now()
            )
            
            logger.info(f"策略重载成功: {strategy_name}")
            self._notify_listeners(result)
            self._reload_history.append(result)
            return result
            
        except Exception as e:
            logger.error(f"策略重载失败: {strategy_name}, 错误: {str(e)}")
            result = ReloadResult(
                strategy_name=strategy_name,
                status=ReloadStatus.FAILED,
                message=f"策略 {strategy_name} 重载失败: {str(e)}",
                error=e,
                timestamp=datetime.now()
            )
            self._notify_listeners(result)
            self._reload_history.append(result)
            return result
        finally:
            with self._lock:
                self._status = ReloadStatus.IDLE
    
    def _unload_strategy(self, strategy_name: str) -> ReloadResult:
        """卸载策略
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            ReloadResult: 卸载结果
        """
        try:
            info = self._strategies[strategy_name]
            module_name = info.module_path.replace('/', '.').replace('\\', '.')
            
            if module_name in sys.modules:
                del sys.modules[module_name]
                logger.debug(f"卸载模块: {module_name}")
            
            return ReloadResult(
                strategy_name=strategy_name,
                status=ReloadStatus.SUCCESS,
                message=f"策略 {strategy_name} 卸载成功"
            )
        except Exception as e:
            logger.error(f"策略卸载失败: {strategy_name}, 错误: {str(e)}")
            return ReloadResult(
                strategy_name=strategy_name,
                status=ReloadStatus.FAILED,
                message=f"策略 {strategy_name} 卸载失败: {str(e)}",
                error=e
            )
    
    def _load_strategy(self, strategy_name: str) -> ReloadResult:
        """加载策略
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            ReloadResult: 加载结果
        """
        try:
            info = self._strategies[strategy_name]
            module_path = info.module_path
            
            module = importlib.import_module(module_path)
            strategy_class = getattr(module, info.class_name)
            
            logger.debug(f"加载策略类: {info.class_name}")
            
            return ReloadResult(
                strategy_name=strategy_name,
                status=ReloadStatus.SUCCESS,
                message=f"策略 {strategy_name} 加载成功"
            )
        except Exception as e:
            logger.error(f"策略加载失败: {strategy_name}, 错误: {str(e)}")
            return ReloadResult(
                strategy_name=strategy_name,
                status=ReloadStatus.FAILED,
                message=f"策略 {strategy_name} 加载失败: {str(e)}",
                error=e
            )
    
    def reload_all_strategies(self) -> List[ReloadResult]:
        """重载所有策略
        
        Returns:
            List[ReloadResult]: 重载结果列表
        """
        results = []
        strategy_names = list(self._strategies.keys())
        
        logger.info(f"开始重载所有策略: {len(strategy_names)} 个")
        
        for strategy_name in strategy_names:
            result = self.reload_strategy(strategy_name)
            results.append(result)
        
        success_count = sum(1 for r in results if r.status == ReloadStatus.SUCCESS)
        logger.info(f"重载完成: 成功 {success_count}/{len(results)}")
        
        return results
    
    def reload_strategies_by_pattern(self, pattern: str) -> List[ReloadResult]:
        """按模式重载策略
        
        Args:
            pattern: 策略名称模式（支持通配符 *）
            
        Returns:
            List[ReloadResult]: 重载结果列表
        """
        import fnmatch
        
        matched_strategies = [
            name for name in self._strategies.keys()
            if fnmatch.fnmatch(name, pattern)
        ]
        
        logger.info(f"按模式重载策略: {pattern}, 匹配 {len(matched_strategies)} 个")
        
        results = []
        for strategy_name in matched_strategies:
            result = self.reload_strategy(strategy_name)
            results.append(result)
        
        return results
    
    def add_reload_listener(self, listener: Callable[[ReloadResult], None]):
        """添加重载监听器
        
        Args:
            listener: 重载监听器函数
        """
        with self._lock:
            self._reload_listeners.append(listener)
            logger.debug(f"添加重载监听器: {listener.__name__}")
    
    def remove_reload_listener(self, listener: Callable[[ReloadResult], None]):
        """移除重载监听器
        
        Args:
            listener: 重载监听器函数
        """
        with self._lock:
            if listener in self._reload_listeners:
                self._reload_listeners.remove(listener)
                logger.debug(f"移除重载监听器: {listener.__name__}")
    
    def _notify_listeners(self, result: ReloadResult):
        """通知所有监听器
        
        Args:
            result: 重载结果
        """
        for listener in self._reload_listeners:
            try:
                listener(result)
            except Exception as e:
                logger.error(f"重载监听器执行失败: {str(e)}")
    
    def get_strategy_info(self, strategy_name: str) -> Optional[StrategyReloadInfo]:
        """获取策略重载信息
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            Optional[StrategyReloadInfo]: 策略重载信息，如果不存在则返回None
        """
        return self._strategies.get(strategy_name)
    
    def get_all_strategies(self) -> List[str]:
        """获取所有注册的策略名称"""
        return list(self._strategies.keys())
    
    def get_reload_history(self, limit: int = 100) -> List[ReloadResult]:
        """获取重载历史
        
        Args:
            limit: 返回的最大历史记录数
            
        Returns:
            List[ReloadResult]: 重载历史记录
        """
        return self._reload_history[-limit:]
    
    def get_status(self) -> ReloadStatus:
        """获取当前状态"""
        return self._status
    
    def clear_history(self):
        """清空重载历史"""
        with self._lock:
            self._reload_history.clear()
            logger.info("重载历史已清空")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            Dict[str, Any]: 统计信息字典
        """
        with self._lock:
            total_reloads = sum(info.reloaded_count for info in self._strategies.values())
            success_reloads = sum(
                1 for result in self._reload_history
                if result.status == ReloadStatus.SUCCESS
            )
            failed_reloads = sum(
                1 for result in self._reload_history
                if result.status == ReloadStatus.FAILED
            )
            
            return {
                "total_strategies": len(self._strategies),
                "total_reloads": total_reloads,
                "success_reloads": success_reloads,
                "failed_reloads": failed_reloads,
                "current_status": self._status.value,
                "reload_history_size": len(self._reload_history)
            }


def get_strategy_hot_reloader() -> StrategyHotReloader:
    """获取策略热重载器单例"""
    if not hasattr(get_strategy_hot_reloader, '_instance'):
        get_strategy_hot_reloader._instance = StrategyHotReloader()
    return get_strategy_hot_reloader._instance
