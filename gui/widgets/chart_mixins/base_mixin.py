from loguru import logger
"""
图表控件基础功能Mixin

该模块包含ChartWidget的基础功能，包括：
- 初始化和配置管理
- 主题应用和样式设置
- 基础UI初始化
- 管理器实例化
"""

import traceback
from typing import Optional, Dict, Any
from PyQt5.QtCore import QTimer, QMutex, QMutexLocker, Qt
from PyQt5.QtWidgets import QVBoxLayout, QSizePolicy
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# 导入必要的管理器
from utils.cache import Cache
from core.config import ConfigManager
from ..async_data_processor import AsyncDataProcessor
from ..chart_renderer import ChartRenderer

# 延迟导入主题管理器，避免在模块级别导入时崩溃
THEME_MANAGER_AVAILABLE = False
get_theme_manager = None

def _import_theme_manager():
    """延迟导入主题管理器"""
    global THEME_MANAGER_AVAILABLE, get_theme_manager
    if not THEME_MANAGER_AVAILABLE:
        try:
            from utils.theme import get_theme_manager as _get_theme_manager
            get_theme_manager = _get_theme_manager
            THEME_MANAGER_AVAILABLE = True
            logger.info("主题管理器模块导入成功")
        except Exception as e:
            logger.warning(f"导入主题管理器失败: {e}")

class BaseMixin:
    """基础功能Mixin - 负责初始化、配置管理、主题应用等"""

    def __init__(self):
        """初始化基础功能 - 不接受参数，属性由主类提供"""
        # 注意：所有属性都应该在主类ChartWidget中初始化
        # 这里只做一些基础的设置
        pass

    def _process_update_queue(self):
        """处理更新队列中的任务"""
        try:
            if not self._update_queue:
                return

            with QMutexLocker(self._update_lock):
                while self._update_queue:
                    update_func, args = self._update_queue.pop(0)
                    try:
                        update_func(*args)
                    except Exception as e:
                        logger.error(f"更新任务执行失败: {str(e)}")

        except Exception as e:
            logger.error(f"处理更新队列失败: {str(e)}")

    def queue_update(self, update_func, *args):
        """将更新任务加入队列

        Args:
            update_func: 更新函数
            *args: 函数参数
        """
        with QMutexLocker(self._update_lock):
            self._update_queue.append((update_func, args))

    def update_loading_progress(self, value: int, message: str = None):
        """更新加载进度，保证数值安全"""
        value = max(0, min(100, int(value)))
        if hasattr(self, 'loading_dialog'):
            self.loading_dialog.setValue(value)
            if message:
                self.loading_dialog.setLabelText(message)

    def set_loading_progress_error(self, message="渲染失败"):
        """设置加载进度错误状态"""
        if hasattr(self, 'loading_dialog'):
            self.loading_dialog.setStyleSheet(
                "QProgressBar::chunk {background-color: #FF0000;}")
            self.loading_dialog.setLabelText(message)

    def close_loading_dialog(self):
        """关闭加载进度对话框"""
        if hasattr(self, 'loading_dialog'):
            self.loading_dialog.close()

    def _apply_initial_theme(self):
        """应用初始主题，并优化坐标轴贴边和刻度方向"""
        try:
            if not self.theme_manager:
                # 如果主题管理器不可用，使用默认颜色
                theme = None
                colors = {
                    'chart_background': '#181c24',
                    'chart_grid': '#2c3140',
                    'chart_text': '#b0b8c1'
                }
            else:
                theme = self.theme_manager.current_theme
                colors = self.theme_manager.get_theme_colors(theme)
            
            self.figure.patch.set_facecolor(
                colors.get('chart_background', '#181c24'))
            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                if ax is not None:
                    ax.set_facecolor(colors.get('chart_background', '#181c24'))
                    ax.grid(True, color=colors.get('chart_grid',
                            '#2c3140'), linestyle='--', alpha=0.3)
                    ax.tick_params(colors=colors.get(
                        'chart_text', '#b0b8c1'), direction='in', length=6)
                    # 让坐标轴贴边
                    ax.spines['left'].set_position(('outward', 0))
                    ax.spines['bottom'].set_position(('outward', 0))
                    ax.spines['right'].set_visible(False)
                    ax.spines['top'].set_visible(False)
                    # 标签靠近边界
                    ax.yaxis.set_label_position('left')
                    ax.yaxis.set_ticks_position('none')
                    ax.xaxis.set_label_position('bottom')
            self.canvas.setStyleSheet(
                f"background: {colors.get('chart_background', '#181c24')}; border-radius: 10px; border: 1px solid {colors.get('chart_grid', '#2c3140')};")
            if hasattr(self, 'toolbar'):
                self.toolbar.setStyleSheet(
                    f"background: {colors.get('chart_background', '#181c24')}; color: {colors.get('chart_text', '#b0b8c1')}; border: none;")
            self.figure.subplots_adjust(
                left=0.04, right=0.99, top=0.99, bottom=0.06, hspace=0.00)
            self.canvas.draw_idle()
        except Exception as e:
            logger.error(f"应用初始主题失败: {str(e)}")

    def apply_theme(self):
        """应用主题（兼容方法）"""
        self._apply_initial_theme()

    def _optimize_rendering(self):
        """优化渲染性能"""
        try:
            # 设置matplotlib渲染选项
            if hasattr(self, 'figure'):
                # 使用安全的布局设置，避免tight_layout警告
                from utils.matplotlib_utils import safe_figure_layout
                safe_figure_layout(self.figure,
                                   left=0.04, right=0.99,
                                   top=0.99, bottom=0.06,
                                   hspace=0.00)
                # 设置DPI和渲染质量
                self.figure.set_dpi(100)

        except Exception as e:
            logger.error(f"优化渲染失败: {str(e)}")

    def _on_render_progress(self, progress: int, message: str):
        """渲染进度回调"""
        self.update_loading_progress(progress, message)

    def _on_render_complete(self):
        """渲染完成回调"""
        self.close_loading_dialog()

    def _on_render_error(self, error: str):
        """渲染错误回调"""
        self.set_loading_progress_error(f"渲染失败: {error}")
        logger.error(f"渲染失败: {error}")

    def _on_calculation_progress(self, progress: int, message: str):
        """计算进度回调"""
        self.update_loading_progress(progress, message)

    def _on_calculation_complete(self, results: dict):
        """计算完成回调"""
        try:
            if results:
                self._update_chart_with_results(results)
        except Exception as e:
            logger.error(f"处理计算结果失败: {str(e)}")

    def _on_calculation_error(self, error: str):
        """计算错误回调"""
        self.set_loading_progress_error(f"计算失败: {error}")
        logger.error(f"计算失败: {error}")

    def _update_chart_with_results(self, results: dict):
        """使用计算结果更新图表

        Args:
            results: 计算结果字典
        """
        try:
            # 这里可以根据结果更新图表
            # 具体实现在RenderingMixin中
            pass
        except Exception as e:
            logger.error(f"更新图表失败: {str(e)}")
