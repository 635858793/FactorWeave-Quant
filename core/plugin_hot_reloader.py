"""
插件热重载管理器

提供插件的动态加载、卸载和重载功能，支持不重启系统的情况下更新插件
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
import importlib
import sys
import threading
from pathlib import Path
from datetime import datetime
import hashlib
import json

logger = logging.getLogger(__name__)


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
    plugin_name: str
    status: ReloadStatus
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[Exception] = None
    old_version: Optional[str] = None
    new_version: Optional[str] = None


@dataclass
class PluginReloadInfo:
    """插件重载信息"""
    plugin_name: str
    module_path: str
    class_name: str
    version: str = "1.0.0"
    loaded_at: Optional[datetime] = None
    reloaded_count: int = 0
    is_active: bool = False
    file_hash: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)


class PluginHotReloader:
    """插件热重载器"""
    
    def __init__(self):
        self._plugins: Dict[str, PluginReloadInfo] = {}
        self._reload_history: List[ReloadResult] = []
        self._reload_listeners: List[Callable[[ReloadResult], None]] = []
        self._lock = threading.RLock()
        self._status = ReloadStatus.IDLE
        self._backup_dir = Path(__file__).parent / ".plugin_backups"
        
        self._backup_dir.mkdir(exist_ok=True)
        logger.info("插件热重载器初始化完成")
    
    def register_plugin(self, plugin_name: str, module_path: str, 
                     class_name: str, version: str = "1.0.0",
                     dependencies: List[str] = None):
        """注册插件
        
        Args:
            plugin_name: 插件名称
            module_path: 模块路径
            class_name: 类名
            version: 插件版本
            dependencies: 依赖列表
        """
        with self._lock:
            file_path = Path(module_path.replace('.', '/')).with_suffix('.py')
            file_hash = self._calculate_file_hash(file_path) if file_path.exists() else None
            
            info = PluginReloadInfo(
                plugin_name=plugin_name,
                module_path=module_path,
                class_name=class_name,
                version=version,
                loaded_at=datetime.now(),
                reloaded_count=0,
                is_active=False,
                file_hash=file_hash,
                dependencies=dependencies or []
            )
            self._plugins[plugin_name] = info
            logger.info(f"注册插件: {plugin_name} v{version}")
    
    def unregister_plugin(self, plugin_name: str):
        """取消注册插件
        
        Args:
            plugin_name: 插件名称
        """
        with self._lock:
            if plugin_name in self._plugins:
                del self._plugins[plugin_name]
                logger.info(f"取消注册插件: {plugin_name}")
    
    def reload_plugin(self, plugin_name: str, force: bool = False) -> ReloadResult:
        """重载单个插件
        
        Args:
            plugin_name: 插件名称
            force: 是否强制重载（即使文件未变化）
            
        Returns:
            ReloadResult: 重载结果
        """
        with self._lock:
            if plugin_name not in self._plugins:
                return ReloadResult(
                    plugin_name=plugin_name,
                    status=ReloadStatus.FAILED,
                    message=f"插件 {plugin_name} 未注册"
                )
            
            info = self._plugins[plugin_name]
            self._status = ReloadStatus.RELOADING
        
        try:
            logger.info(f"开始重载插件: {plugin_name}")
            
            old_version = info.version
            old_hash = info.file_hash
            
            step1_result = self._check_file_changed(plugin_name)
            if not force and not step1_result:
                return ReloadResult(
                    plugin_name=plugin_name,
                    status=ReloadStatus.SUCCESS,
                    message=f"插件 {plugin_name} 文件未变化，跳过重载",
                    old_version=old_version,
                    new_version=old_version
                )
            
            step2_result = self._backup_plugin(plugin_name)
            if step2_result.status != ReloadStatus.SUCCESS:
                return step2_result
            
            step3_result = self._unload_plugin(plugin_name)
            if step3_result.status != ReloadStatus.SUCCESS:
                return step3_result
            
            step4_result = self._load_plugin(plugin_name)
            if step4_result.status != ReloadStatus.SUCCESS:
                return step4_result
            
            new_hash = self._plugins[plugin_name].file_hash
            
            with self._lock:
                info = self._plugins[plugin_name]
                info.reloaded_count += 1
                info.loaded_at = datetime.now()
                info.file_hash = new_hash
            
            result = ReloadResult(
                plugin_name=plugin_name,
                status=ReloadStatus.SUCCESS,
                message=f"插件 {plugin_name} 重载成功",
                old_version=old_version,
                new_version=info.version,
                timestamp=datetime.now()
            )
            
            logger.info(f"插件重载成功: {plugin_name}")
            self._notify_listeners(result)
            self._reload_history.append(result)
            return result
            
        except Exception as e:
            logger.error(f"插件重载失败: {plugin_name}, 错误: {str(e)}")
            result = ReloadResult(
                plugin_name=plugin_name,
                status=ReloadStatus.FAILED,
                message=f"插件 {plugin_name} 重载失败: {str(e)}",
                error=e,
                old_version=old_version,
                timestamp=datetime.now()
            )
            self._notify_listeners(result)
            self._reload_history.append(result)
            return result
        finally:
            with self._lock:
                self._status = ReloadStatus.IDLE
    
    def _check_file_changed(self, plugin_name: str) -> bool:
        """检查插件文件是否变化
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 文件是否变化
        """
        info = self._plugins[plugin_name]
        file_path = Path(info.module_path.replace('.', '/')).with_suffix('.py')
        
        if not file_path.exists():
            logger.warning(f"插件文件不存在: {file_path}")
            return False
        
        new_hash = self._calculate_file_hash(file_path)
        return new_hash != info.file_hash
    
    def _backup_plugin(self, plugin_name: str) -> ReloadResult:
        """备份插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            ReloadResult: 备份结果
        """
        try:
            info = self._plugins[plugin_name]
            file_path = Path(info.module_path.replace('.', '/')).with_suffix('.py')
            
            if not file_path.exists():
                return ReloadResult(
                    plugin_name=plugin_name,
                    status=ReloadStatus.SUCCESS,
                    message=f"插件文件不存在，跳过备份"
                )
            
            backup_path = self._backup_dir / f"{plugin_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
            backup_path.write_text(file_path.read_text(encoding='utf-8'), encoding='utf-8')
            
            logger.debug(f"插件备份成功: {plugin_name} -> {backup_path}")
            
            return ReloadResult(
                plugin_name=plugin_name,
                status=ReloadStatus.SUCCESS,
                message=f"插件 {plugin_name} 备份成功"
            )
        except Exception as e:
            logger.error(f"插件备份失败: {plugin_name}, 错误: {str(e)}")
            return ReloadResult(
                plugin_name=plugin_name,
                status=ReloadStatus.FAILED,
                message=f"插件 {plugin_name} 备份失败: {str(e)}",
                error=e
            )
    
    def _unload_plugin(self, plugin_name: str) -> ReloadResult:
        """卸载插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            ReloadResult: 卸载结果
        """
        try:
            info = self._plugins[plugin_name]
            module_name = info.module_path.replace('/', '.').replace('\\', '.')
            
            modules_to_remove = [module_name]
            for mod_name in list(sys.modules.keys()):
                if mod_name.startswith(module_name):
                    modules_to_remove.append(mod_name)
            
            for mod_name in modules_to_remove:
                if mod_name in sys.modules:
                    del sys.modules[mod_name]
                    logger.debug(f"卸载模块: {mod_name}")
            
            return ReloadResult(
                plugin_name=plugin_name,
                status=ReloadStatus.SUCCESS,
                message=f"插件 {plugin_name} 卸载成功"
            )
        except Exception as e:
            logger.error(f"插件卸载失败: {plugin_name}, 错误: {str(e)}")
            return ReloadResult(
                plugin_name=plugin_name,
                status=ReloadStatus.FAILED,
                message=f"插件 {plugin_name} 卸载失败: {str(e)}",
                error=e
            )
    
    def _load_plugin(self, plugin_name: str) -> ReloadResult:
        """加载插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            ReloadResult: 加载结果
        """
        try:
            info = self._plugins[plugin_name]
            module_path = info.module_path
            
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, info.class_name)
            
            logger.debug(f"加载插件类: {info.class_name}")
            
            return ReloadResult(
                plugin_name=plugin_name,
                status=ReloadStatus.SUCCESS,
                message=f"插件 {plugin_name} 加载成功"
            )
        except Exception as e:
            logger.error(f"插件加载失败: {plugin_name}, 错误: {str(e)}")
            return ReloadResult(
                plugin_name=plugin_name,
                status=ReloadStatus.FAILED,
                message=f"插件 {plugin_name} 加载失败: {str(e)}",
                error=e
            )
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件哈希
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件哈希值
        """
        content = file_path.read_text(encoding='utf-8')
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def reload_all_plugins(self, force: bool = False) -> List[ReloadResult]:
        """重载所有插件
        
        Args:
            force: 是否强制重载所有插件
            
        Returns:
            List[ReloadResult]: 重载结果列表
        """
        results = []
        plugin_names = list(self._plugins.keys())
        
        logger.info(f"开始重载所有插件: {len(plugin_names)} 个")
        
        for plugin_name in plugin_names:
            result = self.reload_plugin(plugin_name, force=force)
            results.append(result)
        
        success_count = sum(1 for r in results if r.status == ReloadStatus.SUCCESS)
        logger.info(f"重载完成: 成功 {success_count}/{len(results)}")
        
        return results
    
    def reload_plugins_by_pattern(self, pattern: str, force: bool = False) -> List[ReloadResult]:
        """按模式重载插件
        
        Args:
            pattern: 插件名称模式（支持通配符 *）
            force: 是否强制重载
            
        Returns:
            List[ReloadResult]: 重载结果列表
        """
        import fnmatch
        
        matched_plugins = [
            name for name in self._plugins.keys()
            if fnmatch.fnmatch(name, pattern)
        ]
        
        logger.info(f"按模式重载插件: {pattern}, 匹配 {len(matched_plugins)} 个")
        
        results = []
        for plugin_name in matched_plugins:
            result = self.reload_plugin(plugin_name, force=force)
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
    
    def get_plugin_info(self, plugin_name: str) -> Optional[PluginReloadInfo]:
        """获取插件重载信息
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            Optional[PluginReloadInfo]: 插件重载信息，如果不存在则返回None
        """
        return self._plugins.get(plugin_name)
    
    def get_all_plugins(self) -> List[str]:
        """获取所有注册的插件名称"""
        return list(self._plugins.keys())
    
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
            total_reloads = sum(info.reloaded_count for info in self._plugins.values())
            success_reloads = sum(
                1 for result in self._reload_history
                if result.status == ReloadStatus.SUCCESS
            )
            failed_reloads = sum(
                1 for result in self._reload_history
                if result.status == ReloadStatus.FAILED
            )
            
            return {
                "total_plugins": len(self._plugins),
                "total_reloads": total_reloads,
                "success_reloads": success_reloads,
                "failed_reloads": failed_reloads,
                "current_status": self._status.value,
                "reload_history_size": len(self._reload_history),
                "backup_dir": str(self._backup_dir)
            }
    
    def rollback_plugin(self, plugin_name: str, backup_version: str = None) -> ReloadResult:
        """回滚插件到备份版本
        
        Args:
            plugin_name: 插件名称
            backup_version: 备份版本（时间戳），如果为None则回滚到最新备份
            
        Returns:
            ReloadResult: 回滚结果
        """
        try:
            backup_files = list(self._backup_dir.glob(f"{plugin_name}_*.py"))
            
            if not backup_files:
                return ReloadResult(
                    plugin_name=plugin_name,
                    status=ReloadStatus.FAILED,
                    message=f"插件 {plugin_name} 没有可用的备份"
                )
            
            if backup_version:
                backup_file = self._backup_dir / f"{plugin_name}_{backup_version}.py"
                if not backup_file.exists():
                    return ReloadResult(
                        plugin_name=plugin_name,
                        status=ReloadStatus.FAILED,
                        message=f"插件 {plugin_name} 备份 {backup_version} 不存在"
                    )
            else:
                backup_file = max(backup_files, key=lambda p: p.stat().st_mtime)
            
            info = self._plugins[plugin_name]
            file_path = Path(info.module_path.replace('.', '/')).with_suffix('.py')
            
            file_path.write_text(backup_file.read_text(encoding='utf-8'), encoding='utf-8')
            
            result = self.reload_plugin(plugin_name, force=True)
            
            if result.status == ReloadStatus.SUCCESS:
                result.message = f"插件 {plugin_name} 回滚成功"
            
            return result
            
        except Exception as e:
            logger.error(f"插件回滚失败: {plugin_name}, 错误: {str(e)}")
            return ReloadResult(
                plugin_name=plugin_name,
                status=ReloadStatus.FAILED,
                message=f"插件 {plugin_name} 回滚失败: {str(e)}",
                error=e
            )


def get_plugin_hot_reloader() -> PluginHotReloader:
    """获取插件热重载器单例"""
    if not hasattr(get_plugin_hot_reloader, '_instance'):
        get_plugin_hot_reloader._instance = PluginHotReloader()
    return get_plugin_hot_reloader._instance
