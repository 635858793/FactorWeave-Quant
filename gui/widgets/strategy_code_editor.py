"""
策略代码编辑器组件 - 重构版
集成系统主题管理，提供现代化的代码编辑体验
功能：语法高亮、代码补全、错误提示、行号、Minimap、多标签页
"""
import os
import re
import sys
import threading
import queue
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger
from concurrent.futures import ThreadPoolExecutor
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLabel,
    QPushButton, QToolBar, QAction, QStatusBar, QFileDialog,
    QMessageBox, QSplitter, QListWidget, QListWidgetItem, QTabWidget,
    QComboBox, QSpinBox, QGroupBox, QFormLayout, QDialog, QTextEdit,
    QFrame, QSizePolicy, QMenu, QShortcut, QApplication, QListView,
    QAbstractItemView, QStyledItemDelegate, QStyleOptionViewItem, QStyle
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRegExp, QRect, QSize, QPoint, QStringListModel, QEvent, QThread, QMutex
from PyQt5.QtGui import (
    QFont, QTextCharFormat, QSyntaxHighlighter, QColor, QTextCursor,
    QKeySequence, QIcon, QPainter, QTextBlock, QPen, QBrush, QLinearGradient,
    QFontMetrics, QStandardItemModel, QStandardItem
)

try:
    from utils.theme import get_theme_manager, Theme
    from gui.styles.unified_design_system import DesignTokens, ColorScheme, StyleSheetGenerator
    THEME_AVAILABLE = True
except ImportError as e:
    logger.warning(f"主题模块导入失败: {e}")
    THEME_AVAILABLE = False


class AsyncCompletionWorker(QThread):
    """异步补全工作线程 - 完全独立的线程处理补全请求"""
    
    completion_ready = pyqtSignal(int, list, str, str)  # request_id, completions, prefix, trigger_type
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._request_queue = queue.Queue()
        self._running = True
        self._current_request_id = 0
        self._mutex = QMutex()
        
        self._init_completion_data()
        
    def _init_completion_data(self):
        """初始化补全数据"""
        self._python_keywords = [
            'and', 'as', 'assert', 'async', 'await', 'break', 'class',
            'continue', 'def', 'del', 'elif', 'else', 'except', 'False',
            'finally', 'for', 'from', 'global', 'if', 'import', 'in',
            'is', 'lambda', 'None', 'nonlocal', 'not', 'or', 'pass',
            'raise', 'return', 'True', 'try', 'while', 'with', 'yield'
        ]
        self._python_builtins = [
            'abs', 'all', 'any', 'bin', 'bool', 'bytearray', 'bytes',
            'callable', 'chr', 'classmethod', 'compile', 'complex',
            'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval',
            'exec', 'filter', 'float', 'format', 'frozenset', 'getattr',
            'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input',
            'int', 'isinstance', 'issubclass', 'iter', 'len', 'list',
            'locals', 'map', 'max', 'memoryview', 'min', 'next', 'object',
            'oct', 'open', 'ord', 'pow', 'print', 'property', 'range',
            'repr', 'reversed', 'round', 'set', 'setattr', 'slice',
            'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple',
            'type', 'vars', 'zip'
        ]
        self._hikyuu_api = [
            'Stock', 'Query', 'KQuery', 'TimeLine', 'TransList', 
            'Block', 'BlockList', 'StockManager', 'StockType',
            'Parameter', 'PriceList', 'Datetime', 'TimeDelta',
            'Strategy', 'System', 'TradeManager', 'TradeRecord',
            'PositionRecord', 'FundsRecord', 'CostRecord',
            'Indicator', 'KData', 'PriceList', 'DatetimeList',
            'MA', 'EMA', 'SMA', 'MACD', 'KDJ', 'RSI', 'BOLL',
            'ATR', 'ADX', 'OBV', 'VOL', 'VOLUME', 'CLOSE', 'OPEN',
            'HIGH', 'LOW', 'AMO', 'K', 'D', 'J',
            'CVAL', 'REF', 'HHV', 'LLV', 'SUM', 'COUNT', 'IF',
            'CROSS', 'ABS', 'MAX', 'MIN', 'STD', 'VAR',
            'get_stock', 'get_trading_calendar', 'get_version',
            'hku_config_init', 'hku_init', 'set_config',
            'get_context', 'set_context', 'run_strategy',
        ]
        self._system_strategy_api = [
            'BaseStrategy', 'StrategyType', 'StrategyStatus', 'StrategySignal',
            'StrategyParameter', 'StrategyInfo', 'StrategyRegistry', 'StrategyFactory',
            'StrategyEngine', 'StrategyDatabaseManager', 'StrategyHotReloader',
            'StrategyDependencyManager', 'StrategyParameterManager', 'StrategyLifecycleManager',
            'create_strategy', 'execute_strategy', 'list_strategies', 'list_available_strategies',
            'get_strategy_info', 'optimize_strategy_parameters', 'evaluate_strategy_performance',
            'initialize_strategy_system', 'get_system_managers', 'get_system_stats',
            'shutdown_strategy_system', 'get_strategy_registry', 'get_strategy_factory',
            'get_strategy_engine', 'get_strategy_database_manager', 'get_strategy_hot_reloader',
            'get_strategy_dependency_manager', 'get_parameter_manager', 'get_lifecycle_manager',
            'initialize_strategy_factory', 'initialize_strategy_engine', 'initialize_strategy_database',
            'initialize_parameter_manager', 'initialize_lifecycle_manager',
            'register_strategy', 'process_pending_registrations',
            'publish_strategy_event', 'subscribe_event', 'unsubscribe_event',
            'create_strategy_started_event', 'create_strategy_stopped_event',
            'create_signal_generated_event', 'create_strategy_error_event',
            'get_event_metrics', 'reset_event_metrics', 'get_strategy_event_types',
        ]
        self._system_service_api = [
            'get_strategy_service', 'get_database_service', 'get_event_bus',
            'get_data_service', 'get_config_service', 'get_cache_service',
            'get_logger', 'get_config', 'set_config',
            'DatabaseService', 'EventBus', 'DataService', 'ConfigService',
            'CacheService', 'LoggerService',
        ]
        self._strategy_base_methods = [
            'generate_signals', '_init_default_parameters', 'add_parameter',
            'set_parameter', 'get_parameter', 'get_parameters_dict',
            'validate_parameters', 'start', 'stop', 'reset',
            'get_strategy_info', 'get_performance_metrics', 'update_performance_metrics',
            'publish_event', 'subscribe_event', 'unsubscribe_event',
            '_generate_signals_with_event', '_start_with_event', '_stop_with_event',
            '_trigger_signal_generated_event', '_trigger_strategy_started_event',
            '_trigger_strategy_stopped_event', '_trigger_strategy_error_event',
            '_clear_cache', '_get_event_bus',
        ]
        self._numpy_attrs = [
            'array', 'zeros', 'ones', 'empty', 'arange', 'linspace',
            'reshape', 'transpose', 'dot', 'matmul', 'sum', 'mean',
            'std', 'var', 'min', 'max', 'argmin', 'argmax', 'sort',
            'concatenate', 'stack', 'split', 'vstack', 'hstack',
            'sin', 'cos', 'tan', 'exp', 'log', 'sqrt', 'abs',
            'floor', 'ceil', 'round', 'clip', 'where', 'select',
            'random', 'linalg', 'fft', 'polynomial', 'testing',
            'ndarray', 'dtype', 'int32', 'int64', 'float32', 'float64',
            'inf', 'nan', 'pi', 'e', 'newaxis', 's_', 'ix_', 'r_', 'c_',
        ]
        self._pandas_attrs = [
            'DataFrame', 'Series', 'read_csv', 'read_excel', 'read_sql',
            'to_csv', 'to_excel', 'concat', 'merge', 'join', 'groupby',
            'pivot_table', 'melt', 'crosstab', 'cut', 'qcut',
            'to_datetime', 'to_timedelta', 'date_range', 'bdate_range',
            'isna', 'isnull', 'notna', 'notnull', 'fillna', 'dropna',
            'drop_duplicates', 'sort_values', 'sort_index', 'reset_index',
            'set_index', 'apply', 'applymap', 'map', 'agg', 'transform',
            'rolling', 'expanding', 'ewm', 'shift', 'diff', 'pct_change',
            'plot', 'hist', 'boxplot', 'scatter_matrix',
        ]
        self._matplotlib_attrs = [
            'plot', 'scatter', 'bar', 'barh', 'hist', 'pie', 'boxplot',
            'subplot', 'subplots', 'figure', 'axes', 'xlabel', 'ylabel',
            'title', 'legend', 'grid', 'xlim', 'ylim', 'xticks', 'yticks',
            'savefig', 'show', 'close', 'clf', 'cla', 'tight_layout',
            'imshow', 'colorbar', 'contour', 'contourf', 'pcolor', 'pcolormesh',
            'annotate', 'text', 'arrow', 'axhline', 'axvline', 'hlines', 'vlines',
        ]
        
        self._module_map = {
            'np': self._numpy_attrs,
            'numpy': self._numpy_attrs,
            'pd': self._pandas_attrs,
            'pandas': self._pandas_attrs,
            'plt': self._matplotlib_attrs,
            'matplotlib.pyplot': self._matplotlib_attrs,
            'hku': self._hikyuu_api,
            'hikyuu': self._hikyuu_api,
            'core.strategy': self._system_strategy_api,
            'core.services': self._system_service_api,
            'BaseStrategy': self._strategy_base_methods,
        }
        
    def request_completion(self, code: str, line: int, column: int, prefix: str, trigger_type: str):
        """请求补全 - 线程安全"""
        self._mutex.lock()
        self._current_request_id += 1
        request_id = self._current_request_id
        self._mutex.unlock()
        
        self._request_queue.put((request_id, code, line, column, prefix, trigger_type))
        return request_id
        
    def stop(self):
        """停止工作线程"""
        self._running = False
        self._request_queue.put((None, None, None, None, None, None))
        
    def run(self):
        """工作线程主循环"""
        while self._running:
            try:
                request = self._request_queue.get(timeout=0.1)
                if request[0] is None:
                    break
                    
                request_id, code, line, column, prefix, trigger_type = request
                
                completions = self._compute_completions(code, line, column, prefix)
                
                self.completion_ready.emit(request_id, completions, prefix, trigger_type)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.debug(f"Completion worker error: {e}")
                
    def _compute_completions(self, code: str, line: int, column: int, prefix: str) -> List[str]:
        """计算补全项 - 在工作线程中执行"""
        completions = []
        prefix_lower = prefix.lower() if prefix else ''

        text_before = self._get_text_before_cursor(code, line, column)

        if '.' in text_before:
            completions.extend(self._get_module_completions(text_before, prefix))

        seen = set(completions)
        is_match = (lambda w: not prefix_lower or w.lower().startswith(prefix_lower))
        all_sources = (
            self._python_keywords, self._python_builtins, self._hikyuu_api,
            self._system_strategy_api, self._system_service_api,
        )
        for source in all_sources:
            items = [w for w in source if is_match(w) and w not in seen]
            completions.extend(items)
            seen.update(items)

        try:
            import jedi
            script = jedi.Script(code=code)
            jedi_completions = script.complete(line, column)
            jedi_items = [c.name for c in jedi_completions[:20]
                          if c.name not in seen and is_match(c.name)]
            completions.extend(jedi_items)
            seen.update(jedi_items)
        except Exception:
            pass

        words_in_code = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code))
        code_items = [w for w in words_in_code
                      if is_match(w) and w not in seen and len(w) > 2]
        completions.extend(code_items)

        return completions[:50]
        
    def _get_text_before_cursor(self, code: str, line: int, column: int) -> str:
        """获取光标前的文本"""
        lines = code.split('\n')
        if line <= len(lines):
            return lines[line - 1][:column]
        return ''
        
    def _get_module_completions(self, text_before: str, prefix: str) -> List[str]:
        """获取模块属性补全"""
        match = re.search(r'(\w+(?:\.\w+)*)\.$', text_before)
        if match:
            module_name = match.group(1)
            attrs = self._module_map.get(module_name, [])
            prefix_lower = prefix.lower() if prefix else ''
            return [attr for attr in attrs if not prefix_lower or attr.lower().startswith(prefix_lower)]
        return []


