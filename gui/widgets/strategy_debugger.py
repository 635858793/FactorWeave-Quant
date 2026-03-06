"""
策略调试工具组件 - 重构版
集成系统主题管理，提供断点管理、单步执行、变量查看等功能
功能：真正的断点暂停、单步执行、变量监视、调用栈查看
"""
import os
import bdb
import inspect
import traceback
import tempfile
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from loguru import logger

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLabel,
    QPushButton, QToolBar, QAction, QStatusBar,
    QSplitter, QListWidget, QListWidgetItem, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QComboBox, QApplication
)
from PyQt5.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QMutex, QMutexLocker, 
    QWaitCondition, QCoreApplication, QEvent
)
from PyQt5.QtGui import (
    QFont, QTextCharFormat, QColor, QTextCursor, QPainter
)

try:
    from utils.theme import get_theme_manager, Theme
    from gui.styles.unified_design_system import DesignTokens, ColorScheme, StyleSheetGenerator
    THEME_AVAILABLE = True
except ImportError as e:
    logger.warning(f"主题模块导入失败: {e}")
    THEME_AVAILABLE = False
    get_theme_manager = None
    Theme = None
    DesignTokens = None
    ColorScheme = None
    StyleSheetGenerator = None

try:
    from core.strategy.base_strategy import BaseStrategy, StrategySignal, SignalType
    from core.strategy.strategy_engine import StrategyEngine, get_strategy_engine
    from core.strategy.strategy_registry import get_strategy_registry
    from core.strategy.strategy_factory import get_strategy_factory
    from core.services.stock_service import StockService, get_stock_service
    from core.plugin_types import AssetType
    STRATEGY_FRAMEWORK_AVAILABLE = True
except ImportError as e:
    logger.warning(f"策略框架导入失败: {e}")
    STRATEGY_FRAMEWORK_AVAILABLE = False
    BaseStrategy = None
    StrategyEngine = None
    get_strategy_engine = None
    get_strategy_registry = None
    get_strategy_factory = None
    StockService = None
    get_stock_service = None
    AssetType = None

try:
    from gui.widgets.strategy_code_editor import CodeEditor
    CODE_EDITOR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"CodeEditor 组件导入失败: {e}")
    CODE_EDITOR_AVAILABLE = False
    CodeEditor = None


