"""
插件版本管理器

提供插件的版本控制、升级检查、版本回滚和冲突解决功能
"""

from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from loguru import logger
import json
from pathlib import Path
import re

class VersionComparison(Enum):
    """版本比较结果"""
    OLDER = "older"
    EQUAL = "equal"
    NEWER = "newer"
    INCOMPATIBLE = "incompatible"


@dataclass
class PluginVersion:
    """插件版本信息"""
    plugin_name: str
    version: str
    release_date: Optional[datetime] = None
    changelog: List[str] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)
    file_path: Optional[str] = None
    is_compatible: bool = True
    
    def __post_init__(self):
        if not self.is_valid_version(self.version):
            logger.warning(f"无效的版本格式: {self.version}")
    
    @staticmethod
    def is_valid_version(version: str) -> bool:
        """验证版本格式
        
        Args:
            version: 版本字符串
            
        Returns:
            bool: 是否有效
        """
        pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z]+\.\d+)?$'
        return bool(re.match(pattern, version))
    
    def compare_version(self, other_version: str) -> VersionComparison:
        """比较版本
        
        Args:
            other_version: 其他版本字符串
            
        Returns:
            VersionComparison: 比较结果
        """
        if not self.is_valid_version(self.version) or not self.is_valid_version(other_version):
            return VersionComparison.INCOMPATIBLE
        
        v1_parts = self._parse_version(self.version)
        v2_parts = self._parse_version(other_version)
        
        for i in range(min(len(v1_parts), len(v2_parts))):
            if v1_parts[i] > v2_parts[i]:
                return VersionComparison.NEWER
            elif v1_parts[i] < v2_parts[i]:
                return VersionComparison.OLDER
        
        if len(v1_parts) > len(v2_parts):
            return VersionComparison.NEWER
        elif len(v1_parts) < len(v2_parts):
            return VersionComparison.OLDER
        
        return VersionComparison.EQUAL
    
    def _parse_version(self, version: str) -> List[int]:
        """解析版本字符串
        
        Args:
            version: 版本字符串
            
        Returns:
            List[int]: 版本号列表
        """
        parts = []
        for part in version.split('.'):
            if part.isdigit():
                parts.append(int(part))
            elif '-' in part:
                main_part = part.split('-')[0]
                if main_part.isdigit():
                    parts.append(int(main_part))
        return parts
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "plugin_name": self.plugin_name,
            "version": self.version,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "changelog": self.changelog,
            "dependencies": self.dependencies,
            "file_path": self.file_path,
            "is_compatible": self.is_compatible
        }


@dataclass
class VersionConflict:
    """版本冲突"""
    plugin_name: str
    conflict_type: str
    conflicting_plugin: str
    required_version: str
    installed_version: str
    description: str = ""