class CompletionPopup(QWidget):
    """代码补全弹窗组件 - 轻量级实现"""
    
    completion_selected = pyqtSignal(str)
    
    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFocusPolicy(Qt.NoFocus)
        
        self._items = []
        self._current_index = -1
        self._min_width = 280
        self._max_visible_items = 10
        self._item_height = 24
        self._is_visible = False
        
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        
        self._list_widget = QListWidget(self)
        self._list_widget.setFocusPolicy(Qt.NoFocus)
        self._list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._list_widget.itemClicked.connect(self._on_item_clicked)
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._layout.addWidget(self._list_widget)
        
        self._apply_theme()
        
    def _apply_theme(self):
        if self.theme_manager:
            colors = self.theme_manager.get_theme_colors()
            bg_color = colors.get('sidebar_bg', colors.get('background', '#2d2d2d'))
            text_color = colors.get('text', '#d4d4d4')
            selected_bg = colors.get('selected_bg', '#264f78')
            border_color = colors.get('border', '#3c3c3c')
            highlight_color = colors.get('highlight', '#1976d2')
        else:
            bg_color = '#2d2d2d'
            text_color = '#d4d4d4'
            selected_bg = '#264f78'
            border_color = '#3c3c3c'
            highlight_color = '#1976d2'
            
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
        """)
        
        self._list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {bg_color};
                border: none;
                outline: none;
                color: {text_color};
                font-family: 'Segoe UI', Consolas;
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 4px 12px;
                min-height: 20px;
            }}
            QListWidget::item:hover {{
                background-color: {selected_bg};
            }}
            QListWidget::item:selected {{
                background-color: {highlight_color};
                color: white;
            }}
            QScrollBar:vertical {{
                background-color: {bg_color};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {border_color};
                border-radius: 4px;
                min-height: 20px;
            }}
        """)
        
    def set_completions(self, completions: List[Dict]):
        self._items = []
        self._list_widget.clear()
        for item in completions:
            name = item.get('name', '')
            item_type = item.get('type', 'unknown')
            
            icon_map = {
                'function': '𝑓',
                'class': 'ℂ',
                'module': '📦',
                'keyword': '🔑',
                'instance': '📌',
                'statement': '📝',
                'param': '⚙️',
            }
            icon = icon_map.get(item_type, '•')
            display_text = f"{icon} {name}"
            
            list_item = QListWidgetItem(display_text, self._list_widget)
            list_item.setData(Qt.UserRole, name)
            self._items.append(name)
            
        self._update_size()
        
    def set_simple_completions(self, words: List[str]):
        self._items = []
        self._list_widget.clear()
        for word in words:
            list_item = QListWidgetItem(word, self._list_widget)
            list_item.setData(Qt.UserRole, word)
            self._items.append(word)
        self._update_size()
        
    def _update_size(self):
        count = len(self._items)
        visible_count = min(count, self._max_visible_items)
        height = visible_count * self._item_height + 10
        self.setFixedSize(self._min_width, height)
        
    def show_popup(self, pos: QPoint):
        if len(self._items) > 0:
            self._current_index = 0
            self._list_widget.setCurrentRow(0)
            self.move(pos)
            self._is_visible = True
            self.show()
            
    def hide_popup(self):
        try:
            self._current_index = -1
            self._is_visible = False
            self._items = []
            self._list_widget.clear()
            self.setVisible(False)
        except Exception as e:
            logger.debug(f"Hide popup error: {e}")
        
    def is_popup_visible(self):
        return self._is_visible and self.isVisible()
        
    def select_next(self):
        if len(self._items) == 0:
            return
        self._current_index = min(self._current_index + 1, len(self._items) - 1)
        self._list_widget.setCurrentRow(self._current_index)
        
    def select_previous(self):
        if len(self._items) == 0:
            return
        self._current_index = max(self._current_index - 1, 0)
        self._list_widget.setCurrentRow(self._current_index)
        
    def get_current_text(self) -> Optional[str]:
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return None
        
    def _on_item_clicked(self, item):
        pass
        
    def _on_item_double_clicked(self, item):
        text = item.data(Qt.UserRole)
        if text:
            self.completion_selected.emit(text)
        self.hide_popup()
        
    def update_theme(self, theme_manager):
        self.theme_manager = theme_manager
        self._apply_theme()


class LineNumberArea(QWidget):
    """行号区域组件"""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setMouseTracking(True)
        self._clickable_lines = set()
        self._breakpoint_lines = set()

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        if self.editor is None:
            painter = QPainter(self)
            theme_manager = self._get_theme_manager() if hasattr(self, '_get_theme_manager') else None
            if theme_manager:
                colors = theme_manager.get_theme_colors()
                bg_color = colors.get('sidebar_bg', colors.get('background', '#2d2d2d'))
            else:
                bg_color = '#2d2d2d'
            painter.fillRect(self.rect(), QColor(bg_color))
            painter.end()
            return
        try:
            self.editor.line_number_area_paint_event(event)
        except Exception as e:
            logger.debug(f"LineNumberArea paint error: {e}")

    def mousePressEvent(self, event):
        line = self.editor.cursorForPosition(QPoint(0, event.y())).blockNumber() + 1
        if event.button() == Qt.LeftButton:
            if line in self._breakpoint_lines:
                self._breakpoint_lines.discard(line)
            else:
                self._breakpoint_lines.add(line)
            self.update()
            self.editor.breakpoints_changed.emit(self._breakpoint_lines)

    def toggle_breakpoint(self, line: int):
        if line in self._breakpoint_lines:
            self._breakpoint_lines.discard(line)
        else:
            self._breakpoint_lines.add(line)
        self.update()

    def clear_breakpoints(self):
        self._breakpoint_lines.clear()
        self.update()