class DebugState(Enum):
    """调试状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STEP_OVER = "step_over"
    STEP_INTO = "step_into"
    STEP_OUT = "step_out"
    STOPPED = "stopped"


class BreakpointManager:
    """断点管理器"""

    def __init__(self):
        self.breakpoints: Dict[str, Set[int]] = {}
        self.enabled_breakpoints: Dict[str, Set[int]] = {}
        self.condition_breakpoints: Dict[str, Dict[int, str]] = {}

    def add_breakpoint(self, file_path: str, line: int, condition: str = None):
        """添加断点"""
        if file_path not in self.breakpoints:
            self.breakpoints[file_path] = set()
            self.enabled_breakpoints[file_path] = set()
            self.condition_breakpoints[file_path] = {}
        self.breakpoints[file_path].add(line)
        self.enabled_breakpoints[file_path].add(line)
        if condition:
            self.condition_breakpoints[file_path][line] = condition
        logger.info(f"添加断点: {file_path}:{line}" + (f" 条件: {condition}" if condition else ""))

    def remove_breakpoint(self, file_path: str, line: int):
        """移除断点"""
        if file_path in self.breakpoints:
            self.breakpoints[file_path].discard(line)
            self.enabled_breakpoints[file_path].discard(line)
            if line in self.condition_breakpoints.get(file_path, {}):
                del self.condition_breakpoints[file_path][line]
            logger.info(f"移除断点: {file_path}:{line}")

    def toggle_breakpoint(self, file_path: str, line: int):
        """切换断点状态"""
        if file_path in self.breakpoints and line in self.breakpoints[file_path]:
            self.remove_breakpoint(file_path, line)
        else:
            self.add_breakpoint(file_path, line)

    def enable_breakpoint(self, file_path: str, line: int):
        """启用断点"""
        if file_path in self.breakpoints and line in self.breakpoints[file_path]:
            self.enabled_breakpoints[file_path].add(line)
            logger.info(f"启用断点: {file_path}:{line}")

    def disable_breakpoint(self, file_path: str, line: int):
        """禁用断点"""
        if file_path in self.enabled_breakpoints:
            self.enabled_breakpoints[file_path].discard(line)
            logger.info(f"禁用断点: {file_path}:{line}")

    def is_breakpoint(self, file_path: str, line: int) -> bool:
        """检查是否是断点"""
        return (file_path in self.enabled_breakpoints and 
                line in self.enabled_breakpoints[file_path])

    def get_breakpoint_condition(self, file_path: str, line: int) -> Optional[str]:
        """获取断点条件"""
        return self.condition_breakpoints.get(file_path, {}).get(line)

    def get_breakpoints(self, file_path: str) -> Set[int]:
        """获取文件的所有断点"""
        return self.breakpoints.get(file_path, set())

    def clear_all_breakpoints(self):
        """清除所有断点"""
        self.breakpoints.clear()
        self.enabled_breakpoints.clear()
        self.condition_breakpoints.clear()
        logger.info("已清除所有断点")


class ThemeAwareWidget:
    """主题感知组件混入类"""
    
    def _get_theme_colors(self, theme_manager=None) -> Dict[str, str]:
        """获取主题颜色"""
        default_colors = {
            'background': '#1e1e1e',
            'background_secondary': '#2d2d2d',
            'background_tertiary': '#3c3c3c',
            'text': '#d4d4d4',
            'text_secondary': '#808080',
            'border': '#3c3c3c',
            'accent': '#264f78',
            'accent_hover': '#3678a8',
            'success': '#4ec9b0',
            'error': '#f44747',
            'warning': '#dcdcaa',
            'info': '#569cd6',
            'string': '#ce9178',
            'number': '#b5cea8',
            'keyword': '#569cd6',
            'comment': '#6a9955',
            'breakpoint': '#8b0000',
            'current_line': '#264f78',
        }
        
        if theme_manager is None:
            theme_manager = getattr(self, '_theme_manager', None)
        
        if theme_manager is None and THEME_AVAILABLE and get_theme_manager:
            try:
                theme_manager = get_theme_manager()
            except Exception as e:
                logger.debug(f"获取主题管理器失败: {e}")
        
        if theme_manager:
            try:
                colors = theme_manager.get_theme_colors()
                if colors:
                    return {**default_colors, **colors}
            except Exception as e:
                logger.debug(f"获取主题颜色失败: {e}")
        
        return default_colors
    
    def _generate_stylesheet(self, widget_type: str, colors: Dict[str, str]) -> str:
        """生成样式表"""
        styles = {
            'tree': f"""
                QTreeWidget {{
                    background-color: {colors['background']};
                    border: 1px solid {colors['border']};
                    border-radius: 4px;
                    color: {colors['text']};
                    font-family: Consolas;
                    font-size: 11px;
                }}
                QTreeWidget::item {{
                    padding: 2px;
                }}
                QTreeWidget::item:selected {{
                    background-color: {colors['accent']};
                }}
                QHeaderView::section {{
                    background-color: {colors['background_secondary']};
                    color: {colors['text']};
                    padding: 4px;
                    border: none;
                    border-bottom: 1px solid {colors['border']};
                }}
            """,
            'list': f"""
                QListWidget {{
                    background-color: {colors['background']};
                    border: 1px solid {colors['border']};
                    border-radius: 4px;
                    color: {colors['text']};
                    font-family: Consolas;
                    font-size: 11px;
                }}
                QListWidget::item {{
                    padding: 4px;
                    border-bottom: 1px solid {colors['border']};
                }}
                QListWidget::item:selected {{
                    background-color: {colors['accent']};
                }}
                QListWidget::item:hover {{
                    background-color: {colors['background_secondary']};
                }}
            """,
            'text': f"""
                QTextEdit {{
                    background-color: {colors['background']};
                    border: 1px solid {colors['border']};
                    border-radius: 4px;
                    color: {colors['text']};
                    font-family: Consolas;
                    font-size: 11px;
                }}
            """,
            'button': f"""
                QPushButton {{
                    background-color: {colors['background_secondary']};
                    border: 1px solid {colors['border']};
                    border-radius: 4px;
                    padding: 6px 12px;
                    color: {colors['text']};
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: {colors['background_tertiary']};
                }}
                QPushButton:pressed {{
                    background-color: {colors['accent']};
                }}
                QPushButton:disabled {{
                    background-color: {colors['background']};
                    color: {colors['text_secondary']};
                }}
            """,
            'tab': f"""
                QTabWidget::pane {{
                    border: 1px solid {colors['border']};
                    background-color: {colors['background']};
                }}
                QTabBar::tab {{
                    background-color: {colors['background_secondary']};
                    color: {colors['text']};
                    padding: 6px 12px;
                    border: 1px solid {colors['border']};
                }}
                QTabBar::tab:selected {{
                    background-color: {colors['background']};
                }}
            """,
            'header_label': f"""
                QLabel {{
                    background-color: {colors['background_secondary']};
                    color: {colors['text']};
                    padding: 8px;
                    font-weight: bold;
                }}
            """,
            'primary_button': f"""
                QPushButton {{
                    background-color: {colors['accent']};
                    color: white;
                    border: none;
                    padding: 4px 12px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {colors['accent_hover']};
                }}
            """,
            'danger_button': f"""
                QPushButton {{
                    background-color: {colors['error']};
                    color: white;
                    border: none;
                    padding: 4px 12px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: #a00000;
                }}
            """,
        }
        return styles.get(widget_type, '')


class DebuggerThread(QThread, bdb.Bdb):
    """调试器线程 - 基于 bdb 实现真正的调试功能"""
    
    signal_breakpoint_hit = pyqtSignal(str, int, dict)
    signal_step_complete = pyqtSignal(str, int, dict)
    signal_execution_complete = pyqtSignal(dict)
    signal_error = pyqtSignal(str)
    signal_call_stack_update = pyqtSignal(list)
    signal_output = pyqtSignal(str)
    
    def __init__(self, code: str, filename: str, breakpoints: Dict[str, Set[int]], 
                 context: Dict[str, Any] = None, parent=None):
        QThread.__init__(self, parent)
        bdb.Bdb.__init__(self)
        
        self.code = code
        self.filename = filename
        self.breakpoints_data = breakpoints
        self.local_vars = {}
        self.global_vars = {'__name__': '__main__'}
        
        if context:
            self.global_vars.update(context)
        
        self._state = DebugState.IDLE
        self._state_lock = QMutex()
        self._wait_condition = QWaitCondition()
        self._running = True
        self._current_frame = None
        self._call_stack = []
        
        self._step_mode = None
        self._stop_frame = None
        
        self._original_stdout = None
        self._original_stderr = None
        
        for file_path, lines in breakpoints.items():
            for line in lines:
                self.set_break(file_path, line)
    
    def get_state(self) -> DebugState:
        with QMutexLocker(self._state_lock):
            return self._state
    
    def set_state(self, state: DebugState):
        with QMutexLocker(self._state_lock):
            self._state = state
    
    def continue_execution(self):
        """继续执行"""
        self._step_mode = None
        self.set_state(DebugState.RUNNING)
        self._wait_condition.wakeAll()
    
    def step_over(self):
        """单步跳过"""
        self._step_mode = 'over'
        self._stop_frame = self._current_frame
        self.set_state(DebugState.STEP_OVER)
        self._wait_condition.wakeAll()
    
    def step_into(self):
        """单步进入"""
        self._step_mode = 'into'
        self.set_state(DebugState.STEP_INTO)
        self._wait_condition.wakeAll()
    
    def step_out(self):
        """单步退出"""
        self._step_mode = 'out'
        self._stop_frame = self._current_frame
        self.set_state(DebugState.STEP_OUT)
        self._wait_condition.wakeAll()
    
    def stop(self):
        """停止调试"""
        self._running = False
        self.set_state(DebugState.STOPPED)
        self._wait_condition.wakeAll()
    
    def _capture_output(self):
        """捕获标准输出"""
        import sys
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        
        class OutputCapture:
            def __init__(self, callback):
                self.callback = callback
            
            def write(self, text):
                if text.strip():
                    self.callback(text)
            
            def flush(self):
                pass
        
        sys.stdout = OutputCapture(lambda t: self.signal_output.emit(t))
        sys.stderr = OutputCapture(lambda t: self.signal_output.emit(f"[ERROR] {t}"))
    
    def _restore_output(self):
        """恢复标准输出"""
        import sys
        if self._original_stdout:
            sys.stdout = self._original_stdout
        if self._original_stderr:
            sys.stderr = self._original_stderr
    
    def run(self):
        """运行调试会话"""
        self.set_state(DebugState.RUNNING)
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, 
                                             encoding='utf-8') as f:
                f.write(self.code)
                temp_file = f.name
            
            try:
                self._capture_output()
                self.global_vars['__file__'] = temp_file
                code_obj = compile(self.code, temp_file, 'exec')
                self.set_trace()
                exec(code_obj, self.global_vars, self.local_vars)
                
                result = {
                    'success': True,
                    'local_vars': self._safe_copy_vars(self.local_vars),
                    'global_vars': self._safe_copy_vars(self.global_vars),
                }
                self.signal_execution_complete.emit(result)
                
            finally:
                self._restore_output()
                self.reset()
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    
        except bdb.BdbQuit:
            self._restore_output()
            self.signal_execution_complete.emit({'success': True, 'stopped': True})
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            self.signal_error.emit(error_msg)
            logger.error(f"调试执行错误: {error_msg}\n{traceback.format_exc()}")
    
    def user_line(self, frame):
        """在每行执行前调用"""
        if not self._running:
            raise bdb.BdbQuit()
        
        self._current_frame = frame
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        
        self._update_call_stack(frame)
        
        is_breakpoint = self.breaks.get(filename, {}).get(lineno, False)
        
        should_pause = False
        
        if is_breakpoint:
            should_pause = True
            self.set_state(DebugState.PAUSED)
        
        elif self._step_mode == 'into':
            should_pause = True
            self.set_state(DebugState.PAUSED)
        
        elif self._step_mode == 'over':
            if self._stop_frame is None or frame == self._stop_frame:
                should_pause = True
                self.set_state(DebugState.PAUSED)
        
        elif self._step_mode == 'out':
            if self._stop_frame is not None:
                try:
                    frame_depth = 0
                    f = frame
                    while f is not None:
                        if f == self._stop_frame:
                            break
                        frame_depth += 1
                        f = f.f_back
                    else:
                        should_pause = True
                        self.set_state(DebugState.PAUSED)
                except:
                    pass
        
        if should_pause:
            vars_data = {
                'local_vars': self._safe_copy_vars(frame.f_locals),
                'global_vars': self._safe_copy_vars(frame.f_globals),
            }
            
            if is_breakpoint:
                self.signal_breakpoint_hit.emit(filename, lineno, vars_data)
            else:
                self.signal_step_complete.emit(filename, lineno, vars_data)
            
            self._wait_for_user_action()
        
        return self._running
    
    def user_call(self, frame, argument_list):
        """函数调用时调用"""
        if not self._running:
            raise bdb.BdbQuit()
        self._update_call_stack(frame)
    
    def user_return(self, frame, return_value):
        """函数返回时调用"""
        pass
    
    def user_exception(self, frame, exc_info):
        """异常发生时调用"""
        exc_type, exc_value, exc_tb = exc_info
        error_msg = f"{exc_type.__name__}: {str(exc_value)}"
        self.signal_error.emit(error_msg)
    
    def _update_call_stack(self, frame):
        """更新调用栈"""
        self._call_stack = []
        f = frame
        while f is not None:
            self._call_stack.append({
                'filename': f.f_code.co_filename,
                'lineno': f.f_lineno,
                'function': f.f_code.co_name,
                'locals': dict(f.f_locals),
            })
            f = f.f_back
        self.signal_call_stack_update.emit(self._call_stack)
    
    def _wait_for_user_action(self):
        """等待用户操作 - 使用 QWaitCondition 进行线程同步"""
        while self.get_state() == DebugState.PAUSED and self._running:
            with QMutexLocker(self._state_lock):
                self._wait_condition.wait(self._state_lock)
    
    def _safe_copy_vars(self, vars_dict: dict) -> dict:
        """安全复制变量字典"""
        result = {}
        for key, value in vars_dict.items():
            if key.startswith('__') and key.endswith('__'):
                continue
            try:
                if isinstance(value, (str, int, float, bool, type(None))):
                    result[key] = value
                elif isinstance(value, (list, tuple)):
                    result[key] = f"[{len(value)} items]"
                elif isinstance(value, dict):
                    result[key] = f"{{{len(value)} items}}"
                else:
                    result[key] = f"<{type(value).__name__}>"
            except:
                result[key] = "<无法显示>"
        return result


class VariableViewer(QWidget, ThemeAwareWidget):
    """变量查看器"""

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.var_tree = QTreeWidget()
        self.var_tree.setHeaderLabels(['变量', '类型', '值'])
        self._apply_theme()
        layout.addWidget(self.var_tree)

    def _apply_theme(self):
        """应用主题"""
        colors = self._get_theme_colors(self._theme_manager)
        self.var_tree.setStyleSheet(self._generate_stylesheet('tree', colors))

    def update_theme(self, theme_manager):
        """更新主题"""
        self._theme_manager = theme_manager
        self._apply_theme()

    def update_variables(self, local_vars: Dict[str, Any], global_vars: Dict[str, Any] = None):
        """更新变量显示"""
        self.var_tree.clear()
        colors = self._get_theme_colors(self._theme_manager)

        local_item = QTreeWidgetItem(['局部变量', '', ''])
        local_item.setForeground(0, QColor(colors['success']))
        self.var_tree.addTopLevelItem(local_item)

        for name, value in sorted(local_vars.items()):
            if name.startswith('_'):
                continue
            self._add_variable_item(local_item, name, value, colors)

        if global_vars:
            global_item = QTreeWidgetItem(['全局变量', '', ''])
            global_item.setForeground(0, QColor(colors['success']))
            self.var_tree.addTopLevelItem(global_item)

            for name, value in sorted(global_vars.items()):
                if name.startswith('_') or name in local_vars:
                    continue
                self._add_variable_item(global_item, name, value, colors)

        self.var_tree.expandAll()

    def _add_variable_item(self, parent: QTreeWidgetItem, name: str, value: Any, colors: Dict[str, str]):
        """添加变量项"""
        type_name = type(value).__name__ if not isinstance(value, str) else 'str'
        
        if isinstance(value, (list, tuple)):
            display_value = f"[{len(value)} items]"
            color = colors['success']
        elif isinstance(value, dict):
            display_value = f"{{{len(value)} items}}"
            color = colors['success']
        elif isinstance(value, str):
            display_value = f'"{value[:50]}..."' if len(value) > 50 else f'"{value}"'
            color = colors['string']
        elif isinstance(value, (int, float)):
            display_value = str(value)
            color = colors['number']
        elif isinstance(value, bool):
            display_value = str(value)
            color = colors['keyword']
        elif value is None:
            display_value = 'None'
            color = colors['keyword']
        else:
            display_value = str(value)[:50]
            color = colors['text']

        item = QTreeWidgetItem([name, type_name, display_value])
        item.setForeground(0, QColor(color))
        item.setForeground(2, QColor(color))
        parent.addChild(item)

        if isinstance(value, (list, tuple)) and len(value) <= 20:
            for i, v in enumerate(value):
                self._add_variable_item(item, f'[{i}]', v, colors)
        elif isinstance(value, dict) and len(value) <= 20:
            for k, v in value.items():
                self._add_variable_item(item, str(k), v, colors)


class CallStackViewer(QWidget, ThemeAwareWidget):
    """调用栈查看器"""

    frame_clicked = pyqtSignal(int)

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stack_list = QListWidget()
        self._apply_theme()
        self.stack_list.itemClicked.connect(self._on_frame_clicked)
        layout.addWidget(self.stack_list)

    def _apply_theme(self):
        """应用主题"""
        colors = self._get_theme_colors(self._theme_manager)
        self.stack_list.setStyleSheet(self._generate_stylesheet('list', colors))

    def update_theme(self, theme_manager):
        """更新主题"""
        self._theme_manager = theme_manager
        self._apply_theme()

    def update_call_stack(self, frames: List[Dict]):
        """更新调用栈"""
        self.stack_list.clear()
        colors = self._get_theme_colors(self._theme_manager)
        
        for i, frame in enumerate(frames):
            func_name = frame.get('function', '<unknown>')
            file_name = os.path.basename(frame.get('filename', '<unknown>'))
            line_no = frame.get('lineno', 0)
            
            item_text = f"[{i}] {func_name} at {file_name}:{line_no}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, i)
            item.setForeground(QColor(colors['text']))
            self.stack_list.addItem(item)

    def _on_frame_clicked(self, item: QListWidgetItem):
        """帧点击"""
        frame_index = item.data(Qt.UserRole)
        if frame_index is not None:
            self.frame_clicked.emit(frame_index)


class BreakpointListWidget(QWidget, ThemeAwareWidget):
    """断点列表面板"""

    breakpoint_clicked = pyqtSignal(str, int)
    breakpoint_toggled = pyqtSignal(str, int, bool)
    breakpoint_removed = pyqtSignal(str, int)

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._breakpoints_data = []
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_layout = QHBoxLayout()
        self.header_label = QLabel("断点列表")
        self._apply_header_style()
        header_layout.addWidget(self.header_label)
        
        self.clear_btn = QPushButton("清除全部")
        self.clear_btn.clicked.connect(self._clear_all_breakpoints)
        self._apply_clear_button_style()
        header_layout.addWidget(self.clear_btn)
        layout.addLayout(header_layout)

        self.bp_list = QListWidget()
        self._apply_list_style()
        self.bp_list.itemClicked.connect(self._on_breakpoint_clicked)
        self.bp_list.itemDoubleClicked.connect(self._on_breakpoint_double_clicked)
        layout.addWidget(self.bp_list)

        btn_layout = QHBoxLayout()
        
        self.enable_btn = QPushButton("启用")
        self.enable_btn.clicked.connect(self._enable_selected)
        self._apply_primary_button_style(self.enable_btn)
        btn_layout.addWidget(self.enable_btn)
        
        self.disable_btn = QPushButton("禁用")
        self.disable_btn.clicked.connect(self._disable_selected)
        self._apply_secondary_button_style(self.disable_btn)
        btn_layout.addWidget(self.disable_btn)
        
        self.remove_btn = QPushButton("删除")
        self.remove_btn.clicked.connect(self._remove_selected)
        self._apply_danger_button_style(self.remove_btn)
        btn_layout.addWidget(self.remove_btn)
        
        layout.addLayout(btn_layout)

    def _apply_header_style(self):
        colors = self._get_theme_colors(self._theme_manager)
        self.header_label.setStyleSheet(self._generate_stylesheet('header_label', colors))

    def _apply_clear_button_style(self):
        colors = self._get_theme_colors(self._theme_manager)
        self.clear_btn.setStyleSheet(self._generate_stylesheet('button', colors))

    def _apply_list_style(self):
        colors = self._get_theme_colors(self._theme_manager)
        self.bp_list.setStyleSheet(self._generate_stylesheet('list', colors))

    def _apply_primary_button_style(self, btn):
        colors = self._get_theme_colors(self._theme_manager)
        btn.setStyleSheet(self._generate_stylesheet('primary_button', colors))

    def _apply_secondary_button_style(self, btn):
        colors = self._get_theme_colors(self._theme_manager)
        btn.setStyleSheet(self._generate_stylesheet('button', colors))

    def _apply_danger_button_style(self, btn):
        colors = self._get_theme_colors(self._theme_manager)
        btn.setStyleSheet(self._generate_stylesheet('danger_button', colors))

    def _apply_theme(self):
        """应用主题"""
        self._apply_header_style()
        self._apply_clear_button_style()
        self._apply_list_style()
        self._apply_primary_button_style(self.enable_btn)
        self._apply_secondary_button_style(self.disable_btn)
        self._apply_danger_button_style(self.remove_btn)

    def update_theme(self, theme_manager):
        """更新主题"""
        self._theme_manager = theme_manager
        self._apply_theme()

    def update_breakpoints(self, breakpoints: Dict[str, Set[int]], enabled_breakpoints: Dict[str, Set[int]]):
        """更新断点列表"""
        self.bp_list.clear()
        self._breakpoints_data = []
        colors = self._get_theme_colors(self._theme_manager)

        for file_path, lines in breakpoints.items():
            file_name = os.path.basename(file_path)
            for line in sorted(lines):
                is_enabled = line in enabled_breakpoints.get(file_path, set())
                
                status_icon = "●" if is_enabled else "○"
                item_text = f"{status_icon} {file_name}:{line}"
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, (file_path, line, is_enabled))
                
                if is_enabled:
                    item.setForeground(QColor(colors['success']))
                else:
                    item.setForeground(QColor(colors['text_secondary']))
                
                self.bp_list.addItem(item)
                self._breakpoints_data.append({
                    'file_path': file_path,
                    'line': line,
                    'enabled': is_enabled
                })

    def _on_breakpoint_clicked(self, item: QListWidgetItem):
        """断点项点击"""
        data = item.data(Qt.UserRole)
        if data:
            file_path, line, _ = data
            self.breakpoint_clicked.emit(file_path, line)

    def _on_breakpoint_double_clicked(self, item: QListWidgetItem):
        """断点项双击 - 切换启用/禁用状态"""
        data = item.data(Qt.UserRole)
        if data:
            file_path, line, is_enabled = data
            self.breakpoint_toggled.emit(file_path, line, not is_enabled)

    def _enable_selected(self):
        """启用选中断点"""
        current_item = self.bp_list.currentItem()
        if current_item:
            data = current_item.data(Qt.UserRole)
            if data:
                file_path, line, _ = data
                self.breakpoint_toggled.emit(file_path, line, True)

    def _disable_selected(self):
        """禁用选中断点"""
        current_item = self.bp_list.currentItem()
        if current_item:
            data = current_item.data(Qt.UserRole)
            if data:
                file_path, line, _ = data
                self.breakpoint_toggled.emit(file_path, line, False)

    def _remove_selected(self):
        """删除选中断点"""
        current_item = self.bp_list.currentItem()
        if current_item:
            data = current_item.data(Qt.UserRole)
            if data:
                file_path, line, _ = data
                self.breakpoint_removed.emit(file_path, line)

    def _clear_all_breakpoints(self):
        """清除所有断点"""
        for bp_data in self._breakpoints_data:
            self.breakpoint_removed.emit(bp_data['file_path'], bp_data['line'])


class DebugController(QWidget, ThemeAwareWidget):
    """调试控制器"""

    continue_clicked = pyqtSignal()
    step_over_clicked = pyqtSignal()
    step_into_clicked = pyqtSignal()
    step_out_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    restart_clicked = pyqtSignal()

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self.init_ui()
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """设置快捷键"""
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence
        
        self._shortcuts = {
            'continue': QShortcut(QKeySequence('F5'), self),
            'step_over': QShortcut(QKeySequence('F10'), self),
            'step_into': QShortcut(QKeySequence('F11'), self),
            'step_out': QShortcut(QKeySequence('Shift+F11'), self),
            'stop': QShortcut(QKeySequence('Shift+F5'), self),
            'restart': QShortcut(QKeySequence('Ctrl+Shift+F5'), self),
        }
        
        self._shortcuts['continue'].activated.connect(self.continue_clicked.emit)
        self._shortcuts['step_over'].activated.connect(self.step_over_clicked.emit)
        self._shortcuts['step_into'].activated.connect(self.step_into_clicked.emit)
        self._shortcuts['step_out'].activated.connect(self.step_out_clicked.emit)
        self._shortcuts['stop'].activated.connect(self.stop_clicked.emit)
        self._shortcuts['restart'].activated.connect(self.restart_clicked.emit)

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.continue_btn = QPushButton('▶ 继续')
        self.continue_btn.clicked.connect(self.continue_clicked.emit)
        layout.addWidget(self.continue_btn)

        self.step_over_btn = QPushButton('⏭ 单步跳过')
        self.step_over_btn.clicked.connect(self.step_over_clicked.emit)
        layout.addWidget(self.step_over_btn)

        self.step_into_btn = QPushButton('⏬ 单步进入')
        self.step_into_btn.clicked.connect(self.step_into_clicked.emit)
        layout.addWidget(self.step_into_btn)

        self.step_out_btn = QPushButton('⏫ 单步退出')
        self.step_out_btn.clicked.connect(self.step_out_clicked.emit)
        layout.addWidget(self.step_out_btn)

        self.stop_btn = QPushButton('⏹ 停止')
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        layout.addWidget(self.stop_btn)

        self.restart_btn = QPushButton('🔄 重启')
        self.restart_btn.clicked.connect(self.restart_clicked.emit)
        layout.addWidget(self.restart_btn)

        self._apply_theme()

    def _apply_theme(self):
        """应用主题"""
        colors = self._get_theme_colors(self._theme_manager)
        style = self._generate_stylesheet('button', colors)
        for btn in [self.continue_btn, self.step_over_btn, self.step_into_btn,
                    self.step_out_btn, self.stop_btn, self.restart_btn]:
            btn.setStyleSheet(style)

    def update_theme(self, theme_manager):
        """更新主题"""
        self._theme_manager = theme_manager
        self._apply_theme()

    def set_debugging_state(self, is_debugging: bool, is_paused: bool = False):
        """设置调试状态
        
        Args:
            is_debugging: 是否正在调试中
            is_paused: 是否处于暂停状态（用于区分运行中和暂停）
        """
        self.continue_btn.setEnabled(is_paused)
        self.step_over_btn.setEnabled(is_paused)
        self.step_into_btn.setEnabled(is_paused)
        self.step_out_btn.setEnabled(is_paused)
        self.stop_btn.setEnabled(is_debugging)
        self.restart_btn.setEnabled(not is_debugging)


class OutputViewer(QWidget, ThemeAwareWidget):
    """输出查看器"""

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self._apply_theme()
        layout.addWidget(self.output_text)

    def _apply_theme(self):
        """应用主题"""
        colors = self._get_theme_colors(self._theme_manager)
        self.output_text.setStyleSheet(self._generate_stylesheet('text', colors))

    def update_theme(self, theme_manager):
        """更新主题"""
        self._theme_manager = theme_manager
        self._apply_theme()

    def append_output(self, text: str, color: str = None):
        """添加输出"""
        colors = self._get_theme_colors(self._theme_manager)
        if color is None:
            color = colors['text']
            
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        format = QTextCharFormat()
        format.setForeground(QColor(color))
        cursor.insertText(text + '\n', format)
        
        self.output_text.setTextCursor(cursor)
        self.output_text.ensureCursorVisible()

    def clear_output(self):
        """清除输出"""
        self.output_text.clear()


class StrategyDebugger(QWidget, ThemeAwareWidget):
    """策略调试器 - 重构版"""

    debug_started = pyqtSignal()
    debug_stopped = pyqtSignal()
    breakpoint_hit = pyqtSignal(str, int)
    debug_state_changed = pyqtSignal(str)

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self.breakpoint_manager = BreakpointManager()
        self.debug_state = DebugState.IDLE
        self.current_file = None
        self.current_line = 0
        self.debug_thread: Optional[DebuggerThread] = None
        self.mutex = QMutex()
        
        self._current_strategy_name = None
        self._current_strategy_class = None
        self._current_strategy_instance = None
        self._current_strategy_params = {}
        self._current_data = None
        self._current_data_path = None
        self._using_code_editor = False
        
        self._init_theme_manager()
        self.init_ui()
        self._connect_theme_signals()

    def _init_theme_manager(self):
        """初始化主题管理器"""
        if self._theme_manager is None and THEME_AVAILABLE and get_theme_manager:
            try:
                self._theme_manager = get_theme_manager()
                logger.debug("成功获取主题管理器")
            except Exception as e:
                logger.warning(f"获取主题管理器失败: {e}")

    def _connect_theme_signals(self):
        """连接主题变化信号"""
        if self._theme_manager and hasattr(self._theme_manager, 'theme_changed'):
            try:
                self._theme_manager.theme_changed.connect(self._on_theme_changed)
            except Exception as e:
                logger.debug(f"连接主题信号失败: {e}")

    def _on_theme_changed(self, theme_name: str):
        """主题变化处理"""
        logger.debug(f"主题变化: {theme_name}")
        self._apply_theme()
        self.update_theme(self._theme_manager)

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QToolBar()

        start_action = QAction('开始调试', self)
        start_action.triggered.connect(self._start_debug)
        toolbar.addAction(start_action)

        stop_action = QAction('停止调试', self)
        stop_action.triggered.connect(self._stop_debug)
        toolbar.addAction(stop_action)

        toolbar.addSeparator()

        if STRATEGY_FRAMEWORK_AVAILABLE:
            self.strategy_combo = QComboBox()
            self.strategy_combo.setMinimumWidth(150)
            self.strategy_combo.setToolTip('选择要调试的策略')
            self._refresh_strategy_list()
            toolbar.addWidget(QLabel(' 策略: '))
            toolbar.addWidget(self.strategy_combo)

            load_strategy_action = QAction('加载策略代码', self)
            load_strategy_action.triggered.connect(self._load_strategy_code)
            load_strategy_action.setToolTip('加载选中策略的源代码进行调试')
            toolbar.addAction(load_strategy_action)

            load_data_action = QAction('加载数据', self)
            load_data_action.triggered.connect(self._load_data)
            load_data_action.setToolTip('从系统数据库或CSV文件加载数据用于策略调试')
            toolbar.addAction(load_data_action)
            
            csv_help_action = QAction('CSV格式帮助', self)
            csv_help_action.triggered.connect(self._show_csv_format_help)
            csv_help_action.setToolTip('查看CSV数据格式要求')
            toolbar.addAction(csv_help_action)

            toolbar.addSeparator()

        clear_bp_action = QAction('清除所有断点', self)
        clear_bp_action.triggered.connect(self._clear_all_breakpoints)
        toolbar.addAction(clear_bp_action)

        layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        if CODE_EDITOR_AVAILABLE:
            self.code_editor = CodeEditor(theme_manager=self._theme_manager)
            self.code_editor.breakpoints_changed.connect(self._on_breakpoints_changed_from_editor)
            self._using_code_editor = True
        else:
            self.code_editor = QPlainTextEdit()
            self.code_editor.setFont(QFont('Consolas', 10))
            self.code_editor.setLineWrapMode(QPlainTextEdit.NoWrap)
            self.code_editor.installEventFilter(self)
            self._using_code_editor = False
        left_layout.addWidget(self.code_editor)

        self.debug_controller = DebugController(theme_manager=self._theme_manager)
        self.debug_controller.continue_clicked.connect(self._continue)
        self.debug_controller.step_over_clicked.connect(self._step_over)
        self.debug_controller.step_into_clicked.connect(self._step_into)
        self.debug_controller.step_out_clicked.connect(self._step_out)
        self.debug_controller.stop_clicked.connect(self._stop_debug)
        self.debug_controller.restart_clicked.connect(self._restart)
        left_layout.addWidget(self.debug_controller)

        splitter.addWidget(left_panel)

        right_panel = QTabWidget()
        self._apply_tab_style(right_panel)

        self.var_viewer = VariableViewer(theme_manager=self._theme_manager)
        right_panel.addTab(self.var_viewer, '变量')

        self.stack_viewer = CallStackViewer(theme_manager=self._theme_manager)
        self.stack_viewer.frame_clicked.connect(self._on_frame_clicked)
        right_panel.addTab(self.stack_viewer, '调用栈')

        self.output_viewer = OutputViewer(theme_manager=self._theme_manager)
        right_panel.addTab(self.output_viewer, '输出')

        self.breakpoint_list = BreakpointListWidget(theme_manager=self._theme_manager)
        self.breakpoint_list.breakpoint_clicked.connect(self._on_breakpoint_list_clicked)
        self.breakpoint_list.breakpoint_toggled.connect(self._on_breakpoint_list_toggled)
        self.breakpoint_list.breakpoint_removed.connect(self._on_breakpoint_list_removed)
        right_panel.addTab(self.breakpoint_list, '断点')

        splitter.addWidget(right_panel)
        splitter.setSizes([600, 400])

        layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.status_bar.showMessage('就绪')
        layout.addWidget(self.status_bar)

        self.debug_controller.set_debugging_state(False)

    def _apply_tab_style(self, tab_widget):
        """应用标签页样式"""
        colors = self._get_theme_colors(self._theme_manager)
        tab_widget.setStyleSheet(self._generate_stylesheet('tab', colors))

    def _apply_theme(self):
        """应用主题"""
        if hasattr(self, 'code_editor') and not self._using_code_editor:
            colors = self._get_theme_colors(self._theme_manager)
            self.code_editor.setStyleSheet(f"""
                QPlainTextEdit {{
                    background-color: {colors['background']};
                    color: {colors['text']};
                    border: none;
                    font-family: Consolas;
                    font-size: 10pt;
                }}
            """)

    def update_theme(self, theme_manager):
        """更新主题"""
        self._theme_manager = theme_manager
        
        if hasattr(self, 'var_viewer'):
            self.var_viewer.update_theme(theme_manager)
        if hasattr(self, 'stack_viewer'):
            self.stack_viewer.update_theme(theme_manager)
        if hasattr(self, 'output_viewer'):
            self.output_viewer.update_theme(theme_manager)
        if hasattr(self, 'breakpoint_list'):
            self.breakpoint_list.update_theme(theme_manager)
        if hasattr(self, 'debug_controller'):
            self.debug_controller.update_theme(theme_manager)
        
        self._apply_theme()

    def load_code(self, code: str, file_path: str = None):
        """加载代码"""
        self.code_editor.setPlainText(code)
        self.current_file = file_path or '<string>'
        if not self._using_code_editor:
            self._update_breakpoint_markers()

    def eventFilter(self, obj, event):
        """事件过滤器 - 用于处理代码编辑器的鼠标事件"""
        if obj == self.code_editor and not self._using_code_editor:
            if event.type() == QEvent.MouseButtonPress:
                if event.modifiers() & Qt.ControlModifier:
                    cursor = self.code_editor.cursorForPosition(event.pos())
                    line = cursor.blockNumber() + 1
                    self.breakpoint_manager.toggle_breakpoint(self.current_file, line)
                    self._update_breakpoint_markers()
                    return True
        return super().eventFilter(obj, event)

    def _on_breakpoints_changed_from_editor(self, breakpoint_lines: set):
        """处理 CodeEditor 的断点变化信号"""
        if not self.current_file:
            return
        
        current_breakpoints = self.breakpoint_manager.get_breakpoints(self.current_file)
        
        for line in breakpoint_lines:
            if line not in current_breakpoints:
                self.breakpoint_manager.add_breakpoint(self.current_file, line)
        
        for line in current_breakpoints:
            if line not in breakpoint_lines:
                self.breakpoint_manager.remove_breakpoint(self.current_file, line)
        
        self._update_breakpoint_list()

    def _update_breakpoint_markers(self):
        """更新断点标记"""
        if not self.current_file:
            return

        breakpoints = self.breakpoint_manager.get_breakpoints(self.current_file)
        
        if not hasattr(self, '_last_breakpoints'):
            self._last_breakpoints = set()
        
        if breakpoints == self._last_breakpoints:
            return
        
        self._last_breakpoints = breakpoints.copy()
        
        if self._using_code_editor:
            if hasattr(self.code_editor, 'line_number_area') and self.code_editor.line_number_area:
                self.code_editor.line_number_area._breakpoint_lines = breakpoints.copy()
                self.code_editor.line_number_area.update()
        else:
            colors = self._get_theme_colors(self._theme_manager)
            
            cursor = self.code_editor.textCursor()
            cursor.select(QTextCursor.Document)
            
            format = QTextCharFormat()
            format.setBackground(QColor(colors['background']))
            cursor.mergeCharFormat(format)

            for line in breakpoints:
                block = self.code_editor.document().findBlockByNumber(line - 1)
                if block.isValid():
                    cursor = QTextCursor(block)
                    cursor.select(QTextCursor.LineUnderCursor)
                    
                    format = QTextCharFormat()
                    format.setBackground(QColor(colors['breakpoint']))
                    cursor.mergeCharFormat(format)
        
        self._update_breakpoint_list()

    def _update_breakpoint_list(self):
        """更新断点列表面板"""
        if hasattr(self, 'breakpoint_list') and self.breakpoint_list:
            self.breakpoint_list.update_breakpoints(
                self.breakpoint_manager.breakpoints,
                self.breakpoint_manager.enabled_breakpoints
            )

    def _on_breakpoint_list_clicked(self, file_path: str, line: int):
        """断点列表项点击 - 跳转到对应代码行"""
        if file_path == self.current_file:
            block = self.code_editor.document().findBlockByNumber(line - 1)
            if block.isValid():
                cursor = QTextCursor(block)
                self.code_editor.setTextCursor(cursor)
                self.code_editor.setFocus()
                self.code_editor.ensureCursorVisible()

    def _on_breakpoint_list_toggled(self, file_path: str, line: int, enabled: bool):
        """断点列表项启用/禁用切换"""
        if enabled:
            self.breakpoint_manager.enable_breakpoint(file_path, line)
        else:
            self.breakpoint_manager.disable_breakpoint(file_path, line)
        self._update_breakpoint_markers()

    def _on_breakpoint_list_removed(self, file_path: str, line: int):
        """断点列表项删除"""
        self.breakpoint_manager.remove_breakpoint(file_path, line)
        self._update_breakpoint_markers()

    def _highlight_current_line(self, line: int):
        """高亮当前行"""
        if hasattr(self, '_current_highlighted_line') and self._current_highlighted_line == line:
            return
        
        colors = self._get_theme_colors(self._theme_manager)
        
        if not self._using_code_editor:
            if hasattr(self, '_current_highlighted_line') and self._current_highlighted_line > 0:
                old_line = self._current_highlighted_line
                block = self.code_editor.document().findBlockByNumber(old_line - 1)
                if block.isValid():
                    cursor = QTextCursor(block)
                    cursor.select(QTextCursor.LineUnderCursor)
                    
                    format = QTextCharFormat()
                    format.setBackground(QColor(colors['background']))
                    cursor.mergeCharFormat(format)
        
        self._current_highlighted_line = line
        
        if not self._using_code_editor:
            self._update_breakpoint_markers()

            block = self.code_editor.document().findBlockByNumber(line - 1)
            if block.isValid():
                cursor = QTextCursor(block)
                cursor.select(QTextCursor.LineUnderCursor)
                
                format = QTextCharFormat()
                format.setBackground(QColor(colors['current_line']))
                cursor.mergeCharFormat(format)

        block = self.code_editor.document().findBlockByNumber(line - 1)
        if block.isValid():
            cursor = QTextCursor(block)
            self.code_editor.setTextCursor(cursor)
            self.code_editor.ensureCursorVisible()

    def _set_debug_state(self, state: DebugState):
        """设置调试状态"""
        self.debug_state = state
        self.debug_state_changed.emit(state.value)
        
        is_debugging = state not in [DebugState.IDLE, DebugState.STOPPED]
        is_paused = state == DebugState.PAUSED
        
        self.debug_controller.set_debugging_state(is_debugging, is_paused)
        
        if hasattr(self, 'status_bar'):
            state_messages = {
                DebugState.IDLE: '就绪',
                DebugState.RUNNING: '运行中...',
                DebugState.PAUSED: '已暂停',
                DebugState.STEP_OVER: '单步跳过中...',
                DebugState.STEP_INTO: '单步进入中...',
                DebugState.STEP_OUT: '单步退出中...',
                DebugState.STOPPED: '已停止',
            }
            self.status_bar.showMessage(state_messages.get(state, '未知状态'))

    def _start_debug(self):
        """开始调试"""
        if self.debug_state != DebugState.IDLE:
            return

        self._set_debug_state(DebugState.RUNNING)
        self.debug_started.emit()
        self.output_viewer.clear_output()
        self.output_viewer.append_output('调试会话已启动', '#4ec9b0')

        self._run_debug_session()

    def _stop_debug(self):
        """停止调试"""
        if self.debug_state == DebugState.IDLE:
            return

        if self.debug_thread and self.debug_thread.isRunning():
            self.debug_thread.stop()
            self.debug_thread.wait(2000)
            if self.debug_thread.isRunning():
                self.debug_thread.terminate()
                self.debug_thread.wait()

        self._set_debug_state(DebugState.STOPPED)
        self.debug_stopped.emit()
        self.output_viewer.append_output('调试会话已停止', '#f44747')

    def _run_debug_session(self):
        """运行调试会话"""
        code = self.code_editor.toPlainText()
        
        if not code.strip():
            self.output_viewer.append_output('错误: 代码为空', '#f44747')
            self._stop_debug()
            return

        context = {}
        if self._current_strategy_instance:
            context['_strategy_instance'] = self._current_strategy_instance
            context['_strategy_params'] = self._current_strategy_params
            self.output_viewer.append_output(f'策略上下文已注入: {self._current_strategy_name}', '#4ec9b0')
        
        if self._current_data is not None:
            context['_debug_data'] = self._current_data
            rows, cols = self._current_data.shape
            self.output_viewer.append_output(f'数据上下文已注入: {rows} 行, {cols} 列', '#4ec9b0')

        self.debug_thread = DebuggerThread(
            code=code,
            filename=self.current_file or '<string>',
            breakpoints=self.breakpoint_manager.enabled_breakpoints,
            context=context,
            parent=self
        )
        
        self.debug_thread.signal_breakpoint_hit.connect(self._on_breakpoint_hit)
        self.debug_thread.signal_step_complete.connect(self._on_step_complete)
        self.debug_thread.signal_execution_complete.connect(self._on_execution_complete)
        self.debug_thread.signal_error.connect(self._on_debug_error)
        self.debug_thread.signal_call_stack_update.connect(self._on_call_stack_update)
        self.debug_thread.signal_output.connect(self._on_debug_output)
        
        self.debug_thread.start()

    def _on_debug_output(self, text: str):
        """调试输出处理"""
        self.output_viewer.append_output(text, '#d4d4d4')

    def _on_breakpoint_hit(self, filename: str, line: int, vars_data: dict):
        """断点命中处理"""
        self._set_debug_state(DebugState.PAUSED)
        self.current_line = line
        self._highlight_current_line(line)
        
        self.output_viewer.append_output(f'断点命中: {os.path.basename(filename)}:{line}', '#f44747')
        self.breakpoint_hit.emit(filename, line)
        
        self._update_variables_display(vars_data)

    def _on_step_complete(self, filename: str, line: int, vars_data: dict):
        """单步完成处理"""
        self._set_debug_state(DebugState.PAUSED)
        self.current_line = line
        self._highlight_current_line(line)
        
        self.output_viewer.append_output(f'执行到: {os.path.basename(filename)}:{line}', '#4ec9b0')
        
        self._update_variables_display(vars_data)

    def _on_execution_complete(self, result: dict):
        """执行完成处理"""
        if result.get('stopped'):
            self.output_viewer.append_output('调试已停止', '#d4d4d4')
        else:
            self.output_viewer.append_output('代码执行完成', '#4ec9b0')
            
            if 'local_vars' in result:
                self._update_variables_display({
                    'local_vars': result['local_vars'],
                    'global_vars': result.get('global_vars', {})
                })
        
        self._set_debug_state(DebugState.STOPPED)
        self.debug_stopped.emit()

    def _on_debug_error(self, error_msg: str):
        """调试错误处理"""
        self.output_viewer.append_output(f'错误: {error_msg}', '#f44747')
        logger.error(f'调试错误: {error_msg}')
        self._set_debug_state(DebugState.STOPPED)

    def _on_call_stack_update(self, frames: list):
        """调用栈更新处理"""
        self.stack_viewer.update_call_stack(frames)

    def _update_variables_display(self, vars_data: dict):
        """更新变量显示"""
        local_vars = vars_data.get('local_vars', {})
        global_vars = vars_data.get('global_vars', {})
        self.var_viewer.update_variables(local_vars, global_vars)

    def _continue(self):
        """继续执行"""
        if self.debug_thread and self.debug_state == DebugState.PAUSED:
            self._set_debug_state(DebugState.RUNNING)
            self.output_viewer.append_output('继续执行...', '#d4d4d4')
            self.debug_thread.continue_execution()

    def _step_over(self):
        """单步跳过"""
        if self.debug_thread and self.debug_state == DebugState.PAUSED:
            self._set_debug_state(DebugState.STEP_OVER)
            self.output_viewer.append_output('单步跳过...', '#d4d4d4')
            self.debug_thread.step_over()

    def _step_into(self):
        """单步进入"""
        if self.debug_thread and self.debug_state == DebugState.PAUSED:
            self._set_debug_state(DebugState.STEP_INTO)
            self.output_viewer.append_output('单步进入...', '#d4d4d4')
            self.debug_thread.step_into()

    def _step_out(self):
        """单步退出"""
        if self.debug_thread and self.debug_state == DebugState.PAUSED:
            self._set_debug_state(DebugState.STEP_OUT)
            self.output_viewer.append_output('单步退出...', '#d4d4d4')
            self.debug_thread.step_out()

    def _restart(self):
        """重启调试"""
        self._stop_debug()
        QTimer.singleShot(100, self._start_debug)

    def _clear_all_breakpoints(self):
        """清除所有断点"""
        self.breakpoint_manager.clear_all_breakpoints()
        self._update_breakpoint_markers()
        self.status_bar.showMessage('已清除所有断点')

    def _refresh_strategy_list(self):
        """刷新策略列表"""
        if not STRATEGY_FRAMEWORK_AVAILABLE:
            return
        
        try:
            registry = get_strategy_registry()
            strategies = registry.list_strategies()
            self.strategy_combo.clear()
            self.strategy_combo.addItem('-- 选择策略 --', None)
            for strategy_name in strategies:
                self.strategy_combo.addItem(strategy_name, strategy_name)
        except Exception as e:
            logger.error(f"获取策略列表失败: {e}")
            self.strategy_combo.addItem('-- 获取失败 --', None)

    def _load_strategy_code(self):
        """加载选中策略的源代码"""
        if not STRATEGY_FRAMEWORK_AVAILABLE:
            self.output_viewer.append_output('策略框架不可用', '#f44747')
            return
        
        strategy_name = self.strategy_combo.currentData()
        if not strategy_name:
            self.output_viewer.append_output('请先选择一个策略', '#f44747')
            return
        
        try:
            registry = get_strategy_registry()
            strategy_class = registry.get_strategy(strategy_name)
            if strategy_class:
                source_code = inspect.getsource(strategy_class)
                self.load_code(source_code, f'{strategy_name}.py')
                self._current_strategy_name = strategy_name
                self._current_strategy_class = strategy_class
                
                factory = get_strategy_factory()
                self._current_strategy_instance = factory.create_strategy(strategy_name)
                
                if self._current_strategy_instance:
                    self._current_strategy_params = self._current_strategy_instance.get_parameters_dict()
                    param_info = f", {len(self._current_strategy_params)} 个参数"
                else:
                    param_info = ""
                    self._current_strategy_params = {}
                
                self.output_viewer.append_output(f'已加载策略: {strategy_name}{param_info}', '#4ec9b0')
                self.status_bar.showMessage(f'已加载策略: {strategy_name}{param_info}')
                
                self._show_parameter_config()
            else:
                self.output_viewer.append_output(f'未找到策略: {strategy_name}', '#f44747')
        except Exception as e:
            error_msg = f'加载策略代码失败: {str(e)}'
            self.output_viewer.append_output(error_msg, '#f44747')
            logger.error(error_msg)

    def _show_parameter_config(self):
        """显示策略参数配置对话框"""
        if not self._current_strategy_instance:
            return
        
        from PyQt5.QtWidgets import QDialog, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDialogButtonBox, QVBoxLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f'配置策略参数 - {self._current_strategy_name}')
        dialog.setMinimumWidth(400)
        
        layout = QFormLayout(dialog)
        
        param_widgets = {}
        
        for param_name, param in self._current_strategy_instance.parameters.items():
            if param.choices:
                widget = QComboBox()
                widget.addItems([str(c) for c in param.choices])
                if param.value is not None:
                    widget.setCurrentText(str(param.value))
            elif param.param_type == bool:
                widget = QComboBox()
                widget.addItems(['True', 'False'])
                widget.setCurrentText(str(param.value) if param.value is not None else 'False')
            elif param.param_type == int:
                widget = QSpinBox()
                widget.setRange(param.min_value or -999999, param.max_value or 999999)
                widget.setValue(param.value if param.value is not None else 0)
            elif param.param_type == float:
                widget = QDoubleSpinBox()
                widget.setRange(param.min_value or -999999.0, param.max_value or 999999.0)
                widget.setValue(param.value if param.value is not None else 0.0)
            else:
                widget = QLineEdit()
                widget.setText(str(param.value) if param.value is not None else '')
            
            if param.description:
                widget.setToolTip(param.description)
            
            layout.addRow(f'{param_name}:', widget)
            param_widgets[param_name] = widget
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addRow(button_box)
        
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        if dialog.exec_() == QDialog.Accepted:
            for param_name, widget in param_widgets.items():
                param = self._current_strategy_instance.parameters[param_name]
                if isinstance(widget, QComboBox):
                    if param.param_type == bool:
                        self._current_strategy_params[param_name] = widget.currentText() == 'True'
                    elif param.choices:
                        self._current_strategy_params[param_name] = param.choices[widget.currentIndex()]
                    else:
                        try:
                            self._current_strategy_params[param_name] = param.param_type(widget.currentText())
                        except:
                            self._current_strategy_params[param_name] = widget.currentText()
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    self._current_strategy_params[param_name] = widget.value()
                else:
                    try:
                        self._current_strategy_params[param_name] = param.param_type(widget.text())
                    except:
                        self._current_strategy_params[param_name] = widget.text()
            
            self.output_viewer.append_output(f'参数已更新: {self._current_strategy_params}', '#4ec9b0')
            self.status_bar.showMessage(f'参数已配置: {self._current_strategy_name}')
        else:
            self.output_viewer.append_output('参数配置已取消', '#d4d4d4')

    def _load_data(self):
        """加载数据 - 从系统数据库或文件"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QSpinBox, QDialogButtonBox, QFileDialog
        import pandas as pd
        
        dialog = QDialog(self)
        dialog.setWindowTitle('加载数据')
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel('数据源:'))
        source_combo = QComboBox()
        source_combo.addItems(['从系统数据库加载', '从CSV文件加载'])
        source_layout.addWidget(source_combo)
        layout.addLayout(source_layout)
        
        stacked_widget = QWidget()
        stacked_layout = QVBoxLayout(stacked_widget)
        stacked_layout.setContentsMargins(0, 0, 0, 0)
        
        system_widget = QWidget()
        system_layout = QVBoxLayout(system_widget)
        
        asset_type_layout = QHBoxLayout()
        asset_type_layout.addWidget(QLabel('资产类型:'))
        asset_type_combo = QComboBox()
        if AssetType:
            for at in AssetType:
                asset_type_combo.addItem(at.value, at)
        asset_type_layout.addWidget(asset_type_combo)
        system_layout.addLayout(asset_type_layout)
        
        stock_layout = QHBoxLayout()
        stock_layout.addWidget(QLabel('股票代码:'))
        stock_code_edit = QLineEdit()
        stock_code_edit.setPlaceholderText('例如: 000001.SZ')
        stock_layout.addWidget(stock_code_edit)
        system_layout.addLayout(stock_layout)
        
        period_layout = QHBoxLayout()
        period_layout.addWidget(QLabel('周期:'))
        period_combo = QComboBox()
        period_combo.addItems(['D', 'W', 'M'])
        period_layout.addWidget(period_combo)
        period_layout.addWidget(QLabel('  数据条数:'))
        count_spin = QSpinBox()
        count_spin.setRange(1, 10000)
        count_spin.setValue(365)
        period_layout.addWidget(count_spin)
        system_layout.addLayout(period_layout)
        
        stacked_layout.addWidget(system_widget)
        
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        file_button = QPushButton('选择CSV文件')
        file_label = QLabel('未选择文件')
        file_layout.addWidget(file_button)
        file_layout.addWidget(file_label)
        
        stacked_layout.addWidget(file_widget)
        
        layout.addWidget(stacked_widget)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(button_box)
        
        def update_stacked(index):
            system_widget.setVisible(index == 0)
            file_widget.setVisible(index == 1)
        
        source_combo.currentIndexChanged.connect(update_stacked)
        
        selected_file = [None]
        def select_file():
            path, _ = QFileDialog.getOpenFileName(dialog, '选择CSV文件', '', 'CSV Files (*.csv);;All Files (*)')
            if path:
                selected_file[0] = path
                file_label.setText(os.path.basename(path))
        
        file_button.clicked.connect(select_file)
        
        update_stacked(0)
        
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        if dialog.exec_() != QDialog.Accepted:
            return
        
        source = source_combo.currentIndex()
        
        try:
            if source == 0:
                if not StockService or not get_stock_service:
                    self.output_viewer.append_output('股票服务不可用', '#f44747')
                    return
                
                stock_code = stock_code_edit.text().strip()
                if not stock_code:
                    self.output_viewer.append_output('请输入股票代码', '#f44747')
                    return
                
                stock_service = get_stock_service()
                asset_type = asset_type_combo.currentData()
                period = period_combo.currentText()
                count = count_spin.value()
                
                if asset_type and asset_type != AssetType.STOCK_A:
                    from core.services.unified_data_manager import get_unified_data_manager
                    data_manager = get_unified_data_manager()
                    if data_manager:
                        data = data_manager.get_kdata(stock_code, period, count, asset_type=asset_type)
                    else:
                        self.output_viewer.append_output('统一数据管理器不可用', '#f44747')
                        return
                else:
                    data = stock_service.get_kdata(stock_code, period, count)
                
                if data is None or data.empty:
                    self.output_viewer.append_output(f'未找到数据: {stock_code}', '#f44747')
                    return
                
                self._current_data = data
                self._current_data_path = f'系统数据库: {stock_code}'
                
                rows, cols = data.shape
                self.output_viewer.append_output(f'已加载数据: {stock_code} ({rows} 行, {cols} 列)', '#4ec9b0')
                self.output_viewer.append_output(f'数据列: {list(data.columns)}', '#d4d4d4')
                self.status_bar.showMessage(f'已加载数据: {stock_code}')
                
            else:
                file_path = selected_file[0]
                if not file_path:
                    self.output_viewer.append_output('请选择CSV文件', '#f44747')
                    return
                
                data = pd.read_csv(file_path)
                
                if self._current_strategy_instance:
                    valid, errors = self._current_strategy_instance.validate_data(data)
                    if not valid:
                        self.output_viewer.append_output(f'数据验证失败: {errors}', '#f44747')
                        self.status_bar.showMessage('数据验证失败')
                        return
                
                self._current_data = data
                self._current_data_path = file_path
                
                rows, cols = data.shape
                self.output_viewer.append_output(f'已加载数据: {os.path.basename(file_path)} ({rows} 行, {cols} 列)', '#4ec9b0')
                self.output_viewer.append_output(f'数据列: {list(data.columns)}', '#d4d4d4')
                self.status_bar.showMessage(f'已加载数据: {file_path}')
            
            if self._current_strategy_instance and self._current_data is not None:
                valid, errors = self._current_strategy_instance.validate_data(self._current_data)
                if not valid:
                    self.output_viewer.append_output(f'警告: 数据可能不满足策略要求: {errors}', '#f44747')
                    
        except Exception as e:
            error_msg = f'加载数据失败: {str(e)}'
            self.output_viewer.append_output(error_msg, '#f44747')
            logger.error(error_msg)

    def _show_csv_format_help(self):
        """显示CSV格式帮助对话框"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle('CSV数据格式说明')
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout(dialog)
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
<h2>CSV数据格式要求</h2>

<h3>必需列（基础OHLCV）</h3>
<table border="1" cellpadding="5">
<tr><th>列名</th><th>类型</th><th>说明</th></tr>
<tr><td>open</td><td>数值</td><td>开盘价</td></tr>
<tr><td>high</td><td>数值</td><td>最高价</td></tr>
<tr><td>low</td><td>数值</td><td>最低价</td></tr>
<tr><td>close</td><td>数值</td><td>收盘价</td></tr>
<tr><td>volume</td><td>整数</td><td>成交量</td></tr>
</table>

<h3>可选列（扩展数据）</h3>
<table border="1" cellpadding="5">
<tr><th>列名</th><th>类型</th><th>说明</th></tr>
<tr><td>timestamp</td><td>日期时间</td><td>时间戳（如：2024-01-01）</td></tr>
<tr><td>date</td><td>日期</td><td>日期（如：2024-01-01）</td></tr>
<tr><td>amount</td><td>数值</td><td>成交额</td></tr>
<tr><td>turnover</td><td>数值</td><td>换手率</td></tr>
<tr><td>adj_close</td><td>数值</td><td>复权价</td></tr>
<tr><td>change</td><td>数值</td><td>涨跌额</td></tr>
<tr><td>change_pct</td><td>数值</td><td>涨跌幅(%)</td></tr>
</table>

<h3>示例CSV内容</h3>
<pre>
timestamp,open,high,low,close,volume,amount
2024-01-02,10.50,10.80,10.30,10.75,1000000,10750000
2024-01-03,10.75,11.00,10.60,10.90,1200000,13080000
2024-01-04,10.90,10.95,10.50,10.60,900000,9540000
</pre>

<h3>注意事项</h3>
<ul>
<li>第一行必须是列标题（表头）</li>
<li>日期格式建议使用 YYYY-MM-DD</li>
<li>数值列不应包含逗号等格式化符号</li>
<li>数据应按时间升序排列</li>
</ul>

<h3>数据验证</h3>
<p>加载CSV后，系统会自动验证：</p>
<ul>
<li>必需列是否存在</li>
<li>数据是否为空</li>
<li>数值类型是否正确</li>
</ul>
        """)
        
        layout.addWidget(help_text)
        
        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec_()

    def _on_frame_clicked(self, frame_index: int):
        """帧点击"""
        self.output_viewer.append_output(f'切换到帧 {frame_index}', '#d4d4d4')

    def closeEvent(self, event):
        """关闭事件处理"""
        if self.debug_thread and self.debug_thread.isRunning():
            self.debug_thread.stop()
            self.debug_thread.wait(2000)
        
        if self._theme_manager and hasattr(self._theme_manager, 'theme_changed'):
            try:
                self._theme_manager.theme_changed.disconnect(self._on_theme_changed)
            except:
                pass
        
        super().closeEvent(event)