class PluginVersionManager:
    """插件版本管理器"""
    
    def __init__(self, storage_dir: Path = None):
        self._versions: Dict[str, PluginVersion] = {}
        self._version_history: Dict[str, List[PluginVersion]] = {}
        self._conflicts: List[VersionConflict] = []
        self._lock = object()
        
        self._storage_dir = storage_dir or Path(__file__).parent / ".plugin_versions"
        self._storage_dir.mkdir(exist_ok=True)
        
        self._load_versions_from_storage()
        logger.info("插件版本管理器初始化完成")
    
    def register_version(self, version: PluginVersion):
        """注册插件版本
        
        Args:
            version: 插件版本信息
        """
        with self._lock:
            plugin_name = version.plugin_name
            
            if plugin_name in self._versions:
                old_version = self._versions[plugin_name]
                comparison = version.compare_version(old_version.version)
                
                if comparison == VersionComparison.NEWER:
                    self._add_to_history(plugin_name, old_version)
                    logger.info(f"插件 {plugin_name} 升级: {old_version.version} -> {version.version}")
                elif comparison == VersionComparison.OLDER:
                    logger.warning(f"插件 {plugin_name} 降级: {old_version.version} -> {version.version}")
                else:
                    logger.info(f"插件 {plugin_name} 重新注册: {version.version}")
            else:
                logger.info(f"注册新插件: {plugin_name} v{version.version}")
            
            self._versions[plugin_name] = version
            self._check_conflicts(plugin_name)
            self._save_versions_to_storage()
    
    def unregister_plugin(self, plugin_name: str):
        """取消注册插件
        
        Args:
            plugin_name: 插件名称
        """
        with self._lock:
            if plugin_name in self._versions:
                del self._versions[plugin_name]
                logger.info(f"取消注册插件: {plugin_name}")
                
                self._conflicts = [
                    c for c in self._conflicts
                    if c.plugin_name != plugin_name and c.conflicting_plugin != plugin_name
                ]
                
                self._save_versions_to_storage()
    
    def get_version(self, plugin_name: str) -> Optional[PluginVersion]:
        """获取插件版本
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            Optional[PluginVersion]: 插件版本信息，如果不存在则返回None
        """
        return self._versions.get(plugin_name)
    
    def get_all_versions(self) -> Dict[str, PluginVersion]:
        """获取所有插件版本"""
        return dict(self._versions)
    
    def check_update(self, plugin_name: str, available_version: str) -> Tuple[bool, str]:
        """检查插件更新
        
        Args:
            plugin_name: 插件名称
            available_version: 可用版本
            
        Returns:
            Tuple[bool, str]: (是否有更新, 消息)
        """
        current_version = self.get_version(plugin_name)
        if not current_version:
            return False, f"插件 {plugin_name} 未安装"
        
        comparison = current_version.compare_version(available_version)
        
        if comparison == VersionComparison.NEWER:
            return False, f"插件 {plugin_name} 已是最新版本: {current_version.version}"
        elif comparison == VersionComparison.OLDER:
            return True, f"插件 {plugin_name} 有可用更新: {current_version.version} -> {available_version}"
        elif comparison == VersionComparison.EQUAL:
            return False, f"插件 {plugin_name} 已是最新版本: {current_version.version}"
        else:
            return False, f"插件 {plugin_name} 版本不兼容"
    
    def check_all_updates(self, available_versions: Dict[str, str]) -> Dict[str, Tuple[bool, str]]:
        """检查所有插件更新
        
        Args:
            available_versions: 可用版本字典 {插件名: 版本}
            
        Returns:
            Dict[str, Tuple[bool, str]]: 更新检查结果
        """
        results = {}
        
        for plugin_name, available_version in available_versions.items():
            results[plugin_name] = self.check_update(plugin_name, available_version)
        
        return results
    
    def rollback_version(self, plugin_name: str, target_version: str = None) -> Tuple[bool, str]:
        """回滚插件版本
        
        Args:
            plugin_name: 插件名称
            target_version: 目标版本，如果为None则回滚到上一个版本
            
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        with self._lock:
            if plugin_name not in self._version_history:
                return False, f"插件 {plugin_name} 没有版本历史"
            
            history = self._version_history[plugin_name]
            
            if target_version:
                for version in reversed(history):
                    if version.version == target_version:
                        self._versions[plugin_name] = version
                        self._save_versions_to_storage()
                        return True, f"插件 {plugin_name} 已回滚到版本 {target_version}"
                
                return False, f"插件 {plugin_name} 未找到版本 {target_version}"
            else:
                if len(history) < 2:
                    return False, f"插件 {plugin_name} 没有可回滚的版本"
                
                previous_version = history[-2]
                self._versions[plugin_name] = previous_version
                self._save_versions_to_storage()
                return True, f"插件 {plugin_name} 已回滚到版本 {previous_version.version}"
    
    def get_version_history(self, plugin_name: str) -> List[PluginVersion]:
        """获取插件版本历史
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            List[PluginVersion]: 版本历史列表
        """
        return self._version_history.get(plugin_name, [])
    
    def get_conflicts(self) -> List[VersionConflict]:
        """获取所有版本冲突"""
        return list(self._conflicts)
    
    def resolve_conflict(self, conflict: VersionConflict) -> Tuple[bool, str]:
        """解决版本冲突
        
        Args:
            conflict: 版本冲突
            
        Returns:
            Tuple[bool, str]: (是否解决, 消息)
        """
        logger.info(f"尝试解决冲突: {conflict.plugin_name} vs {conflict.conflicting_plugin}")
        
        if conflict.conflict_type == "version_mismatch":
            return self._resolve_version_mismatch(conflict)
        elif conflict.conflict_type == "dependency_conflict":
            return self._resolve_dependency_conflict(conflict)
        else:
            return False, f"未知冲突类型: {conflict.conflict_type}"
    
    def _resolve_version_mismatch(self, conflict: VersionConflict) -> Tuple[bool, str]:
        """解决版本不匹配冲突"""
        plugin_version = self.get_version(conflict.plugin_name)
        
        if not plugin_version:
            return False, f"插件 {conflict.plugin_name} 未安装"
        
        comparison = plugin_version.compare_version(conflict.required_version)
        
        if comparison == VersionComparison.NEWER or comparison == VersionComparison.EQUAL:
            return True, f"版本兼容: {plugin_version.version} >= {conflict.required_version}"
        else:
            return False, f"版本不兼容: {plugin_version.version} < {conflict.required_version}"
    
    def _resolve_dependency_conflict(self, conflict: VersionConflict) -> Tuple[bool, str]:
        """解决依赖冲突"""
        plugin_version = self.get_version(conflict.plugin_name)
        
        if not plugin_version:
            return False, f"插件 {conflict.plugin_name} 未安装"
        
        conflicting_version = self.get_version(conflict.conflicting_plugin)
        
        if not conflicting_version:
            return False, f"插件 {conflict.conflicting_plugin} 未安装"
        
        return True, f"依赖冲突已记录，需要手动解决"
    
    def _check_conflicts(self, plugin_name: str):
        """检查插件冲突
        
        Args:
            plugin_name: 插件名称
        """
        if plugin_name not in self._versions:
            return
        
        version = self._versions[plugin_name]
        
        for dep_name, required_version in version.dependencies.items():
            if dep_name in self._versions:
                dep_version = self._versions[dep_name]
                comparison = dep_version.compare_version(required_version)
                
                if comparison == VersionComparison.OLDER:
                    conflict = VersionConflict(
                        plugin_name=plugin_name,
                        conflict_type="version_mismatch",
                        conflicting_plugin=dep_name,
                        required_version=required_version,
                        installed_version=dep_version.version,
                        description=f"插件 {plugin_name} 需要 {dep_name} v{required_version}，但已安装 v{dep_version.version}"
                    )
                    if conflict not in self._conflicts:
                        self._conflicts.append(conflict)
                        logger.warning(f"检测到版本冲突: {conflict.description}")
    
    def _add_to_history(self, plugin_name: str, version: PluginVersion):
        """添加到版本历史
        
        Args:
            plugin_name: 插件名称
            version: 版本信息
        """
        if plugin_name not in self._version_history:
            self._version_history[plugin_name] = []
        
        self._version_history[plugin_name].append(version)
        
        max_history = 10
        if len(self._version_history[plugin_name]) > max_history:
            self._version_history[plugin_name] = self._version_history[plugin_name][-max_history:]
    
    def _load_versions_from_storage(self):
        """从存储加载版本信息"""
        try:
            storage_file = self._storage_dir / "versions.json"
            if storage_file.exists():
                with open(storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    for plugin_name, version_data in data.get('versions', {}).items():
                        version = PluginVersion(
                            plugin_name=plugin_name,
                            version=version_data.get('version', '1.0.0'),
                            release_date=datetime.fromisoformat(version_data['release_date']) if version_data.get('release_date') else None,
                            changelog=version_data.get('changelog', []),
                            dependencies=version_data.get('dependencies', {}),
                            file_path=version_data.get('file_path'),
                            is_compatible=version_data.get('is_compatible', True)
                        )
                        self._versions[plugin_name] = version
                    
                    for plugin_name, history_data in data.get('history', {}).items():
                        history = []
                        for version_data in history_data:
                            version = PluginVersion(
                                plugin_name=plugin_name,
                                version=version_data.get('version', '1.0.0'),
                                release_date=datetime.fromisoformat(version_data['release_date']) if version_data.get('release_date') else None,
                                changelog=version_data.get('changelog', []),
                                dependencies=version_data.get('dependencies', {}),
                                file_path=version_data.get('file_path'),
                                is_compatible=version_data.get('is_compatible', True)
                            )
                            history.append(version)
                        self._version_history[plugin_name] = history
                    
                    logger.info(f"从存储加载版本信息: {len(self._versions)} 个插件")
        except Exception as e:
            logger.error(f"加载版本信息失败: {str(e)}")
    
    def _save_versions_to_storage(self):
        """保存版本信息到存储"""
        try:
            storage_file = self._storage_dir / "versions.json"
            
            versions_data = {}
            for plugin_name, version in self._versions.items():
                versions_data[plugin_name] = version.to_dict()
            
            history_data = {}
            for plugin_name, history in self._version_history.items():
                history_data[plugin_name] = [v.to_dict() for v in history]
            
            data = {
                'versions': versions_data,
                'history': history_data,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug("版本信息已保存到存储")
        except Exception as e:
            logger.error(f"保存版本信息失败: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            Dict[str, Any]: 统计信息字典
        """
        with self._lock:
            total_plugins = len(self._versions)
            total_history = sum(len(history) for history in self._version_history.values())
            total_conflicts = len(self._conflicts)
            
            return {
                "total_plugins": total_plugins,
                "total_history_entries": total_history,
                "total_conflicts": total_conflicts,
                "storage_dir": str(self._storage_dir),
                "last_updated": datetime.now().isoformat()
            }
    
    def export_versions(self, file_path: Path):
        """导出版本信息
        
        Args:
            file_path: 导出文件路径
        """
        try:
            data = {
                'exported_at': datetime.now().isoformat(),
                'versions': {name: v.to_dict() for name, v in self._versions.items()},
                'history': {name: [v.to_dict() for v in history] for name, history in self._version_history.items()},
                'conflicts': [
                    {
                        'plugin_name': c.plugin_name,
                        'conflict_type': c.conflict_type,
                        'conflicting_plugin': c.conflicting_plugin,
                        'required_version': c.required_version,
                        'installed_version': c.installed_version,
                        'description': c.description
                    }
                    for c in self._conflicts
                ]
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"版本信息已导出到: {file_path}")
        except Exception as e:
            logger.error(f"导出版本信息失败: {str(e)}")
    
    def clear_history(self, plugin_name: str = None):
        """清空版本历史
        
        Args:
            plugin_name: 插件名称，如果为None则清空所有历史
        """
        with self._lock:
            if plugin_name:
                if plugin_name in self._version_history:
                    self._version_history[plugin_name].clear()
                    logger.info(f"清空插件 {plugin_name} 的版本历史")
            else:
                self._version_history.clear()
                logger.info("清空所有版本历史")
            
            self._save_versions_to_storage()


def get_plugin_version_manager(storage_dir: Path = None) -> PluginVersionManager:
    """获取插件版本管理器单例"""
    if not hasattr(get_plugin_version_manager, '_instance'):
        get_plugin_version_manager._instance = PluginVersionManager(storage_dir)
    return get_plugin_version_manager._instance