class MinimapWidget(QWidget):
    """代码缩略图组件"""

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setFixedWidth(100)
        self._scale_factor = 0.15
        self._visible_area_ratio = 0.0
        self._visible_area_start = 0.0
        self.setMouseTracking(True)

    def update_visible_area(self, start_ratio: float, ratio: float):
        self._visible_area_start = start_ratio
        self._visible_area_ratio = ratio
        self.update()

    def paintEvent(self, event):
        if self.editor is None:
            painter = QPainter(self)
            theme_manager = self._get_theme_manager()
            if theme_manager:
                colors = theme_manager.get_theme_colors()
                bg_color = colors.get('chart_background', colors.get('background', '#1e1e1e'))
            else:
                bg_color = '#1e1e1e'
            painter.fillRect(self.rect(), QColor(bg_color))
            painter.end()
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        theme_manager = self._get_theme_manager()
        if theme_manager:
            colors = theme_manager.get_theme_colors()
            bg_color = colors.get('chart_background', colors.get('background', '#1e1e1e'))
            text_color = colors.get('text', '#d4d4d4')
            highlight_color = colors.get('highlight', '#1976d2')
        else:
            bg_color = '#1e1e1e'
            text_color = '#d4d4d4'
            highlight_color = '#1976d2'

        painter.fillRect(self.rect(), QColor(bg_color))

        try:
            doc = self.editor.document()
            if doc is None:
                painter.end()
                return
                
            block = doc.firstBlock()
            y = 0
            font = QFont('Consolas', 2)
            painter.setFont(font)

            while block.isValid():
                text = block.text()
                if text.strip():
                    painter.setPen(QColor(text_color))
                    painter.drawText(2, y + 4, text[:80])
                y += 3
                block = block.next()
                if y > self.height():
                    break

            visible_height = self.height() * self._visible_area_ratio
            visible_y = self.height() * self._visible_area_start
            painter.fillRect(
                QRect(0, int(visible_y), self.width(), int(visible_height)),
                QColor(highlight_color + '40')
            )
        except Exception as e:
            logger.debug(f"Minimap paint error: {e}")
        finally:
            painter.end()

    def _get_theme_manager(self):
        if THEME_AVAILABLE:
            try:
                return get_theme_manager()
            except Exception:
                pass
        return None


class PythonSyntaxHighlighter(QSyntaxHighlighter):
    """Python语法高亮器 - 支持主题"""

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._init_formats()
        self._init_rules()

    def _get_color(self, key: str, default: str) -> QColor:
        if self.theme_manager:
            colors = self.theme_manager.get_theme_colors()
            color = colors.get(key, default)
            return QColor(color)
        return QColor(default)

    def _init_formats(self):
        self.formats = {}

        self.formats['keyword'] = QTextCharFormat()
        self.formats['keyword'].setForeground(self._get_color('keyword', '#ff79c6'))
        self.formats['keyword'].setFontWeight(QFont.Bold)

        self.formats['builtins'] = QTextCharFormat()
        self.formats['builtins'].setForeground(self._get_color('builtins', '#8be9fd'))

        self.formats['string'] = QTextCharFormat()
        self.formats['string'].setForeground(self._get_color('string', '#f1fa8c'))

        self.formats['comment'] = QTextCharFormat()
        self.formats['comment'].setForeground(self._get_color('comment', '#6272a4'))
        self.formats['comment'].setFontItalic(True)

        self.formats['number'] = QTextCharFormat()
        self.formats['number'].setForeground(self._get_color('number', '#bd93f9'))

        self.formats['function'] = QTextCharFormat()
        self.formats['function'].setForeground(self._get_color('function', '#50fa7b'))

        self.formats['class'] = QTextCharFormat()
        self.formats['class'].setForeground(self._get_color('class', '#ffb86c'))

        self.formats['decorator'] = QTextCharFormat()
        self.formats['decorator'].setForeground(self._get_color('decorator', '#ff79c6'))

        self.formats['operator'] = QTextCharFormat()
        self.formats['operator'].setForeground(self._get_color('operator', '#ff79c6'))

        self.formats['self'] = QTextCharFormat()
        self.formats['self'].setForeground(self._get_color('self', '#ff5555'))

    def _init_rules(self):
        self.rules = []

        keywords = [
            'and', 'as', 'assert', 'async', 'await', 'break', 'class',
            'continue', 'def', 'del', 'elif', 'else', 'except', 'False',
            'finally', 'for', 'from', 'global', 'if', 'import', 'in',
            'is', 'lambda', 'None', 'nonlocal', 'not', 'or', 'pass',
            'raise', 'return', 'True', 'try', 'while', 'with', 'yield'
        ]

        builtins = [
            'abs', 'all', 'any', 'bin', 'bool', 'bytearray', 'bytes',
            'callable', 'chr', 'classmethod', 'compile', 'complex',
            'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval',
            'exec', 'filter', 'float', 'format', 'frozenset', 'getattr',
            'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input',
            'int', 'isinstance', 'issubclass', 'iter', 'len', 'list',
            'locals', 'map', 'max', 'memoryview', 'min', 'next', 'object',
            'oct', 'open', 'ord', 'pow', 'print', 'property', 'range',
            'repr', 'reversed', 'round', 'set', 'setattr', 'slice',
            'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple',
            'type', 'vars', 'zip'
        ]

        for word in keywords:
            pattern = QRegExp(r'\b' + word + r'\b')
            self.rules.append((pattern, self.formats['keyword']))

        for word in builtins:
            pattern = QRegExp(r'\b' + word + r'\b')
            self.rules.append((pattern, self.formats['builtins']))

        self.rules.append((QRegExp(r'\bself\b'), self.formats['self']))
        self.rules.append((QRegExp(r'"[^"\\]*(\\.[^"\\]*)*"'), self.formats['string']))
        self.rules.append((QRegExp(r"'[^'\\]*(\\.[^'\\]*)*'"), self.formats['string']))
        self.rules.append((QRegExp(r'""".*"""'), self.formats['string']))
        self.rules.append((QRegExp(r"'''.*'''"), self.formats['string']))
        self.rules.append((QRegExp(r'#[^\n]*'), self.formats['comment']))
        self.rules.append((QRegExp(r'\b[0-9]+\.?[0-9]*\b'), self.formats['number']))
        self.rules.append((QRegExp(r'\b0[xX][0-9A-Fa-f]+\b'), self.formats['number']))
        self.rules.append((QRegExp(r'\b[A-Za-z_][A-Za-z0-9_]*(?=\()'), self.formats['function']))
        self.rules.append((QRegExp(r'\bclass\s+([A-Za-z_][A-Za-z0-9_]*)'), self.formats['class']))
        self.rules.append((QRegExp(r'@[A-Za-z_][A-Za-z0-9_]*'), self.formats['decorator']))
        self.rules.append((QRegExp(r'[+\-*/%&|^~<>!=]'), self.formats['operator']))

    def highlightBlock(self, text):
        for pattern, format in self.rules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                self.setFormat(index, length, format)
                index = pattern.indexIn(text, index + length)

    def update_theme(self, theme_manager):
        self.theme_manager = theme_manager
        self._init_formats()
        self.rehighlight()


