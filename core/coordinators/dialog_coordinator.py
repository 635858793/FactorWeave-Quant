"""
对话框协调器模块

负责管理所有对话框的创建、显示、关闭。
从 MainWindowCoordinator 中提取对话框相关功能，实现集中化管理。
"""

from collections import OrderedDict
from loguru import logger
from typing import Dict, Any, Optional, Type
from PyQt5.QtWidgets import QDialog, QApplication, QWidget
from PyQt5.QtCore import Qt

from core.coordinators.base_coordinator import BaseCoordinator


class DialogCoordinator(BaseCoordinator):
    """
    对话框协调器

    职责：
    1. 管理所有对话框的创建、显示、关闭
    2. 提供 LRU 对话框缓存机制，避免重复创建
    3. 居中显示对话框
    4. 管理对话框的生命周期
    """

    MAX_CACHE_SIZE = 20

    def __init__(self,
                 main_window_coordinator=None,
                 main_window=None,
                 service_container=None,
                 event_bus=None,
                 parent_widget: Optional[QWidget] = None):
        """
        初始化对话框协调器

        Args:
            main_window_coordinator: 主窗口协调器引用
            main_window: 主窗口实例
            service_container: 服务容器
            event_bus: 事件总线
            parent_widget: 父窗口部件
        """
        super().__init__(service_container, event_bus)
        
        self._main_window_coordinator = main_window_coordinator
        self._main_window = main_window
        self._parent_widget = parent_widget or main_window
        self._dialog_cache: OrderedDict[str, QDialog] = OrderedDict()
        self._active_dialogs: Dict[str, QDialog] = {}

    def show_dialog(self, dialog_type: str, dialog_class: Type[QDialog], **kwargs) -> Optional[QDialog]:
        """
        显示对话框
        
        Args:
            dialog_type: 对话框类型标识（用于缓存）
            dialog_class: 对话框类
            **kwargs: 传递给对话框构造函数的参数
            
        Returns:
            对话框实例
        """
        try:
            self._ensure_not_disposed()
            
            # 检查缓存
            cache_key = f"{dialog_type}_{str(kwargs)}"
            
            if cache_key in self._dialog_cache:
                dialog = self._dialog_cache[cache_key]
                if dialog.isVisible():
                    dialog.raise_()
                    dialog.activateWindow()
                    logger.debug(f"Dialog {dialog_type} already visible, raising")
                    return dialog
                else:
                    # 对话框已创建但不可见，重新显示
                    dialog.show()
                    self.center_dialog(dialog)
                    self._active_dialogs[cache_key] = dialog
                    logger.info(f"Dialog {dialog_type} shown from cache")
                    return dialog
            
            # 创建新对话框
            parent = kwargs.pop('parent', self._parent_widget)
            dialog = dialog_class(parent=parent, **kwargs)
            
            # 检查缓存大小，执行 LRU 淘汰
            if len(self._dialog_cache) >= self.MAX_CACHE_SIZE:
                oldest_key, oldest_dialog = self._dialog_cache.popitem(last=False)
                if oldest_dialog and oldest_dialog != dialog:
                    try:
                        oldest_dialog.close()
                        logger.debug(f"LRU evicted oldest dialog: {oldest_key}")
                    except Exception as e:
                        logger.warning(f"Failed to close evicted dialog: {e}")
            
            # 缓存对话框
            self._dialog_cache[cache_key] = dialog
            self._dialog_cache.move_to_end(cache_key)
            self._active_dialogs[cache_key] = dialog
            
            # 显示对话框
            dialog.show()
            self.center_dialog(dialog)
            
            # 连接关闭信号
            dialog.finished.connect(
                lambda: self._on_dialog_closed(cache_key)
            )
            
            logger.info(f"Dialog {dialog_type} created and shown")
            return dialog
            
        except Exception as e:
            logger.error(f"Failed to show dialog {dialog_type}: {e}")
            return None

    def close_dialog(self, dialog_type: str, **kwargs) -> bool:
        """
        关闭指定对话框
        
        Args:
            dialog_type: 对话框类型标识
            **kwargs: 用于匹配缓存的关键词参数
            
        Returns:
            是否成功关闭
        """
        try:
            cache_key = f"{dialog_type}_{str(kwargs)}"
            
            if cache_key in self._active_dialogs:
                dialog = self._active_dialogs[cache_key]
                dialog.close()
                logger.info(f"Dialog {dialog_type} closed")
                return True
            
            logger.warning(f"Dialog {dialog_type} not found")
            return False
            
        except Exception as e:
            logger.error(f"Failed to close dialog {dialog_type}: {e}")
            return False

    def close_all_dialogs(self) -> int:
        """
        关闭所有活动对话框
        
        Returns:
            关闭的对话框数量
        """
        try:
            count = 0
            for cache_key, dialog in list(self._active_dialogs.items()):
                try:
                    dialog.close()
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to close dialog {cache_key}: {e}")
            
            self._active_dialogs.clear()
            logger.info(f"Closed {count} dialogs")
            return count
            
        except Exception as e:
            logger.error(f"Failed to close all dialogs: {e}")
            return 0

    def center_dialog(self, dialog: QDialog, parent: Optional[QWidget] = None, offset_y: int = 50) -> None:
        """
        居中显示对话框
        
        Args:
            dialog: 对话框实例
            parent: 父窗口（默认为主窗口）
            offset_y: Y轴偏移量
        """
        try:
            if parent is None:
                parent = self._parent_widget
            
            if parent is None:
                logger.warning("No parent widget available for centering dialog")
                return
            
            # 获取父窗口的几何信息
            parent_rect = parent.geometry()
            
            # 计算对话框的位置
            x = parent_rect.x() + (parent_rect.width() - dialog.width()) // 2
            y = parent_rect.y() + (parent_rect.height() - dialog.height()) // 2 - offset_y
            
            # 确保对话框不会超出屏幕边界
            screen = QApplication.desktop().screenGeometry()
            x = max(0, min(x, screen.width() - dialog.width()))
            y = max(0, min(y, screen.height() - dialog.height()))
            
            dialog.move(x, y)
            
        except Exception as e:
            logger.error(f"Failed to center dialog: {e}")

    def get_active_dialog_count(self) -> int:
        """
        获取活动对话框数量
        
        Returns:
            活动对话框数量
        """
        return len(self._active_dialogs)

    def is_dialog_open(self, dialog_type: str, **kwargs) -> bool:
        """
        检查对话框是否已打开
        
        Args:
            dialog_type: 对话框类型标识
            **kwargs: 用于匹配缓存的关键词参数
            
        Returns:
            对话框是否已打开且可见
        """
        cache_key = f"{dialog_type}_{str(kwargs)}"
        
        if cache_key in self._active_dialogs:
            dialog = self._active_dialogs[cache_key]
            return dialog.isVisible()
        
        return False

    def _on_dialog_closed(self, cache_key: str) -> None:
        """
        对话框关闭回调
        
        Args:
            cache_key: 缓存键
        """
        try:
            if cache_key in self._active_dialogs:
                del self._active_dialogs[cache_key]
                logger.debug(f"Dialog removed from active list: {cache_key}")
            
        except Exception as e:
            logger.error(f"Error handling dialog closed event: {e}")

    def clear_cache(self) -> None:
        """
        清空对话框缓存
        """
        try:
            self.close_all_dialogs()
            self._dialog_cache.clear()
            logger.info("Dialog cache cleared")
            
        except Exception as e:
            logger.error(f"Failed to clear dialog cache: {e}")

    def _do_dispose(self) -> None:
        """
        清理对话框协调器资源
        """
        try:
            self.close_all_dialogs()
            self._dialog_cache.clear()
            logger.info("Dialog coordinator disposed")
            
        except Exception as e:
            logger.error(f"Failed to dispose dialog coordinator: {e}")
