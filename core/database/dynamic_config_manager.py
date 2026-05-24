from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDB动态配置管理器

实现DuckDB配置的动态应用和实时生效
"""

import threading
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from pathlib import Path

from db.models.duckdb_config_models import (
    DuckDBConfigManager, DuckDBConfigProfile, get_duckdb_config_manager
)
from core.database.duckdb_performance_optimizer import (
    DuckDBPerformanceOptimizer, WorkloadType
)



class DynamicConfigManager:
    """DuckDB动态配置管理器"""

    def __init__(self):
        self.config_manager = get_duckdb_config_manager()
        self.active_connections = {}  # 存储活动的DuckDB连接
        self.config_listeners = []    # 配置变更监听器
        self.current_config = None    # 当前活动配置
        self._lock = threading.Lock()

        # 加载当前活动配置
        self._load_active_config()

    def _load_active_config(self):
        """加载当前活动配置"""
        try:
            active_profile = self.config_manager.get_active_profile()
            if active_profile:
                self.current_config = active_profile
                logger.info(f"加载活动配置: {active_profile.profile_name}")
            else:
                # 如果没有活动配置，使用默认配置
                default_profile = self.config_manager.get_default_profile()
                if default_profile:
                    self.current_config = default_profile
                    # 激活默认配置
                    self.config_manager.activate_profile(default_profile.id, "system")
                    logger.info(f"激活默认配置: {default_profile.profile_name}")
                else:
                    logger.warning("没有找到活动或默认配置")

        except Exception as e:
            logger.error(f"加载活动配置失败: {e}")

    def register_connection(self, connection_id: str, db_path: str,
                            connection_factory: Callable = None) -> bool:
        """注册DuckDB连接"""
        try:
            with self._lock:
                if connection_id in self.active_connections:
                    logger.warning(f"连接已存在: {connection_id}")
                    return False

                # 创建连接信息
                connection_info = {
                    'connection_id': connection_id,
                    'db_path': db_path,
                    'connection_factory': connection_factory,
                    'optimizer': None,
                    'connection': None,
                    'last_config_applied': None,
                    'created_at': datetime.now(),
                    'status': 'registered'
                }

                self.active_connections[connection_id] = connection_info

                # 如果有当前配置，立即应用
                if self.current_config:
                    self._apply_config_to_connection(connection_id, self.current_config)

                logger.info(f"注册DuckDB连接: {connection_id} -> {db_path}")
                return True

        except Exception as e:
            logger.error(f"注册连接失败: {e}")
            return False

    def unregister_connection(self, connection_id: str) -> bool:
        """注销DuckDB连接"""
        try:
            with self._lock:
                if connection_id not in self.active_connections:
                    logger.warning(f"连接不存在: {connection_id}")
                    return False

                connection_info = self.active_connections[connection_id]

                # 关闭优化器和连接
                if connection_info.get('optimizer'):
                    try:
                        connection_info['optimizer'].close()
                    except Exception as e:
                        logger.warning(f"关闭优化器失败: {e}")

                if connection_info.get('connection'):
                    try:
                        connection_info['connection'].close()
                    except Exception as e:
                        logger.warning(f"关闭连接失败: {e}")

                # 移除连接
                del self.active_connections[connection_id]

                logger.info(f"注销DuckDB连接: {connection_id}")
                return True

        except Exception as e:
            logger.error(f"注销连接失败: {e}")
            return False

    def apply_config_profile(self, profile_id: int, applied_by: str = "system") -> bool:
        """应用配置配置文件到所有连接"""
        try:
            # 获取配置配置文件
            profile = self.config_manager.get_profile(profile_id)
            if not profile:
                logger.error(f"配置配置文件不存在: {profile_id}")
                return False

            # 激活配置
            success = self.config_manager.activate_profile(profile_id, applied_by)
            if not success:
                logger.error(f"激活配置失败: {profile_id}")
                return False

            # 更新当前配置
            self.current_config = profile

            # 应用到所有连接
            applied_count = 0
            failed_connections = []

            with self._lock:
                for connection_id in list(self.active_connections.keys()):
                    try:
                        if self._apply_config_to_connection(connection_id, profile):
                            applied_count += 1
                        else:
                            failed_connections.append(connection_id)
                    except Exception as e:
                        logger.error(f"应用配置到连接 {connection_id} 失败: {e}")
                        failed_connections.append(connection_id)

            # 通知监听器
            self._notify_config_changed(profile, applied_by)

            logger.info(f"配置应用完成: {profile.profile_name}, 成功: {applied_count}, 失败: {len(failed_connections)}")

            if failed_connections:
                logger.warning(f"配置应用失败的连接: {failed_connections}")

            return len(failed_connections) == 0

        except Exception as e:
            logger.error(f"应用配置配置文件失败: {e}")
            return False

    def _apply_config_to_connection(self, connection_id: str, profile: DuckDBConfigProfile) -> bool:
        """应用配置到指定连接"""
        try:
            connection_info = self.active_connections.get(connection_id)
            if not connection_info:
                logger.error(f"连接不存在: {connection_id}")
                return False

            # 关闭现有优化器和连接
            if connection_info.get('optimizer'):
                try:
                    connection_info['optimizer'].close()
                except Exception:
                    pass

            # 创建新的优化器
            optimizer = DuckDBPerformanceOptimizer(connection_info['db_path'])

            # 应用工作负载优化
            workload_type = getattr(WorkloadType, profile.workload_type, WorkloadType.OLAP)
            success = optimizer.optimize_for_workload(workload_type)

            if not success:
                logger.error(f"工作负载优化失败: {connection_id}")
                return False

            # 获取连接
            connection = optimizer.get_connection()

            # 应用详细配置
            self._apply_detailed_config(connection, profile)

            # 更新连接信息
            connection_info['optimizer'] = optimizer
            connection_info['connection'] = connection
            connection_info['last_config_applied'] = profile.to_dict()
            connection_info['status'] = 'configured'

            logger.info(f"配置应用成功: {connection_id} -> {profile.profile_name}")
            return True

        except Exception as e:
            logger.error(f"应用配置到连接失败 {connection_id}: {e}")
            return False

    def _apply_detailed_config(self, connection, profile: DuckDBConfigProfile):
        """应用详细配置参数"""
        try:
            # 构建配置命令列表
            config_commands = []

            # 内存配置
            if profile.memory_limit:
                config_commands.append(f"SET memory_limit = '{profile.memory_limit}'")
            if profile.max_memory:
                config_commands.append(f"SET max_memory = '{profile.max_memory}'")

            # 线程配置
            config_commands.append(f"SET threads = {profile.threads}")

            # 查询配置
            config_commands.append(f"SET enable_progress_bar = {str(profile.enable_progress_bar).lower()}")
            config_commands.append(f"SET enable_object_cache = {str(profile.enable_object_cache).lower()}")
            config_commands.append(f"SET preserve_insertion_order = {str(profile.preserve_insertion_order).lower()}")

            # 应用配置
            applied_count = 0
            for cmd in config_commands:
                try:
                    connection.execute(cmd)
                    applied_count += 1
                    logger.debug(f"应用配置: {cmd}")
                except Exception as e:
                    logger.warning(f"配置应用失败: {cmd} - {e}")

            logger.info(f"详细配置应用完成: {applied_count}/{len(config_commands)}")

        except Exception as e:
            logger.error(f"应用详细配置失败: {e}")

    def get_connection(self, connection_id: str):
        """获取DuckDB连接"""
        with self._lock:
            connection_info = self.active_connections.get(connection_id)
            if connection_info and connection_info.get('connection'):
                return connection_info['connection']
            return None

    def get_connection_status(self, connection_id: str) -> Dict[str, Any]:
        """获取连接状态"""
        with self._lock:
            connection_info = self.active_connections.get(connection_id)
            if connection_info:
                return {
                    'connection_id': connection_info['connection_id'],
                    'db_path': connection_info['db_path'],
                    'status': connection_info['status'],
                    'created_at': connection_info['created_at'].isoformat(),
                    'has_optimizer': connection_info.get('optimizer') is not None,
                    'has_connection': connection_info.get('connection') is not None,
                    'last_config': connection_info.get('last_config_applied', {}).get('profile_name', 'None')
                }
            return {'error': 'Connection not found'}

    def list_connections(self) -> List[Dict[str, Any]]:
        """列出所有连接状态"""
        with self._lock:
            return [self.get_connection_status(conn_id) for conn_id in self.active_connections.keys()]

    def add_config_listener(self, listener: Callable[[DuckDBConfigProfile, str], None]):
        """添加配置变更监听器"""
        if listener not in self.config_listeners:
            self.config_listeners.append(listener)
            logger.info(f"添加配置监听器: {listener.__name__ if hasattr(listener, '__name__') else str(listener)}")

    def remove_config_listener(self, listener: Callable):
        """移除配置变更监听器"""
        if listener in self.config_listeners:
            self.config_listeners.remove(listener)
            logger.info(f"移除配置监听器: {listener.__name__ if hasattr(listener, '__name__') else str(listener)}")

    def _notify_config_changed(self, profile: DuckDBConfigProfile, changed_by: str):
        """通知配置变更"""
        for listener in self.config_listeners:
            try:
                listener(profile, changed_by)
            except Exception as e:
                logger.error(f"配置监听器执行失败: {e}")

    def get_current_config(self) -> Optional[DuckDBConfigProfile]:
        """获取当前活动配置"""
        return self.current_config

    def reload_active_config(self) -> bool:
        """重新加载活动配置"""
        try:
            self._load_active_config()

            # 如果有新的活动配置，应用到所有连接
            if self.current_config:
                applied_count = 0
                with self._lock:
                    for connection_id in list(self.active_connections.keys()):
                        try:
                            if self._apply_config_to_connection(connection_id, self.current_config):
                                applied_count += 1
                        except Exception as e:
                            logger.error(f"重新应用配置到连接 {connection_id} 失败: {e}")

                logger.info(f"重新加载配置完成: {self.current_config.profile_name}, 应用到 {applied_count} 个连接")
                return True
            else:
                logger.warning("没有找到活动配置")
                return False

        except Exception as e:
            logger.error(f"重新加载活动配置失败: {e}")
            return False

    def test_config_on_connection(self, connection_id: str, profile: DuckDBConfigProfile) -> Dict[str, Any]:
        """在指定连接上测试配置"""
        try:
            connection_info = self.active_connections.get(connection_id)
            if not connection_info:
                return {'error': f'连接不存在: {connection_id}'}

            # 创建临时优化器进行测试
            test_db_path = f"{connection_info['db_path']}_test"
            test_optimizer = DuckDBPerformanceOptimizer(test_db_path)

            # 应用配置
            workload_type = getattr(WorkloadType, profile.workload_type, WorkloadType.OLAP)
            success = test_optimizer.optimize_for_workload(workload_type)

            if not success:
                test_optimizer.close()
                return {'error': '配置应用失败'}

            # 执行基准测试
            test_queries = [
                "SELECT 1 as test",
                "SELECT COUNT(*) FROM (SELECT 1 as x FROM generate_series(1, 1000))",
                "SELECT x FROM generate_series(1, 100) as t(x) ORDER BY x DESC LIMIT 10"
            ]

            benchmark_result = test_optimizer.benchmark_configuration(test_queries)

            # 清理
            test_optimizer.close()

            # 删除测试数据库文件
            try:
                Path(test_db_path).unlink(missing_ok=True)
            except Exception:
                pass

            return {
                'connection_id': connection_id,
                'profile_name': profile.profile_name,
                'test_result': benchmark_result,
                'test_time': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"测试配置失败: {e}")
            return {'error': str(e)}

    def get_connection_performance_stats(self, connection_id: str) -> Dict[str, Any]:
        """获取连接性能统计"""
        try:
            connection_info = self.active_connections.get(connection_id)
            if not connection_info:
                return {'error': f'连接不存在: {connection_id}'}

            optimizer = connection_info.get('optimizer')
            if not optimizer:
                return {'error': '优化器不可用'}

            # 获取性能建议
            recommendations = optimizer.get_performance_recommendations()

            # 获取当前配置
            current_config = connection_info.get('last_config_applied', {})

            return {
                'connection_id': connection_id,
                'status': connection_info['status'],
                'current_config': current_config.get('profile_name', 'Unknown'),
                'performance_recommendations': recommendations,
                'config_applied_at': connection_info.get('created_at', datetime.now()).isoformat()
            }

        except Exception as e:
            logger.error(f"获取连接性能统计失败: {e}")
            return {'error': str(e)}

    def close_all_connections(self):
        """关闭所有连接"""
        with self._lock:
            for connection_id in list(self.active_connections.keys()):
                try:
                    self.unregister_connection(connection_id)
                except Exception as e:
                    logger.error(f"关闭连接失败 {connection_id}: {e}")

            logger.info("所有DuckDB连接已关闭")


# 全局动态配置管理器实例
_dynamic_config_manager = None
_manager_lock = threading.Lock()


def get_dynamic_config_manager() -> DynamicConfigManager:
    """获取动态配置管理器实例"""
    global _dynamic_config_manager

    with _manager_lock:
        if _dynamic_config_manager is None:
            _dynamic_config_manager = DynamicConfigManager()

    return _dynamic_config_manager


def register_duckdb_connection(connection_id: str, db_path: str) -> bool:
    """注册DuckDB连接（便捷函数）"""
    manager = get_dynamic_config_manager()
    return manager.register_connection(connection_id, db_path)


def apply_config_profile(profile_id: int, applied_by: str = "system") -> bool:
    """应用配置配置文件（便捷函数）"""
    manager = get_dynamic_config_manager()
    return manager.apply_config_profile(profile_id, applied_by)


def get_duckdb_connection(connection_id: str):
    """获取DuckDB连接（便捷函数）"""
    manager = get_dynamic_config_manager()
    return manager.get_connection(connection_id)


# 配置变更监听器示例
def log_config_change(profile: DuckDBConfigProfile, changed_by: str):
    """记录配置变更"""
    logger.info(f"配置变更: {profile.profile_name} (by {changed_by})")
    logger.info(f"  工作负载类型: {profile.workload_type}")
    logger.info(f"  内存限制: {profile.memory_limit}")
    logger.info(f"  线程数: {profile.threads}")


# 自动注册日志监听器
def _auto_register_listeners():
    """自动注册监听器"""
    try:
        manager = get_dynamic_config_manager()
        manager.add_config_listener(log_config_change)
    except Exception as e:
        logger.error(f"自动注册监听器失败: {e}")


# 模块加载时自动注册
_auto_register_listeners()


if __name__ == '__main__':
    # 测试动态配置管理器
    # Loguru配置在core.loguru_config中统一管理

    # 创建管理器
    manager = get_dynamic_config_manager()

    # 注册测试连接
    success = manager.register_connection('test_conn', 'data/test_dynamic.sqlite')
    logger.info(f"注册连接: {success}")

    # 列出连接
    connections = manager.list_connections()
    logger.info(f"连接列表: {connections}")

    # 获取当前配置
    current_config = manager.get_current_config()
    if current_config:
        logger.info(f"当前配置: {current_config.profile_name}")

        # 测试配置
        test_result = manager.test_config_on_connection('test_conn', current_config)
        logger.info(f"配置测试: {test_result}")

    # 清理
    manager.close_all_connections()