class CodeEditor(QPlainTextEdit):
    """代码编辑器 - 带行号和Minimap"""

    breakpoints_changed = pyqtSignal(set)

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.setFont(QFont('Consolas', 11))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(40)

        self.highlighter = PythonSyntaxHighlighter(self.document(), theme_manager)

        self.line_number_area = LineNumberArea(self)
        self.minimap = MinimapWidget(self, self)

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.verticalScrollBar().valueChanged.connect(self._update_minimap)

        self._update_line_number_area_width()
        self._init_theme()

        self.completion_timer = QTimer()
        self.completion_timer.setSingleShot(True)
        self.completion_timer.timeout.connect(self._trigger_completion)

        self.error_timer = QTimer()
        self.error_timer.setSingleShot(True)
        self.error_timer.timeout.connect(self._check_errors)

        self.textChanged.connect(self._on_text_changed)

        self.completion_callback = None
        self.error_callback = None
        self._cached_code_hash = None
        self._cached_completions = None
        self._last_completion_position = None
        self._debounce_interval = 300
        self._error_check_interval = 2000
        
        self._completion_popup = CompletionPopup(self, theme_manager)
        self._completion_popup.completion_selected.connect(self._insert_completion)
        self._completion_popup.hide()
        
        self._async_worker = AsyncCompletionWorker(self)
        self._async_worker.completion_ready.connect(self._on_completion_ready)
        self._async_worker.start()
        
        self._current_request_id = 0
        self._pending_prefix = ''
        self._suppress_completion = False

    def stop_async_worker(self):
        """停止异步补全工作线程（R247 修复）

        原实现启动 AsyncCompletionWorker(QThread) 后无任何 stop/closeEvent 路径,
        run() 的 while self._running 循环永不退出。当包含编辑器的对话框被关闭/GC 时,
        QThread 对象被销毁而线程仍在运行 -> "QThread: Destroyed while thread is still running"
        -> 进程崩溃。此方法供上层关闭链 (StrategyManagerDialog.cleanup) 调用。
        """
        worker = getattr(self, '_async_worker', None)
        if worker is not None:
            try:
                worker.stop()
                worker.wait(3000)
                if worker.isRunning():
                    logger.warning("异步补全线程 3 秒内未退出，继续等待...")
                    worker.wait(5000)
            except Exception as e:
                logger.warning(f"停止异步补全线程异常: {e}")
            finally:
                self._async_worker = None

    def _init_theme(self):
        if self.theme_manager:
            colors = self.theme_manager.get_theme_colors()
            bg_color = colors.get('chart_background', colors.get('background', '#1e1e1e'))
            text_color = colors.get('text', '#d4d4d4')
            selection_color = colors.get('selected_bg', '#264f78')
            
            self.setStyleSheet(f"""
                QPlainTextEdit {{
                    background-color: {bg_color};
                    border: none;
                    color: {text_color};
                    font-family: Consolas;
                    font-size: 11px;
                    selection-background-color: {selection_color};
                }}
            """)

    def line_number_area_width(self):
        digits = 1
        max_value = max(1, self.blockCount())
        while max_value >= 10:
            max_value //= 10
            digits += 1
        space = 10 + self.fontMetrics().width('9') * digits
        return space

    def _update_line_number_area_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def _update_minimap(self):
        if hasattr(self, 'minimap') and self.minimap:
            scrollbar = self.verticalScrollBar()
            if scrollbar.maximum() > 0:
                start_ratio = scrollbar.value() / (scrollbar.maximum() + scrollbar.pageStep())
                visible_ratio = scrollbar.pageStep() / (scrollbar.maximum() + scrollbar.pageStep())
                self.minimap.update_visible_area(start_ratio, visible_ratio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event):
        if self.line_number_area is None:
            return
            
        painter = QPainter(self.line_number_area)
        
        try:
            if self.theme_manager:
                colors = self.theme_manager.get_theme_colors()
                bg_color = colors.get('sidebar_bg', colors.get('background', '#252526'))
                text_color = colors.get('text', '#d4d4d4')
                highlight_color = colors.get('highlight', '#1976d2')
                breakpoint_color = colors.get('error', '#ef4444')
            else:
                bg_color = '#252526'
                text_color = '#d4d4d4'
                highlight_color = '#1976d2'
                breakpoint_color = '#ef4444'

            painter.fillRect(event.rect(), QColor(bg_color))

            block = self.firstVisibleBlock()
            block_number = block.blockNumber()
            top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
            bottom = top + self.blockBoundingRect(block).height()
            current_line = self.textCursor().blockNumber()

            while block.isValid() and top <= event.rect().bottom():
                if block.isVisible() and bottom >= event.rect().top():
                    number = str(block_number + 1)
                    
                    if block_number == current_line:
                        painter.setPen(QColor(highlight_color))
                        font = painter.font()
                        font.setBold(True)
                        painter.setFont(font)
                    else:
                        painter.setPen(QColor(text_color))
                        font = painter.font()
                        font.setBold(False)
                        painter.setFont(font)

                    painter.drawText(
                        0, int(top), self.line_number_area.width() - 5, self.fontMetrics().height(),
                        Qt.AlignRight, number
                    )

                    if block_number + 1 in self.line_number_area._breakpoint_lines:
                        painter.setBrush(QColor(breakpoint_color))
                        painter.setPen(Qt.NoPen)
                        painter.drawEllipse(5, int(top) + 2, 8, 8)

                block = block.next()
                top = bottom
                bottom = top + self.blockBoundingRect(block).height()
                block_number += 1
        except Exception as e:
            logger.debug(f"Line number paint error: {e}")
        finally:
            painter.end()

    def _on_text_changed(self):
        if self._suppress_completion:
            return
        self.completion_timer.start(self._debounce_interval)
        self.error_timer.start(self._error_check_interval)

    def _trigger_completion(self):
        if self._suppress_completion:
            return
        cursor = self.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber()
        text_before_cursor = cursor.block().text()[:column]
        
        if not text_before_cursor:
            self._completion_popup.hide_popup()
            return
            
        word_match = re.search(r'[\w.]+$', text_before_cursor)
        if not word_match:
            self._completion_popup.hide_popup()
            return
            
        current_word = word_match.group()
        
        if current_word.endswith('.'):
            prefix = ''
            trigger_type = 'dot'
        elif '.' in current_word:
            prefix = current_word.split('.')[-1]
            trigger_type = 'dot'
        else:
            prefix = current_word
            trigger_type = 'normal'
            
        if len(prefix) < 1 and trigger_type == 'normal':
            self._completion_popup.hide_popup()
            return
            
        self._pending_prefix = prefix
        code = self.toPlainText()
        
        self._current_request_id = self._async_worker.request_completion(
            code, line, column, prefix, trigger_type
        )
            
        if self.completion_callback:
            current_position = (line, column)
            code_hash = hash(code)
            
            if (self._cached_code_hash == code_hash and 
                self._last_completion_position == current_position and
                self._cached_completions is not None):
                return
            
            self._cached_code_hash = code_hash
            self._last_completion_position = current_position
            self.completion_callback(text_before_cursor, line, column)
            
    def _on_completion_ready(self, request_id: int, completions: List[str], prefix: str, trigger_type: str):
        """处理异步补全结果 - 在主线程中执行"""
        if request_id != self._current_request_id:
            return
            
        if not completions:
            self._completion_popup.hide_popup()
            return
            
        self._completion_popup.set_simple_completions(completions)
        cursor_rect = self.cursorRect()
        cursor_rect.setWidth(self._completion_popup.width())
        popup_pos = self.mapToGlobal(cursor_rect.bottomLeft())
        self._completion_popup.show_popup(popup_pos)
        
    def _insert_completion(self, text: str):
        try:
            self._completion_popup.hide_popup()
            
            cursor = self.textCursor()
            
            cursor.movePosition(QTextCursor.StartOfWord, QTextCursor.KeepAnchor)
            
            selected = cursor.selectedText()
            if selected and selected.endswith('.'):
                cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
                selected = cursor.selectedText()
            
            if selected:
                cursor.removeSelectedText()
            
            cursor.insertText(text)
            self.setTextCursor(cursor)
            
        except Exception as e:
            logger.debug(f"Insert completion error: {e}")
            self._completion_popup.hide_popup()
        
    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        if self._completion_popup.is_popup_visible():
            if key == Qt.Key_Escape:
                self._completion_popup.hide_popup()
                return
            elif key == Qt.Key_Up:
                self._completion_popup.select_previous()
                return
            elif key == Qt.Key_Down:
                self._completion_popup.select_next()
                return
            elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
                text = self._completion_popup.get_current_text()
                if text:
                    self._completion_popup.hide_popup()
                    self._suppress_completion = True
                    try:
                        self._do_insert_completion(text)
                    finally:
                        self._suppress_completion = False
                else:
                    self._completion_popup.hide_popup()
                return
            elif key in (Qt.Key_Backspace, Qt.Key_Delete):
                self._completion_popup.hide_popup()
            elif key == Qt.Key_Space:
                self._completion_popup.hide_popup()
                
        if key == Qt.Key_Tab:
            cursor = self.textCursor()
            cursor.insertText('    ')
            return
        elif key == Qt.Key_Return:
            cursor = self.textCursor()
            line = cursor.block().text()
            indent = ''
            for char in line:
                if char in ' \t':
                    indent += char
                else:
                    break
            super().keyPressEvent(event)
            cursor.insertText(indent)
            return
        elif key == Qt.Key_Backspace:
            cursor = self.textCursor()
            if cursor.columnNumber() >= 4:
                cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, 4)
                if cursor.selectedText() == '    ':
                    cursor.removeSelectedText()
                    return
        elif key == Qt.Key_Period:
            super().keyPressEvent(event)
            QTimer.singleShot(100, self._trigger_completion)
            return
        elif key == Qt.Key_Space and modifiers == Qt.ControlModifier:
            self._trigger_completion()
            return

        super().keyPressEvent(event)
        
    def _do_insert_completion(self, text: str):
        """执行补全插入 - 直接操作，不触发信号"""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            cursor.movePosition(QTextCursor.StartOfWord, QTextCursor.KeepAnchor)
            selected = cursor.selectedText()
            if selected and selected.endswith('.'):
                cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            cursor.insertText(text)
        finally:
            cursor.endEditBlock()
        self.setTextCursor(cursor)

    def _check_errors(self):
        if self._completion_popup.is_popup_visible():
            return
        if self.error_callback:
            code = self.toPlainText()
            code_hash = hash(code)
            
            if self._cached_code_hash == code_hash:
                return
            
            self._cached_code_hash = code_hash
            self.error_callback(code)

    def clear_cache(self):
        self._cached_code_hash = None
        self._cached_completions = None
        self._last_completion_position = None

    def update_theme(self, theme_manager):
        self.theme_manager = theme_manager
        self._init_theme()
        self.highlighter.update_theme(theme_manager)
        self.line_number_area.update()
        if hasattr(self, 'minimap') and self.minimap:
            self.minimap.update()
        if hasattr(self, '_completion_popup') and self._completion_popup:
            self._completion_popup.update_theme(theme_manager)


