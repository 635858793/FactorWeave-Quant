from loguru import logger
#!/usr/bin/env python3
"""
异步插件发现服务

使用Qt信号机制在后台线程中执行插件发现和注册，
避免阻塞主线程，提供实时进度更新。
"""

import threading
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import QApplication

class AsyncPluginDiscoveryWorker(QThread):
    """异步插件发现工作线程"""

    # 信号定义
    progress_updated = pyqtSignal(int, str)  # 进度百分比, 状态消息
    plugin_discovered = pyqtSignal(str, dict)  # 插件名称, 插件信息
    discovery_completed = pyqtSignal(dict)  # 发现结果统计
    discovery_failed = pyqtSignal(str)  # 错误消息

    def __init__(self, plugin_manager, data_standardizer, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.data_standardizer = data_standardizer
        self._stop_requested = False

    def run(self):
        """执行插件发现过程"""
        try:
            logger.info("开始异步插件发现...")
            self.progress_updated.emit(0, "初始化插件发现...")

            # 1. 插件管理器插件发现 (0-50%)
            self.progress_updated.emit(10, "扫描插件目录...")
            self._discover_plugins_async()

            if self._stop_requested:
                return

            # 2. 数据源插件发现 (50-100%)
            self.progress_updated.emit(50, "注册数据源插件...")
            self._discover_data_source_plugins_async()

            if self._stop_requested:
                return

            # 完成
            self.progress_updated.emit(100, "插件发现完成")
            self.discovery_completed.emit({
                'status': 'success',
                'message': '插件发现和注册完成'
            })

        except Exception as e:
            logger.error(f"异步插件发现失败: {e}")
            self.discovery_failed.emit(str(e))

    def _discover_plugins_async(self):
        """异步发现插件"""
        try:
            if not self.plugin_manager:
                return

            # 扫描插件目录
            self.progress_updated.emit(15, "扫描插件文件...")
            plugin_files = self._scan_plugin_files()

            if not plugin_files:
                self.progress_updated.emit(40, "未发现插件文件")
                return

            # 加载插件
            total_files = len(plugin_files)
            for i, (plugin_name, plugin_path) in enumerate(plugin_files):
                if self._stop_requested:
                    break

                progress = 15 + (25 * i // total_files)
                self.progress_updated.emit(progress, f"加载插件: {plugin_name}")

                # 在工作线程中加载插件
                success = self._load_plugin_safe(plugin_name, plugin_path)
                if success:
                    self.plugin_discovered.emit(plugin_name, {
                        'path': str(plugin_path),
                        'status': 'loaded'
                    })

                # 避免过快执行，给UI更新时间
                self.msleep(10)

            self.progress_updated.emit(40, f"插件加载完成，共处理 {total_files} 个文件")

        except Exception as e:
            logger.error(f"异步插件发现失败: {e}")
            raise

    def _discover_data_source_plugins_async(self):
        """异步发现数据源插件"""
        try:
            if not self.data_standardizer:
                self.progress_updated.emit(90, "数据标准化器未就绪，跳过插件发现")
                return

            self.progress_updated.emit(60, "注册数据源插件...")

            # 数据标准化器模式下跳过插件发现过程
            self.progress_updated.emit(90, "数据源插件注册完成（数据标准化器模式）")

        except Exception as e:
            logger.error(f"数据源插件发现失败: {e}")
            raise

    def _scan_plugin_files(self) -> List[tuple]:
        """扫描插件文件"""
        plugin_files = []

        try:
            plugin_dir = self.plugin_manager.plugin_dir
            if not plugin_dir.exists():
                return plugin_files

            excluded_files = ["plugin_interface.py", "plugin_market.py", "__init__.py"]

            # 扫描主插件目录
            for plugin_path in plugin_dir.glob("*.py"):
                if plugin_path.name not in excluded_files and not plugin_path.name.startswith("__"):
                    plugin_files.append((plugin_path.stem, plugin_path))

            # 扫描子目录
            for subdir in ["sentiment_data_sources"]:  # 修复：移除examples
                sub_path = plugin_dir / subdir
                if sub_path.exists():
                    for plugin_path in sub_path.glob("*.py"):
                        if plugin_path.name not in excluded_files and not plugin_path.name.startswith("__"):
                            plugin_name = f"{subdir}.{plugin_path.stem}"
                            plugin_files.append((plugin_name, plugin_path))
            
            # 修复：扫描data_sources及其分类子目录
            data_sources_dir = plugin_dir / "data_sources"
            if data_sources_dir.exists():
                # 扫描data_sources根目录
                for plugin_path in data_sources_dir.glob("*.py"):
                    if plugin_path.name not in excluded_files and not plugin_path.name.startswith("__"):
                        plugin_name = f"data_sources.{plugin_path.stem}"
                        plugin_files.append((plugin_name, plugin_path))
                
                # 扫描分类子目录
                excluded_subdirs = {'templates', 'examples', '__pycache__', 'test', 'tests', '.git', 'utils', 'macro_data_plugins'}
                for category_dir in data_sources_dir.iterdir():
                    if category_dir.is_dir() and category_dir.name not in excluded_subdirs:
                        for plugin_path in category_dir.glob("*_plugin.py"):
                            if plugin_path.name not in excluded_files and not plugin_path.name.startswith("__"):
                                plugin_name = f"data_sources.{category_dir.name}.{plugin_path.stem}"
                                plugin_files.append((plugin_name, plugin_path))
                                logger.debug(f"发现data_sources插件: {plugin_name}")

        except Exception as e:
            logger.error(f"扫描插件文件失败: {e}")

        return plugin_files

    def _load_plugin_safe(self, plugin_name: str, plugin_path: Path) -> bool:
        """安全加载插件"""
        try:
            # 使用插件管理器的load_plugin方法
            return self.plugin_manager.load_plugin(plugin_name, plugin_path)
        except Exception as e:
            logger.warning(f"加载插件失败 {plugin_name}: {e}")
            return False

    def stop(self):
        """停止插件发现"""
        self._stop_requested = True
        self.quit()
        self.wait(5000)  # 等待最多5秒

class AsyncPluginDiscoveryService(QObject):
    """异步插件发现服务"""

    # 信号定义
    discovery_started = pyqtSignal()
    progress_updated = pyqtSignal(int, str)
    plugin_discovered = pyqtSignal(str, dict)
    discovery_completed = pyqtSignal(dict)
    discovery_failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.is_discovering = False

    def start_discovery(self, plugin_manager, data_manager):
        """开始异步插件发现"""
        if self.is_discovering:
            logger.warning("插件发现已在进行中")
            return

        try:
            logger.info("启动异步插件发现服务...")

            # 创建工作线程
            self.worker = AsyncPluginDiscoveryWorker(plugin_manager, data_manager)

            # 连接信号
            self.worker.progress_updated.connect(self.progress_updated.emit)
            self.worker.plugin_discovered.connect(self.plugin_discovered.emit)
            self.worker.discovery_completed.connect(self._on_discovery_completed)
            self.worker.discovery_failed.connect(self._on_discovery_failed)

            # 启动工作线程
            self.worker.start()
            self.is_discovering = True
            self.discovery_started.emit()

            logger.info("异步插件发现服务已启动")

        except Exception as e:
            logger.error(f"启动异步插件发现失败: {e}")
            self.discovery_failed.emit(str(e))

    def stop_discovery(self):
        """停止插件发现"""
        if self.worker and self.is_discovering:
            logger.info("停止异步插件发现...")
            self.worker.stop()
            self.worker = None
            self.is_discovering = False

    def _on_discovery_completed(self, result: dict):
        """插件发现完成"""
        self.is_discovering = False
        self.discovery_completed.emit(result)
        logger.info("异步插件发现完成")

    def _on_discovery_failed(self, error_msg: str):
        """插件发现失败"""
        self.is_discovering = False
        self.discovery_failed.emit(error_msg)
        logger.error(f"异步插件发现失败: {error_msg}")

# 全局服务实例
_async_plugin_discovery_service = None

def get_async_plugin_discovery_service() -> AsyncPluginDiscoveryService:
    """获取异步插件发现服务实例"""
    global _async_plugin_discovery_service
    if _async_plugin_discovery_service is None:
        _async_plugin_discovery_service = AsyncPluginDiscoveryService()
    return _async_plugin_discovery_service
