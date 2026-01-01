"""
插件数据库服务

专业级插件状态管理服务，提供：
- 插件状态持久化
- 实时状态同步
- 性能监控数据收集
- 远程管理API支持
"""

from loguru import logger
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

# 延迟导入 Qt 相关模块，避免在没有 QApplication 时导入失败
_QtObject = None
_pyqtSignal = None

def _get_qt_classes():
    """延迟获取 Qt 类"""
    global _QtObject, _pyqtSignal
    if _QtObject is None:
        try:
            from PyQt5.QtCore import QObject, pyqtSignal
            _QtObject = QObject
            _pyqtSignal = pyqtSignal
        except ImportError:
            raise ImportError("PyQt5 未安装")
    return _QtObject, _pyqtSignal

# 导入插件数据库模型
from db.models.plugin_models import (
    PluginDatabaseManager, PluginRecord, PluginStatus, PluginType
)


class PluginDatabaseService:
    """插件数据库服务 - 延迟初始化 Qt 相关组件"""

    def __init__(self, db_path: str = None):
        """初始化插件数据库服务"""
        # 延迟初始化 Qt 相关组件
        try:
            QObject, pyqtSignal = _get_qt_classes()
            
            # 动态添加信号
            self.plugin_status_changed = pyqtSignal(str, str, str)  # 插件名, 旧状态, 新状态
            self.plugin_registered = pyqtSignal(str, dict)  # 插件名, 插件信息
            self.database_updated = pyqtSignal()  # 数据库更新
        except Exception as e:
            logger.warning(f"无法初始化 Qt 信号: {e}")
            # 创建占位符
            self.plugin_status_changed = None
            self.plugin_registered = None
            self.database_updated = None

        # 设置数据库路径
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'factorweave_system.sqlite')

        self.db_path = os.path.abspath(db_path)
        self.db_manager = PluginDatabaseManager(self.db_path)

        # 缓存：减少数据库查询
        self._status_cache: Dict[str, PluginStatus] = {}
        self._plugins_cache: List[Dict[str, Any]] = []
        self._cache_timestamp = 0
        self._cache_ttl = 60  # 缓存60秒

        logger.info(f"插件数据库服务初始化完成: {self.db_path}")

    def register_plugin_from_metadata(self, plugin_name: str, metadata: Dict[str, Any]) -> bool:
        """从插件元数据注册插件"""
        try:
            # 如果已存在，保留原有状态
            existing_status = self.db_manager.get_plugin_status(plugin_name)
            status_value = (existing_status.value if existing_status else PluginStatus.UNLOADED.value)

            # 构建插件记录
            plugin_record = PluginRecord(
                name=plugin_name,
                display_name=metadata.get('display_name', plugin_name),
                version=metadata.get('version', '1.0.0'),
                plugin_type=metadata.get('plugin_type', PluginType.ANALYSIS.value),
                status=status_value,
                description=metadata.get('description', ''),
                author=metadata.get('author', ''),
                email=metadata.get('email', ''),
                homepage=metadata.get('homepage', ''),
                repository=metadata.get('repository', ''),
                license=metadata.get('license', 'MIT'),
                tags=str(metadata.get('tags', [])),  # JSON string
                install_path=metadata.get('path', ''),
                entry_point=metadata.get('entry_point', ''),
                config_schema=str(metadata.get('config_schema', {})),
                dependencies=str(metadata.get('dependencies', [])),
                compatibility=str(metadata.get('compatibility', {})),
                install_size=metadata.get('install_size', 0),
                checksum=metadata.get('checksum', ''),
                remote_url=metadata.get('remote_url', ''),
                auto_update=metadata.get('auto_update', False),
                priority=metadata.get('priority', 100)
            )

            # 注册到数据库
            plugin_id = self.db_manager.register_plugin(plugin_record)

            # 更新缓存
            self._invalidate_cache()

            # 发射信号
            self.plugin_registered.emit(plugin_name, metadata)

            logger.info(f"插件注册成功: {plugin_name} (ID: {plugin_id})")
            return True

        except Exception as e:
            logger.error(f"注册插件失败: {plugin_name}, 错误: {e}")
            return False

    def update_plugin_status(self, plugin_name: str, new_status: PluginStatus,
                             reason: str = "", error_message: str = "") -> bool:
        """更新插件状态"""
        try:
            # 获取旧状态
            old_status = self.get_plugin_status(plugin_name)
            old_status_str = old_status.value if old_status else "unknown"

            # 更新数据库
            success = self.db_manager.update_plugin_status(
                plugin_name, new_status, reason, error_message
            )

            if success:
                # 更新缓存
                self._status_cache[plugin_name] = new_status
                self._invalidate_cache()

                # 发射状态变更信号
                self.plugin_status_changed.emit(plugin_name, old_status_str, new_status.value)

                logger.info(f"插件状态更新: {plugin_name} {old_status_str} -> {new_status.value}")
                return True

            return False

        except Exception as e:
            logger.error(f"更新插件状态失败: {plugin_name}, 错误: {e}")
            return False

    def get_plugin_status(self, plugin_name: str) -> Optional[PluginStatus]:
        """获取插件状态（优先从缓存）"""
        try:
            # 检查缓存
            if plugin_name in self._status_cache:
                return self._status_cache[plugin_name]

            # 从数据库查询
            status = self.db_manager.get_plugin_status(plugin_name)

            # 更新缓存
            if status:
                self._status_cache[plugin_name] = status

            return status

        except Exception as e:
            logger.error(f"获取插件状态失败: {plugin_name}, 错误: {e}")
            return None

    def get_all_plugins(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """获取所有插件信息（带缓存）"""
        try:
            current_time = datetime.now().timestamp()

            # 检查缓存是否有效
            if (not force_refresh and
                self._plugins_cache and
                    current_time - self._cache_timestamp < self._cache_ttl):
                return self._plugins_cache

            # 从数据库获取
            plugin_records = self.db_manager.get_all_plugins()

            # 将PluginRecord对象转换为字典
            plugins = []
            for record in plugin_records:
                plugin_dict = {
                    'id': record.id,
                    'name': record.name,
                    'display_name': record.display_name,
                    'version': record.version,
                    'plugin_type': record.plugin_type,
                    'status': record.status,
                    'description': record.description,
                    'author': record.author,
                    'email': record.email,
                    'homepage': record.homepage,
                    'repository': record.repository,
                    'license': record.license,
                    'tags': record.tags,
                    'install_path': record.install_path,
                    'entry_point': record.entry_point,
                    'config_schema': record.config_schema,
                    'dependencies': record.dependencies,
                    'compatibility': record.compatibility,
                    'created_at': record.created_at,
                    'updated_at': record.updated_at,
                    'last_enabled_at': record.last_enabled_at,
                    'install_size': record.install_size,
                    'checksum': record.checksum,
                    'remote_url': record.remote_url,
                    'auto_update': record.auto_update,
                    'priority': record.priority
                }
                plugins.append(plugin_dict)

            # 更新缓存
            self._plugins_cache = plugins
            self._cache_timestamp = current_time

            # 更新状态缓存
            for plugin in plugins:
                self._status_cache[plugin['name']] = PluginStatus(plugin['status'])

            return plugins

        except Exception as e:
            logger.error(f"获取所有插件信息失败: {e}")
            return []

    def get_plugins_by_status(self, status: PluginStatus) -> List[Dict[str, Any]]:
        """根据状态获取插件列表"""
        try:
            return self.db_manager.get_plugins_by_status(status)
        except Exception as e:
            logger.error(f"根据状态获取插件失败: {e}")
            return []

    def get_status_statistics(self) -> Dict[str, int]:
        """获取状态统计信息"""
        try:
            statistics = {}
            for status in PluginStatus:
                plugins = self.get_plugins_by_status(status)
                statistics[status.value] = len(plugins)

            # 计算总数
            statistics['total'] = sum(statistics.values())

            return statistics

        except Exception as e:
            logger.error(f"获取状态统计失败: {e}")
            return {}

    def record_performance_metric(self, plugin_name: str, metric_name: str,
                                  metric_value: float, metric_unit: str = "",
                                  additional_data: Dict[str, Any] = None) -> bool:
        """记录插件性能指标"""
        try:
            return self.db_manager.record_plugin_performance(
                plugin_name, metric_name, metric_value, metric_unit, additional_data
            )
        except Exception as e:
            logger.error(f"记录性能指标失败: {e}")
            return False

    def get_performance_metrics(self, plugin_name: str, metric_name: str = None,
                                limit: int = 100) -> List[Dict[str, Any]]:
        """获取插件性能指标"""
        try:
            return self.db_manager.get_plugin_performance_metrics(
                plugin_name, metric_name, limit
            )
        except Exception as e:
            logger.error(f"获取性能指标失败: {e}")
            return []

    def sync_plugin_statuses(self, plugin_manager) -> Dict[str, bool]:
        """同步插件状态到数据库 - 增强版本，确保数据库与真实插件状态一致"""
        try:
            sync_results = {}

            # 第一步：获取所有真实存在的插件
            real_plugins = {}
            if hasattr(plugin_manager, 'get_all_plugin_metadata'):
                real_plugins = plugin_manager.get_all_plugin_metadata()
                logger.info(f"发现 {len(real_plugins)} 个真实插件")

            # 第二步：获取数据库中所有插件记录
            db_plugins = self.get_all_plugins()
            db_plugin_names = set(plugin['name'] for plugin in db_plugins)
            logger.info(f"数据库中有 {len(db_plugin_names)} 个插件记录")

            # 第三步：处理真实存在但数据库不存在的插件 - 添加到数据库，默认禁用
            real_plugin_names = set(real_plugins.keys())
            new_plugins = real_plugin_names - db_plugin_names

            for plugin_name in new_plugins:
                try:
                    metadata = real_plugins[plugin_name]
                    # 注册插件到数据库，默认状态为DISABLED（禁用）
                    success = self.register_plugin_from_metadata(plugin_name, metadata)
                    if success:
                        # 设置为禁用状态
                        self.update_plugin_status(plugin_name, PluginStatus.DISABLED, "新发现插件，默认禁用")
                        sync_results[plugin_name] = True
                        logger.info(f"新插件已添加到数据库: {plugin_name} (状态: 禁用)")
                    else:
                        sync_results[plugin_name] = False
                        logger.error(f"添加新插件到数据库失败: {plugin_name}")
                except Exception as e:
                    logger.error(f"处理新插件失败: {plugin_name}, 错误: {e}")
                    sync_results[plugin_name] = False

            # 第四步：处理数据库存在但真实不存在的插件 - 从数据库删除
            orphan_plugins = db_plugin_names - real_plugin_names

            for plugin_name in orphan_plugins:
                try:
                    success = self.remove_plugin(plugin_name)
                    if success:
                        sync_results[plugin_name] = True
                        logger.info(f"已删除不存在的插件记录: {plugin_name}")
                    else:
                        sync_results[plugin_name] = False
                        logger.error(f"删除插件记录失败: {plugin_name}")
                except Exception as e:
                    logger.error(f"删除孤立插件记录失败: {plugin_name}, 错误: {e}")
                    sync_results[plugin_name] = False

            # 第五步：更新现有插件的状态（只更新运行时状态，不改变用户设置的启用/禁用状态）
            existing_plugins = real_plugin_names & db_plugin_names

            for plugin_name in existing_plugins:
                try:
                    # 获取数据库中的当前状态
                    current_db_status = self.get_plugin_status(plugin_name)

                    # 如果是用户设置的启用/禁用状态，只更新运行时状态
                    if current_db_status in [PluginStatus.ENABLED, PluginStatus.DISABLED]:
                        # 检查运行时状态是否与期望一致
                        actual_runtime_status = self._determine_actual_status(plugin_name, plugin_manager)

                        # 根据数据库状态决定期望的运行时状态
                        if current_db_status == PluginStatus.ENABLED:
                            # 插件应该是启用的，检查是否真的在运行
                            if actual_runtime_status not in [PluginStatus.ENABLED, PluginStatus.LOADED]:
                                # 需要启动插件
                                logger.info(f"插件 {plugin_name} 应该启用但未运行，尝试启用")
                        elif current_db_status == PluginStatus.DISABLED:
                            # 插件应该是禁用的，检查是否真的已停止
                            if actual_runtime_status in [PluginStatus.ENABLED, PluginStatus.LOADED]:
                                # 需要停止插件
                                logger.info(f"插件 {plugin_name} 应该禁用但在运行，尝试禁用")
                    else:
                        # 对于其他状态（如LOADED、UNLOADED、ERROR），更新为实际状态
                        actual_status = self._determine_actual_status(plugin_name, plugin_manager)
                        self.update_plugin_status(plugin_name, actual_status, "状态同步")

                    sync_results[plugin_name] = True

                except Exception as e:
                    logger.error(f"同步现有插件状态失败: {plugin_name}, 错误: {e}")
                    sync_results[plugin_name] = False

            logger.info(f"插件状态同步完成: 新增 {len(new_plugins)} 个，删除 {len(orphan_plugins)} 个，更新 {len(existing_plugins)} 个")
            return sync_results

        except Exception as e:
            logger.error(f"同步插件状态失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}

    def _determine_actual_status(self, plugin_name: str, plugin_manager) -> PluginStatus:
        """确定插件的实际状态"""
        try:
            # 检查插件是否在实例中
            if hasattr(plugin_manager, 'plugin_instances') and plugin_name in plugin_manager.plugin_instances:
                # 检查是否启用
                if hasattr(plugin_manager, 'enhanced_plugins') and plugin_name in plugin_manager.enhanced_plugins:
                    enhanced_plugin = plugin_manager.enhanced_plugins[plugin_name]
                    return enhanced_plugin.status
                else:
                    return PluginStatus.LOADED

            # 检查是否已加载
            elif hasattr(plugin_manager, 'loaded_plugins') and plugin_name in plugin_manager.loaded_plugins:
                return PluginStatus.LOADED

            # 默认为未加载
            else:
                return PluginStatus.UNLOADED

        except Exception as e:
            logger.error(f"确定插件状态失败: {plugin_name}, 错误: {e}")
            return PluginStatus.ERROR

    def remove_plugin(self, plugin_name: str) -> bool:
        """
        从数据库中删除插件记录

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否删除成功
        """
        try:
            success = self.db_manager.delete_plugin(plugin_name)
            if success:
                # 清除缓存中的相关记录
                self._status_cache.pop(plugin_name, None)
                self._invalidate_cache()
                logger.info(f"插件记录已删除: {plugin_name}")
                self.database_updated.emit()
            return success
        except Exception as e:
            logger.error(f"删除插件记录失败: {plugin_name}, 错误: {e}")
            return False

    def _invalidate_cache(self):
        """使缓存失效"""
        self._cache_timestamp = 0

    def export_plugin_data(self, format: str = "json") -> Optional[str]:
        """导出插件数据"""
        try:
            plugins = self.get_all_plugins(force_refresh=True)

            if format.lower() == "json":
                import json
                return json.dumps(plugins, ensure_ascii=False, indent=2)
            elif format.lower() == "csv":
                import csv
                import io

                output = io.StringIO()
                if plugins:
                    writer = csv.DictWriter(output, fieldnames=plugins[0].keys())
                    writer.writeheader()
                    writer.writerows(plugins)

                return output.getvalue()

            return None

        except Exception as e:
            logger.error(f"导出插件数据失败: {e}")
            return None

    def cleanup_old_data(self, days: int = 30) -> bool:
        """清理旧数据"""
        try:
            return self.db_manager.cleanup_old_records(days)
        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")
            return False

    def get_remote_management_data(self) -> Dict[str, Any]:
        """获取远程管理数据"""
        try:
            return {
                'plugins': self.get_all_plugins(),
                'statistics': self.get_status_statistics(),
                'timestamp': datetime.now().isoformat(),
                'version': '2.0.1'
            }
        except Exception as e:
            logger.error(f"获取远程管理数据失败: {e}")
            return {}

    def save_plugin_config_json(self, plugin_name: str, config: Dict[str, Any], config_type: str = 'user') -> bool:
        try:
            ok = self.db_manager.save_unified_plugin_config(plugin_name, config, config_type=config_type)
            if ok:
                self.database_updated.emit()
            return ok
        except Exception as e:
            logger.error(f"保存插件配置失败: {plugin_name}, 错误: {e}")
            return False

    def get_plugin_config_json(self, plugin_name: str, config_type: str = 'user') -> Optional[Dict[str, Any]]:
        try:
            return self.db_manager.load_unified_plugin_config(plugin_name, config_type=config_type)
        except Exception as e:
            logger.error(f"读取插件配置失败: {plugin_name}, 错误: {e}")
            return None

# 全局服务实例
_plugin_db_service = None

def get_plugin_database_service(db_path: str = None) -> PluginDatabaseService:
    """获取插件数据库服务单例"""
    global _plugin_db_service

    if _plugin_db_service is None:
        _plugin_db_service = PluginDatabaseService(db_path)

    return _plugin_db_service