class ErrorListWidget(QWidget):
    """错误列表组件 - 支持主题"""

    error_clicked = pyqtSignal(int, int)

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(12, 8, 8, 8)
        header_layout.setSpacing(8)
        
        header_icon = QLabel("⚠")
        header_icon.setStyleSheet("font-size: 14px;")
        header_layout.addWidget(header_icon)
        
        header = QLabel("问题面板")
        header.setObjectName("panel_header")
        header_layout.addWidget(header)
        
        self._error_count_label = QLabel("0 个问题")
        self._error_count_label.setObjectName("error_count")
        header_layout.addWidget(self._error_count_label)
        header_layout.addStretch()
        
        layout.addWidget(header_widget)

        self.error_list = QListWidget()
        self.error_list.itemClicked.connect(self._on_error_clicked)
        self.error_list.setAlternatingRowColors(True)
        layout.addWidget(self.error_list)
        
        self._apply_theme()

    def _apply_theme(self):
        if self.theme_manager:
            colors = self.theme_manager.get_theme_colors()
            bg_color = colors.get('chart_background', colors.get('background', '#1e1e1e'))
            border_color = colors.get('border', '#3c3c3c')
            text_color = colors.get('text', '#d4d4d4')
            selected_bg = colors.get('selected_bg', '#264f78')
            header_bg = colors.get('sidebar_bg', colors.get('background', '#2d2d2d'))
            error_color = colors.get('error', '#f44336')
            warning_color = colors.get('warning', '#ff9800')
            
            self.setStyleSheet(f"""
                QWidget {{
                    background-color: {bg_color};
                }}
                QLabel#panel_header {{
                    background-color: transparent;
                    color: {text_color};
                    font-size: 12px;
                    font-weight: bold;
                }}
                QLabel#error_count {{
                    background-color: {error_color};
                    color: white;
                    font-size: 10px;
                    padding: 2px 8px;
                    border-radius: 10px;
                }}
                QListWidget {{
                    background-color: {bg_color};
                    border: none;
                    color: {text_color};
                    font-family: 'Segoe UI', Consolas;
                    font-size: 12px;
                    alternate-background-color: {header_bg};
                }}
                QListWidget::item {{
                    padding: 6px 12px;
                    border-bottom: 1px solid {border_color};
                }}
                QListWidget::item:hover {{
                    background-color: {header_bg};
                }}
                QListWidget::item:selected {{
                    background-color: {selected_bg};
                }}
            """)

    def update_errors(self, errors: List[Dict]):
        self.error_list.clear()
        error_count = 0
        warning_count = 0
        
        for error in errors:
            line = error.get('line', 0)
            column = error.get('column', 0)
            message = error.get('message', '')
            severity = error.get('severity', 'error')

            if severity == 'error':
                icon = '✖'
                color = '#f44747'
                error_count += 1
            elif severity == 'warning':
                icon = '⚠'
                color = '#dcdcaa'
                warning_count += 1
            else:
                icon = 'ℹ'
                color = '#608b4e'

            item = QListWidgetItem(f"  {icon}  行 {line}, 列 {column}: {message}")
            item.setForeground(QColor(color))
            item.setData(Qt.UserRole, (line, column))
            self.error_list.addItem(item)
        
        total = error_count + warning_count
        if hasattr(self, '_error_count_label'):
            if total == 0:
                self._error_count_label.setText("无问题")
                self._error_count_label.setStyleSheet("background-color: #4caf50; color: white; font-size: 10px; padding: 2px 8px; border-radius: 10px;")
            else:
                self._error_count_label.setText(f"{error_count} 错误, {warning_count} 警告")
                if error_count > 0:
                    self._error_count_label.setStyleSheet("background-color: #f44336; color: white; font-size: 10px; padding: 2px 8px; border-radius: 10px;")
                else:
                    self._error_count_label.setStyleSheet("background-color: #ff9800; color: white; font-size: 10px; padding: 2px 8px; border-radius: 10px;")

    def _on_error_clicked(self, item):
        data = item.data(Qt.UserRole)
        if data:
            self.error_clicked.emit(data[0], data[1])

    def clear_errors(self):
        self.error_list.clear()

    def update_theme(self, theme_manager):
        self.theme_manager = theme_manager
        self._apply_theme()


class CodeOutlineWidget(QWidget):
    """代码大纲组件 - 支持主题"""

    outline_item_clicked = pyqtSignal(int)

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._outline_items = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(12, 8, 8, 8)
        header_layout.setSpacing(8)
        
        header_icon = QLabel("≡")
        header_icon.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(header_icon)
        
        header = QLabel("代码大纲")
        header.setObjectName("panel_header")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        layout.addWidget(header_widget)

        self.outline_tree = QListWidget()
        self.outline_tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.outline_tree)

        self.setMinimumWidth(200)
        self.setMaximumWidth(300)
        self._apply_theme()

    def _apply_theme(self):
        if self.theme_manager:
            colors = self.theme_manager.get_theme_colors()
            bg_color = colors.get('chart_background', colors.get('background', '#1e1e1e'))
            border_color = colors.get('border', '#3c3c3c')
            text_color = colors.get('text', '#d4d4d4')
            selected_bg = colors.get('selected_bg', '#264f78')
            header_bg = colors.get('sidebar_bg', colors.get('background', '#2d2d2d'))
            accent_color = colors.get('highlight', '#007acc')
            
            self.setStyleSheet(f"""
                QWidget {{
                    background-color: {bg_color};
                }}
                QLabel#panel_header {{
                    background-color: transparent;
                    color: {text_color};
                    font-size: 12px;
                    font-weight: bold;
                }}
                QListWidget {{
                    background-color: {bg_color};
                    border: none;
                    color: {text_color};
                    font-family: 'Segoe UI', Consolas;
                    font-size: 12px;
                    outline: none;
                }}
                QListWidget::item {{
                    padding: 6px 12px;
                    border-left: 3px solid transparent;
                }}
                QListWidget::item:hover {{
                    background-color: {header_bg};
                    border-left: 3px solid {accent_color};
                }}
                QListWidget::item:selected {{
                    background-color: {selected_bg};
                    border-left: 3px solid {accent_color};
                }}
            """)

    def update_outline(self, code: str):
        self._outline_items = []
        self.outline_tree.clear()

        if not code.strip():
            return

        lines = code.split('\n')
        
        class_pattern = re.compile(r'^(\s*)class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:\(]')
        function_pattern = re.compile(r'^(\s*)def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(')
        import_pattern = re.compile(r'^(\s*)(import|from)\s+')

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            class_match = class_pattern.match(line)
            if class_match:
                indent = len(class_match.group(1))
                class_name = class_match.group(2)
                self._add_outline_item('◇', class_name, line_num, indent, 'class')
                continue

            func_match = function_pattern.match(line)
            if func_match:
                indent = len(func_match.group(1))
                func_name = func_match.group(2)
                icon = '○' if func_name.startswith('_') else '●'
                self._add_outline_item(icon, func_name, line_num, indent, 'function')
                continue

            if import_pattern.match(line):
                indent = len(import_match.group(1)) if (import_match := import_pattern.match(line)) else 0
                self._add_outline_item('□', stripped.split()[-1] if stripped else 'import', line_num, indent, 'import')

    def _add_outline_item(self, icon: str, name: str, line: int, indent: int, item_type: str):
        indent_str = '  ' * (indent // 4)
        item = QListWidgetItem(f"{indent_str}{icon} {name}")
        item.setData(Qt.UserRole, line)
        item.setData(Qt.UserRole + 1, item_type)
        
        if self.theme_manager:
            colors = self.theme_manager.get_theme_colors()
            class_color = colors.get('class', '#ffb86c')
            func_color = colors.get('function', '#50fa7b')
            import_color = colors.get('builtins', '#8be9fd')
        else:
            class_color = '#ffb86c'
            func_color = '#50fa7b'
            import_color = '#8be9fd'
        
        if item_type == 'class':
            item.setForeground(QColor(class_color))
        elif item_type == 'function':
            item.setForeground(QColor(func_color))
        elif item_type == 'import':
            item.setForeground(QColor(import_color))
        
        self.outline_tree.addItem(item)
        self._outline_items.append({
            'name': name,
            'line': line,
            'type': item_type,
            'indent': indent
        })

    def _on_item_clicked(self, item):
        line = item.data(Qt.UserRole)
        if line:
            self.outline_item_clicked.emit(line)

    def clear_outline(self):
        self._outline_items = []
        self.outline_tree.clear()

    def update_theme(self, theme_manager):
        self.theme_manager = theme_manager
        self._apply_theme()


class EditorTabWidget(QTabWidget):
    """多标签页编辑器组件"""

    tab_close_requested = pyqtSignal(int)
    current_tab_changed = pyqtSignal(int)

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.tabCloseRequested.connect(self._on_tab_close_requested)
        self.currentChanged.connect(self._on_current_changed)
        self._apply_theme()

    def _apply_theme(self):
        if self.theme_manager:
            colors = self.theme_manager.get_theme_colors()
            bg_color = colors.get('sidebar_bg', '#2d2d2d')
            text_color = colors.get('text', '#d4d4d4')
            border_color = colors.get('border', '#3c3c3c')
            selected_bg = colors.get('selected_bg', '#264f78')
            highlight_color = colors.get('highlight', '#1976d2')
            
            self.setStyleSheet(f"""
                QTabWidget::pane {{
                    border: 1px solid {border_color};
                    background-color: {bg_color};
                }}
                QTabBar::tab {{
                    background-color: {bg_color};
                    color: {text_color};
                    border: 1px solid {border_color};
                    border-bottom: none;
                    padding: 6px 12px;
                    margin-right: 2px;
                }}
                QTabBar::tab:selected {{
                    background-color: {selected_bg};
                    color: {highlight_color};
                }}
                QTabBar::tab:hover {{
                    background-color: {selected_bg};
                }}
                QTabBar::close-button {{
                    image: none;
                    subcontrol-position: right;
                    margin-right: 4px;
                }}
            """)
        else:
            self.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #3c3c3c;
                    background-color: #2d2d2d;
                }
                QTabBar::tab {
                    background-color: #2d2d2d;
                    color: #d4d4d4;
                    border: 1px solid #3c3c3c;
                    border-bottom: none;
                    padding: 6px 12px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #264f78;
                    color: #1976d2;
                }
                QTabBar::tab:hover {
                    background-color: #264f78;
                }
            """)

    def _on_tab_close_requested(self, index):
        self.tab_close_requested.emit(index)

    def _on_current_changed(self, index):
        self.current_tab_changed.emit(index)

    def update_theme(self, theme_manager):
        self.theme_manager = theme_manager
        self._apply_theme()


SAFE_BUILTINS = {
    'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
    'bytearray': bytearray, 'bytes': bytes, 'callable': callable, 'chr': chr,
    'classmethod': classmethod, 'complex': complex, 'delattr': delattr,
    'dict': dict, 'dir': dir, 'divmod': divmod, 'enumerate': enumerate,
    'filter': filter, 'float': float, 'format': format, 'frozenset': frozenset,
    'getattr': getattr, 'hasattr': hasattr, 'hash': hash, 'hex': hex,
    'id': id, 'int': int, 'isinstance': isinstance, 'issubclass': issubclass,
    'iter': iter, 'len': len, 'list': list, 'map': map, 'max': max,
    'min': min, 'next': next, 'object': object, 'oct': oct, 'ord': ord,
    'pow': pow, 'print': print, 'property': property, 'range': range,
    'repr': repr, 'reversed': reversed, 'round': round, 'set': set,
    'setattr': setattr, 'slice': slice, 'sorted': sorted, 'staticmethod': staticmethod,
    'str': str, 'sum': sum, 'super': super, 'tuple': tuple, 'type': type,
    'vars': vars, 'zip': zip, 'True': True, 'False': False, 'None': None,
    'Exception': Exception, 'ValueError': ValueError, 'TypeError': TypeError,
    'KeyError': KeyError, 'IndexError': IndexError, 'AttributeError': AttributeError,
    'ImportError': ImportError, 'RuntimeError': RuntimeError, 'StopIteration': StopIteration,
}

SAFE_IMPORT_WHITELIST = {
    'numpy', 'pandas', 'math', 'statistics', 'datetime', 'collections',
    'itertools', 'functools', 'json', 'csv', 'typing', 'dataclasses',
    'core.strategy', 'core.strategy.base_strategy', 'core.strategy.strategy_factory',
    'hikyuu',
}


class StrategyCodeEditor(QWidget):
    """策略代码编辑器 - 重构版"""

    code_saved = pyqtSignal(str)
    code_executed = pyqtSignal(str)

    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.current_file = None
        self.is_modified = False
        self._open_files = {}
        self._safe_mode = True
        self._init_theme_manager()
        self.init_ui()
        self._init_code_completion()
        self._init_error_checker()
        self._connect_theme_signal()

    def _init_theme_manager(self):
        if self.theme_manager is None and THEME_AVAILABLE:
            try:
                self.theme_manager = get_theme_manager()
            except Exception as e:
                logger.warning(f"获取主题管理器失败: {e}")

    def _connect_theme_signal(self):
        if self.theme_manager:
            try:
                self.theme_manager.theme_changed.connect(self._on_theme_changed)
            except Exception:
                pass

    def stop_threads(self):
        """停止编辑器内所有工作线程（R247 修复）

        由上层关闭链 (StrategyManagerDialog.cleanup) 调用, 防止 QThread 在线程
        仍运行时被 GC 销毁导致 "QThread: Destroyed while thread is still running" 崩溃。
        """
        if hasattr(self, 'code_editor') and self.code_editor:
            try:
                self.code_editor.stop_async_worker()
            except Exception as e:
                logger.warning(f"停止代码编辑器线程异常: {e}")

    def _on_theme_changed(self, theme):
        self._apply_theme()
        if hasattr(self, 'code_editor'):
            self.code_editor.update_theme(self.theme_manager)
        if hasattr(self, 'error_widget'):
            self.error_widget.update_theme(self.theme_manager)
        if hasattr(self, 'outline_widget'):
            self.outline_widget.update_theme(self.theme_manager)
        if hasattr(self, 'tab_widget'):
            self.tab_widget.update_theme(self.theme_manager)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        main_splitter = QSplitter(Qt.Horizontal)

        self.outline_widget = CodeOutlineWidget(theme_manager=self.theme_manager)
        self.outline_widget.outline_item_clicked.connect(self._go_to_outline_item)
        main_splitter.addWidget(self.outline_widget)

        center_widget = self._create_center_widget()
        main_splitter.addWidget(center_widget)

        self.minimap = MinimapWidget(self.code_editor, self)
        main_splitter.addWidget(self.minimap)

        main_splitter.setSizes([220, 700, 120])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)
        layout.addWidget(main_splitter)

        self.status_bar = self._create_status_bar()
        layout.addWidget(self.status_bar)

        self._apply_theme()
        self._load_default_template()

    def _create_toolbar(self) -> QToolBar:
        toolbar = QToolBar()
        toolbar.setObjectName("editor_toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3c3c3c;
                spacing: 2px;
                padding: 4px 8px;
            }
            QToolBar::separator {
                background-color: #3c3c3c;
                width: 1px;
                margin: 4px 8px;
            }
        """)

        file_actions = [
            ('file-new', '新建', QKeySequence.New, self._new_file, 'Ctrl+N'),
            ('file-open', '打开', QKeySequence.Open, self._open_file, 'Ctrl+O'),
            ('file-save', '保存', QKeySequence.Save, self._save_file, 'Ctrl+S'),
        ]

        for action_id, text, shortcut, callback, tooltip in file_actions:
            action = QAction(text, self)
            if shortcut:
                action.setShortcut(shortcut)
            action.setToolTip(f"{text} ({tooltip})")
            if callback:
                action.triggered.connect(callback)
            toolbar.addAction(action)

        toolbar.addSeparator()

        run_actions = [
            ('run-start', '运行', QKeySequence('F5'), self._run_code, 'F5'),
            ('debug-debug', '调试', QKeySequence('F9'), self._open_debugger, 'F9'),
        ]

        for action_id, text, shortcut, callback, tooltip in run_actions:
            action = QAction(text, self)
            if shortcut:
                action.setShortcut(shortcut)
            action.setToolTip(f"{text} ({tooltip})")
            action.triggered.connect(callback)
            toolbar.addAction(action)

        toolbar.addSeparator()

        tool_actions = [
            ('format', '格式化', QKeySequence('Ctrl+Shift+F'), self._format_code, 'Ctrl+Shift+F'),
            ('check', '检查', QKeySequence('Ctrl+Shift+M'), self._check_code, 'Ctrl+Shift+M'),
        ]

        for action_id, text, shortcut, callback, tooltip in tool_actions:
            action = QAction(text, self)
            if shortcut:
                action.setShortcut(shortcut)
            action.setToolTip(f"{text} ({tooltip})")
            action.triggered.connect(callback)
            toolbar.addAction(action)

        toolbar.addSeparator()

        view_actions = [
            ('template', '模板', None, self._insert_template, None),
            ('outline', '大纲', QKeySequence('Ctrl+Shift+O'), self._toggle_outline, 'Ctrl+Shift+O'),
        ]

        for action_id, text, shortcut, callback, tooltip in view_actions:
            action = QAction(text, self)
            if shortcut:
                action.setShortcut(shortcut)
            if tooltip:
                action.setToolTip(f"{text} ({tooltip})")
            else:
                action.setToolTip(text)
            action.triggered.connect(callback)
            toolbar.addAction(action)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        return toolbar

    def _create_center_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tab_widget = EditorTabWidget(theme_manager=self.theme_manager)
        self.tab_widget.tab_close_requested.connect(self._close_tab)
        self.tab_widget.current_tab_changed.connect(self._on_tab_changed)

        self.code_editor = CodeEditor(theme_manager=self.theme_manager)
        self.code_editor.textChanged.connect(self._on_text_changed)
        self.code_editor.breakpoints_changed.connect(self._on_breakpoints_changed)
        self.tab_widget.addTab(self.code_editor, "未命名.py")

        layout.addWidget(self.tab_widget)

        bottom_splitter = QSplitter(Qt.Vertical)
        bottom_splitter.setObjectName("bottom_panel")

        self.error_widget = ErrorListWidget(theme_manager=self.theme_manager)
        self.error_widget.error_clicked.connect(self._go_to_error)
        self.error_widget.setMaximumHeight(150)
        bottom_splitter.addWidget(self.error_widget)

        bottom_splitter.setSizes([400, 150])
        bottom_splitter.setVisible(False)
        
        self._bottom_splitter = bottom_splitter
        self._bottom_panel_visible = False

        return widget

    def _create_status_bar(self) -> QStatusBar:
        status_bar = QStatusBar()
        status_bar.setObjectName("editor_statusbar")
        status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #007acc;
                color: white;
                font-size: 11px;
                min-height: 24px;
                max-height: 24px;
                padding: 0 4px;
            }
            QStatusBar::item {
                border: none;
            }
            QStatusBar QLabel {
                color: white;
                padding: 0 12px;
                border-left: 1px solid rgba(255,255,255,0.3);
                line-height: 24px;
            }
            QStatusBar QLabel:first-child {
                border-left: none;
            }
        """)
        status_bar.setSizeGripEnabled(False)
        
        self._status_label = QLabel("就绪")
        self._status_label.setObjectName("status_label")
        self._status_label.setFixedHeight(24)
        status_bar.addWidget(self._status_label)
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        spacer.setFixedHeight(24)
        status_bar.addWidget(spacer, 1)
        
        self._line_col_label = QLabel("行 1, 列 1")
        self._line_col_label.setObjectName("status_label")
        self._line_col_label.setFixedHeight(24)
        status_bar.addPermanentWidget(self._line_col_label)
        
        self._encoding_label = QLabel("UTF-8")
        self._encoding_label.setObjectName("status_label")
        self._encoding_label.setFixedHeight(24)
        status_bar.addPermanentWidget(self._encoding_label)
        
        self._language_label = QLabel("Python")
        self._language_label.setObjectName("status_label")
        self._language_label.setFixedHeight(24)
        status_bar.addPermanentWidget(self._language_label)
        
        return status_bar

    def _apply_theme(self):
        if self.theme_manager:
            colors = self.theme_manager.get_theme_colors()
            bg_color = colors.get('sidebar_bg', colors.get('background', '#2d2d2d'))
            text_color = colors.get('text', '#d4d4d4')
            border_color = colors.get('border', '#3c3c3c')
            highlight_color = colors.get('highlight', '#1976d2')
            button_bg = colors.get('button_bg', '#3c3c3c')
            button_hover = colors.get('button_hover', '#5a5a5a')
            accent_color = colors.get('highlight', '#007acc')
            
            self.setStyleSheet(f"""
                QToolBar#editor_toolbar {{
                    background-color: {bg_color};
                    border-bottom: 1px solid {border_color};
                    spacing: 2px;
                    padding: 4px 8px;
                }}
                QToolBar QToolButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    color: {text_color};
                    font-size: 12px;
                    font-family: 'Segoe UI', sans-serif;
                }}
                QToolBar QToolButton:hover {{
                    background-color: {button_hover};
                }}
                QToolBar QToolButton:pressed {{
                    background-color: {accent_color};
                }}
                QStatusBar#editor_statusbar {{
                    background-color: {accent_color};
                    color: white;
                    font-size: 11px;
                    min-height: 24px;
                    max-height: 24px;
                    padding: 0 4px;
                }}
                QStatusBar QLabel#status_label {{
                    color: white;
                    padding: 0 12px;
                }}
                QSplitter::handle {{
                    background-color: {border_color};
                    width: 1px;
                }}
                QSplitter::handle:hover {{
                    background-color: {accent_color};
                }}
            """)

    def _init_code_completion(self):
        self.code_editor.completion_callback = self._provide_completions
        self._jedi_script_cache = None
        self._jedi_code_hash = None

    def _init_error_checker(self):
        self.code_editor.error_callback = self._check_code_errors
        self._error_check_thread = None
        self._error_check_lock = threading.Lock()

    def _provide_completions(self, text_before_cursor: str, line: int, column: int):
        try:
            import jedi
            code = self.code_editor.toPlainText()
            code_hash = hash(code)
            
            if self._jedi_code_hash != code_hash or self._jedi_script_cache is None:
                self._jedi_script_cache = jedi.Script(code=code)
                self._jedi_code_hash = code_hash

            completions = self._jedi_script_cache.complete(line + 1, column)
            if completions:
                logger.debug(f"找到 {len(completions)} 个补全建议")
                self.code_editor._cached_completions = completions

        except ImportError:
            logger.debug("jedi库未安装，无法提供代码补全")
        except Exception as e:
            logger.debug(f"代码补全失败: {e}")

    def _check_code_errors(self, code: str):
        errors = []
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            errors.append({
                'line': e.lineno or 1,
                'column': e.offset or 0,
                'message': str(e.msg),
                'severity': 'error'
            })

        if errors:
            self.error_widget.update_errors(errors)
            self._update_status(errors)
            self._show_bottom_panel()
            return

        with self._error_check_lock:
            if self._error_check_thread and self._error_check_thread.is_alive():
                return
            
            self._error_check_thread = threading.Thread(
                target=self._async_flake8_check,
                args=(code,),
                daemon=True
            )
            self._error_check_thread.start()

    def _async_flake8_check(self, code: str):
        try:
            import flake8.api.legacy as flake8
            style_guide = flake8.get_style_guide()
            report = style_guide.input_file(
                filename='<string>',
                lines=code.splitlines(keepends=True)
            )

            errors = []
            for error in report.get_statistics('E'):
                parts = error.split()
                if len(parts) >= 4:
                    line = int(parts[0].split(':')[1])
                    message = ' '.join(parts[2:])
                    errors.append({
                        'line': line,
                        'column': 0,
                        'message': message,
                        'severity': 'error'
                    })

            for warning in report.get_statistics('W'):
                parts = warning.split()
                if len(parts) >= 4:
                    line = int(parts[0].split(':')[1])
                    message = ' '.join(parts[2:])
                    errors.append({
                        'line': line,
                        'column': 0,
                        'message': message,
                        'severity': 'warning'
                    })

            QTimer.singleShot(0, lambda: self._update_errors_on_main_thread(errors))

        except ImportError:
            logger.debug("flake8库未安装，无法进行代码风格检查")
        except Exception as e:
            logger.debug(f"代码风格检查失败: {e}")

    def _update_errors_on_main_thread(self, errors: List[Dict]):
        self.error_widget.update_errors(errors)
        self._update_status(errors)
        if errors:
            self._show_bottom_panel()
        else:
            self._hide_bottom_panel()

    def _update_status(self, errors: List[Dict]):
        error_count = sum(1 for e in errors if e.get('severity') == 'error')
        warning_count = sum(1 for e in errors if e.get('severity') == 'warning')

        if error_count > 0:
            self._status_label.setText(f'● {error_count} 个错误, ○ {warning_count} 个警告')
        elif warning_count > 0:
            self._status_label.setText(f'○ {warning_count} 个警告')
        else:
            self._status_label.setText('✓ 无错误')

    def _show_bottom_panel(self):
        if not self._bottom_panel_visible and hasattr(self, '_bottom_splitter'):
            self._bottom_splitter.setVisible(True)
            self._bottom_panel_visible = True

    def _hide_bottom_panel(self):
        if self._bottom_panel_visible and hasattr(self, '_bottom_splitter'):
            self._bottom_splitter.setVisible(False)
            self._bottom_panel_visible = False

    def _on_text_changed(self):
        self.is_modified = True
        cursor = self.code_editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        self._line_col_label.setText(f"行 {line}, 列 {column}")
        self._update_outline_debounced()

    def _on_breakpoints_changed(self, breakpoints: set):
        logger.debug(f"断点已更改: {breakpoints}")

    def _update_outline_debounced(self):
        if not hasattr(self, '_outline_timer'):
            self._outline_timer = QTimer()
            self._outline_timer.setSingleShot(True)
            self._outline_timer.timeout.connect(self._update_outline)
        self._outline_timer.start(500)

    def _update_outline(self):
        if hasattr(self, 'outline_widget') and self.outline_widget:
            code = self.code_editor.toPlainText()
            self.outline_widget.update_outline(code)

    def _toggle_outline(self):
        if self.outline_widget.isVisible():
            self.outline_widget.hide()
        else:
            self.outline_widget.show()

    def _go_to_outline_item(self, line: int):
        cursor = self.code_editor.textCursor()
        block = self.code_editor.document().findBlockByNumber(line - 1)
        if block.isValid():
            cursor.setPosition(block.position())
            self.code_editor.setTextCursor(cursor)
            self.code_editor.setFocus()
            self.code_editor.ensureCursorVisible()

    def _go_to_error(self, line: int, column: int):
        cursor = self.code_editor.textCursor()
        cursor.movePosition(QTextCursor.Start)
        for _ in range(line - 1):
            cursor.movePosition(QTextCursor.Down)
        for _ in range(column):
            cursor.movePosition(QTextCursor.Right)
        self.code_editor.setTextCursor(cursor)
        self.code_editor.setFocus()

    def _new_file(self):
        if self.is_modified:
            reply = QMessageBox.question(
                self, '保存', '是否保存当前文件？',
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                self._save_file()
            elif reply == QMessageBox.Cancel:
                return

        self.code_editor.clear()
        self.current_file = None
        self.is_modified = False
        self._load_default_template()
        self.tab_widget.setTabText(0, "未命名.py")
        self._status_label.setText('新建文件')

    def _open_file(self):
        if self.is_modified:
            reply = QMessageBox.question(
                self, '保存', '是否保存当前文件？',
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                self._save_file()
            elif reply == QMessageBox.Cancel:
                return

        file_path, _ = QFileDialog.getOpenFileName(
            self, '打开策略文件', '', 'Python 文件 (*.py);;所有文件 (*)'
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                self.code_editor.setPlainText(code)
                self.current_file = file_path
                self.is_modified = False
                filename = os.path.basename(file_path)
                self.tab_widget.setTabText(0, filename)
                self._status_label.setText(f'已打开: {filename}')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'无法打开文件: {e}')

    def _save_file(self):
        if not self.current_file:
            file_path, _ = QFileDialog.getSaveFileName(
                self, '保存策略文件', '', 'Python 文件 (*.py);;所有文件 (*)'
            )
            if not file_path:
                return
            self.current_file = file_path

        try:
            code = self.code_editor.toPlainText()
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(code)
            self.is_modified = False
            filename = os.path.basename(self.current_file)
            self.tab_widget.setTabText(0, filename)
            self._status_label.setText(f'已保存: {filename}')
            self.code_saved.emit(self.current_file)
        except Exception as e:
            QMessageBox.critical(self, '错误', f'无法保存文件: {e}')

    def _run_code(self):
        code = self.code_editor.toPlainText()
        if not code.strip():
            QMessageBox.warning(self, "警告", "代码为空，无法运行")
            return
        if self._safe_mode:
            result, error = self._safe_execute_code(code)
            if error:
                QMessageBox.critical(self, "执行失败", f"代码执行失败:\n{error}")
                self._status_label.setText(f'执行失败: {error[:50]}')
            else:
                self._status_label.setText('代码已在安全沙箱中执行完成')
        else:
            self.code_executed.emit(code)
            self._status_label.setText('正在运行代码...')

    def set_safe_mode(self, enabled: bool = True):
        self._safe_mode = enabled

    def _safe_execute_code(self, code: str) -> tuple:
        import sys
        import threading
        import importlib

        result = {}
        error_msg = None

        safe_globals = {
            '__builtins__': dict(SAFE_BUILTINS),
            '__name__': '__strategy_sandbox__',
            '__file__': '<sandbox>',
        }

        class SandboxImportHook:
            @staticmethod
            def find_module(fullname, path=None):
                if fullname in SAFE_IMPORT_WHITELIST:
                    return None
                for allowed in SAFE_IMPORT_WHITELIST:
                    if fullname.startswith(allowed + '.'):
                        return None
                raise ImportError(f"模块 '{fullname}' 不在安全白名单中")

        class SafeDict(dict):
            def __setitem__(self, key, value):
                if key == '__builtins__':
                    raise RuntimeError("不允许修改 __builtins__")
                super().__setitem__(key, value)

        safe_globals = SafeDict(safe_globals)

        exec_result = {}

        def _exec_in_thread():
            nonlocal error_msg
            try:
                saved_hooks = sys.meta_path[:]
                sys.meta_path.insert(0, SandboxImportHook())
                try:
                    exec(code, safe_globals, safe_globals)
                finally:
                    sys.meta_path = saved_hooks

                for name, obj in safe_globals.items():
                    if name.startswith('_'):
                        continue
                    if isinstance(obj, type) and callable(getattr(obj, 'generate_signals', None)):
                        exec_result['strategy_class'] = name
                        exec_result['strategy_type'] = obj
                        break
            except Exception as e:
                error_msg = str(e)

        exec_thread = threading.Thread(target=_exec_in_thread, daemon=True)
        exec_thread.start()
        exec_thread.join(timeout=30)

        if exec_thread.is_alive():
            error_msg = "代码执行超时（30秒限制）"
            logger.warning(f"安全沙箱执行超时")

        if error_msg:
            return None, error_msg

        logger.info(f"安全沙箱执行成功，发现策略类: {exec_result.get('strategy_class', '无')}")
        return exec_result, None

    def _format_code(self):
        try:
            import black
            code = self.code_editor.toPlainText()
            formatted = black.format_str(code, mode=black.FileMode())
            self.code_editor.setPlainText(formatted)
            self._status_label.setText('代码已格式化')
        except ImportError:
            QMessageBox.warning(
                self, '缺少依赖',
                '请安装black库来格式化代码\n\n安装命令: pip install black'
            )
        except Exception as e:
            QMessageBox.warning(self, '格式化失败', f'代码格式化失败: {e}')

    def _check_code(self):
        code = self.code_editor.toPlainText()
        self._check_code_errors(code)
        self._status_label.setText('代码检查完成')

    def _insert_template(self):
        dialog = TemplateDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            template = dialog.get_template()
            if template:
                self.code_editor.setPlainText(template)
                self._status_label.setText('已插入模板')

    def _open_debugger(self):
        from gui.widgets.strategy_debugger import StrategyDebugger
        
        dialog = QDialog(self)
        dialog.setWindowTitle('策略调试器')
        dialog.resize(1200, 800)
        
        layout = QVBoxLayout(dialog)
        
        debugger = StrategyDebugger()
        debugger.load_code(self.code_editor.toPlainText(), self.current_file)
        layout.addWidget(debugger)
        
        dialog.exec_()

    def _close_tab(self, index: int):
        if self.tab_widget.count() > 1:
            self.tab_widget.removeTab(index)

    def _on_tab_changed(self, index: int):
        pass

    def _load_default_template(self):
        template = '''"""
策略模板
"""
from typing import Dict, List
import pandas as pd
import numpy as np
from core.strategy.base_strategy import BaseStrategy, SignalType


class MyStrategy(BaseStrategy):
    """自定义策略"""

    def __init__(self, params: Dict = None):
        super().__init__(params)
        self.name = "我的策略"

    def initialize(self):
        """初始化策略"""
        pass

    def on_bar(self, bar: Dict):
        """K线回调"""
        pass

    def on_tick(self, tick: Dict):
        """Tick回调"""
        pass

    def calculate_signals(self, data: pd.DataFrame) -> List[Dict]:
        """计算信号"""
        signals = []
        return signals
'''
        self.code_editor.setPlainText(template)
        self._update_outline()


class TemplateDialog(QDialog):
    """策略模板选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('选择策略模板')
        self.resize(400, 300)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.template_combo = QComboBox()
        self.template_combo.addItems([
            '基础策略模板',
            '均线策略模板',
            'MACD策略模板',
            'RSI策略模板',
            '布林带策略模板'
        ])
        layout.addWidget(QLabel('选择模板:'))
        layout.addWidget(self.template_combo)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        layout.addWidget(QLabel('预览:'))
        layout.addWidget(self.preview)

        self.template_combo.currentTextChanged.connect(self._update_preview)
        self._update_preview(self.template_combo.currentText())

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton('确定')
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _update_preview(self, name: str):
        templates = {
            '基础策略模板': '''"""基础策略模板"""
from core.strategy.base_strategy import BaseStrategy

class BasicStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
    
    def calculate_signals(self, data):
        return []
''',
            '均线策略模板': '''"""均线策略模板"""
from core.strategy.base_strategy import BaseStrategy
import pandas as pd

class MAStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
        self.fast_period = params.get('fast_period', 5)
        self.slow_period = params.get('slow_period', 20)
    
    def calculate_signals(self, data):
        signals = []
        data['ma_fast'] = data['close'].rolling(self.fast_period).mean()
        data['ma_slow'] = data['close'].rolling(self.slow_period).mean()
        return signals
''',
            'MACD策略模板': '''"""MACD策略模板"""
from core.strategy.base_strategy import BaseStrategy

class MACDStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
        self.fast = params.get('fast', 12)
        self.slow = params.get('slow', 26)
        self.signal = params.get('signal', 9)
    
    def calculate_signals(self, data):
        signals = []
        return signals
''',
            'RSI策略模板': '''"""RSI策略模板"""
from core.strategy.base_strategy import BaseStrategy

class RSIStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
        self.period = params.get('period', 14)
    
    def calculate_signals(self, data):
        signals = []
        return signals
''',
            '布林带策略模板': '''"""布林带策略模板"""
from core.strategy.base_strategy import BaseStrategy

class BollingerStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
        self.period = params.get('period', 20)
        self.std_dev = params.get('std_dev', 2)
    
    def calculate_signals(self, data):
        signals = []
        return signals
'''
        }
        self.preview.setPlainText(templates.get(name, ''))

    def get_template(self) -> str:
        templates = {
            '基础策略模板': '''"""基础策略模板"""
from core.strategy.base_strategy import BaseStrategy

class BasicStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
    
    def calculate_signals(self, data):
        return []
''',
            '均线策略模板': '''"""均线策略模板"""
from core.strategy.base_strategy import BaseStrategy
import pandas as pd

class MAStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
        self.fast_period = params.get('fast_period', 5)
        self.slow_period = params.get('slow_period', 20)
    
    def calculate_signals(self, data):
        signals = []
        data['ma_fast'] = data['close'].rolling(self.fast_period).mean()
        data['ma_slow'] = data['close'].rolling(self.slow_period).mean()
        return signals
''',
            'MACD策略模板': '''"""MACD策略模板"""
from core.strategy.base_strategy import BaseStrategy

class MACDStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
        self.fast = params.get('fast', 12)
        self.slow = params.get('slow', 26)
        self.signal = params.get('signal', 9)
    
    def calculate_signals(self, data):
        signals = []
        return signals
''',
            'RSI策略模板': '''"""RSI策略模板"""
from core.strategy.base_strategy import BaseStrategy

class RSIStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
        self.period = params.get('period', 14)
    
    def calculate_signals(self, data):
        signals = []
        return signals
''',
            '布林带策略模板': '''"""布林带策略模板"""
from core.strategy.base_strategy import BaseStrategy

class BollingerStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
        self.period = params.get('period', 20)
        self.std_dev = params.get('std_dev', 2)
    
    def calculate_signals(self, data):
        signals = []
        return signals
'''
        }
        return templates.get(self.template_combo.currentText(), '')
