"""
策略代码编辑器组件
提供语法高亮、代码补全、错误提示等功能
"""
import os
import re
import sys
import threading
from typing import Dict, List, Optional, Tuple
from loguru import logger

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLabel,
    QPushButton, QToolBar, QAction, QStatusBar, QFileDialog,
    QMessageBox, QSplitter, QListWidget, QListWidgetItem, QTabWidget,
    QComboBox, QSpinBox, QGroupBox, QFormLayout, QDialog, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRegExp
from PyQt5.QtGui import (
    QFont, QTextCharFormat, QSyntaxHighlighter, QColor, QTextCursor,
    QKeySequence, QIcon
)


class PythonSyntaxHighlighter(QSyntaxHighlighter):
    """Python语法高亮器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_formats()
        self._init_rules()

    def _init_formats(self):
        """初始化格式"""
        self.formats = {}

        self.formats['keyword'] = QTextCharFormat()
        self.formats['keyword'].setForeground(QColor('#ff79c6'))
        self.formats['keyword'].setFontWeight(QFont.Bold)

        self.formats['builtins'] = QTextCharFormat()
        self.formats['builtins'].setForeground(QColor('#8be9fd'))

        self.formats['string'] = QTextCharFormat()
        self.formats['string'].setForeground(QColor('#f1fa8c'))

        self.formats['comment'] = QTextCharFormat()
        self.formats['comment'].setForeground(QColor('#6272a4'))
        self.formats['comment'].setFontItalic(True)

        self.formats['number'] = QTextCharFormat()
        self.formats['number'].setForeground(QColor('#bd93f9'))

        self.formats['function'] = QTextCharFormat()
        self.formats['function'].setForeground(QColor('#50fa7b'))

        self.formats['class'] = QTextCharFormat()
        self.formats['class'].setForeground(QColor('#ffb86c'))

        self.formats['decorator'] = QTextCharFormat()
        self.formats['decorator'].setForeground(QColor('#ff79c6'))

        self.formats['operator'] = QTextCharFormat()
        self.formats['operator'].setForeground(QColor('#ff79c6'))

        self.formats['self'] = QTextCharFormat()
        self.formats['self'].setForeground(QColor('#ff5555'))

    def _init_rules(self):
        """初始化规则"""
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
        """高亮文本块"""
        for pattern, format in self.rules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                self.setFormat(index, length, format)
                index = pattern.indexIn(text, index + length)


class CodeEditor(QPlainTextEdit):
    """代码编辑器 - 性能优化版本"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont('Consolas', 10))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopWidth(40)

        self.highlighter = PythonSyntaxHighlighter(self.document())

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
        
        self._debounce_interval = 800
        self._error_check_interval = 2000

    def _on_text_changed(self):
        """文本改变时触发 - 使用防抖机制"""
        self.completion_timer.start(self._debounce_interval)
        self.error_timer.start(self._error_check_interval)

    def _trigger_completion(self):
        """触发代码补全 - 使用缓存机制"""
        if self.completion_callback:
            cursor = self.textCursor()
            line = cursor.blockNumber()
            column = cursor.columnNumber()
            text_before_cursor = cursor.block().text()[:column]
            
            current_position = (line, column)
            code = self.toPlainText()
            code_hash = hash(code)
            
            if (self._cached_code_hash == code_hash and 
                self._last_completion_position == current_position and
                self._cached_completions is not None):
                return
            
            self._cached_code_hash = code_hash
            self._last_completion_position = current_position
            self.completion_callback(text_before_cursor, line, column)

    def _check_errors(self):
        """检查错误 - 使用缓存机制"""
        if self.error_callback:
            code = self.toPlainText()
            code_hash = hash(code)
            
            if self._cached_code_hash == code_hash:
                return
            
            self._cached_code_hash = code_hash
            self.error_callback(code)
    
    def clear_cache(self):
        """清除缓存"""
        self._cached_code_hash = None
        self._cached_completions = None
        self._last_completion_position = None

    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key_Tab:
            cursor = self.textCursor()
            cursor.insertText('    ')
            return
        elif event.key() == Qt.Key_Return:
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
        elif event.key() == Qt.Key_Backspace:
            cursor = self.textCursor()
            if cursor.columnNumber() >= 4:
                cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, 4)
                if cursor.selectedText() == '    ':
                    cursor.removeSelectedText()
                    return

        super().keyPressEvent(event)


class ErrorListWidget(QWidget):
    """错误列表组件"""

    error_clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.error_list = QListWidget()
        self.error_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                color: #d4d4d4;
                font-family: Consolas;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #3c3c3c;
            }
            QListWidget::item:selected {
                background-color: #264f78;
            }
        """)
        self.error_list.itemClicked.connect(self._on_error_clicked)
        layout.addWidget(self.error_list)

    def update_errors(self, errors: List[Dict]):
        """更新错误列表"""
        self.error_list.clear()
        for error in errors:
            line = error.get('line', 0)
            column = error.get('column', 0)
            message = error.get('message', '')
            severity = error.get('severity', 'error')

            if severity == 'error':
                icon = '❌'
                color = '#f44747'
            elif severity == 'warning':
                icon = '⚠️'
                color = '#dcdcaa'
            else:
                icon = 'ℹ️'
                color = '#608b4e'

            item = QListWidgetItem(f"{icon} Line {line}, Col {column}: {message}")
            item.setForeground(QColor(color))
            item.setData(Qt.UserRole, (line, column))
            self.error_list.addItem(item)

    def _on_error_clicked(self, item):
        """错误项点击"""
        data = item.data(Qt.UserRole)
        if data:
            self.error_clicked.emit(data[0], data[1])

    def clear_errors(self):
        """清除错误列表"""
        self.error_list.clear()


class CodeOutlineWidget(QWidget):
    """代码大纲组件 - 显示文件结构导航"""

    outline_item_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._outline_items = []
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("📁 文件大纲")
        header.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                color: #d4d4d4;
                padding: 8px;
                font-weight: bold;
                border-bottom: 1px solid #3c3c3c;
            }
        """)
        layout.addWidget(header)

        self.outline_tree = QListWidget()
        self.outline_tree.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: none;
                color: #d4d4d4;
                font-family: Consolas;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #2d2d2d;
            }
            QListWidget::item:hover {
                background-color: #2d2d2d;
            }
            QListWidget::item:selected {
                background-color: #264f78;
            }
        """)
        self.outline_tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.outline_tree)

        self.setMinimumWidth(200)
        self.setMaximumWidth(300)

    def update_outline(self, code: str):
        """更新代码大纲"""
        self._outline_items = []
        self.outline_tree.clear()

        if not code.strip():
            return

        lines = code.split('\n')
        
        class_pattern = re.compile(r'^(\s*)class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:\(]')
        function_pattern = re.compile(r'^(\s*)def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(')
        import_pattern = re.compile(r'^(\s*)(import|from)\s+')
        variable_pattern = re.compile(r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*')

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            class_match = class_pattern.match(line)
            if class_match:
                indent = len(class_match.group(1))
                class_name = class_match.group(2)
                self._add_outline_item('🏛️', class_name, line_num, indent, 'class')
                continue

            func_match = function_pattern.match(line)
            if func_match:
                indent = len(func_match.group(1))
                func_name = func_match.group(2)
                icon = '⚡' if func_name.startswith('_') else '🔧'
                self._add_outline_item(icon, func_name, line_num, indent, 'function')
                continue

            if import_pattern.match(line):
                indent = len(import_match.group(1)) if (import_match := import_pattern.match(line)) else 0
                self._add_outline_item('📦', stripped.split()[-1] if stripped else 'import', line_num, indent, 'import')

    def _add_outline_item(self, icon: str, name: str, line: int, indent: int, item_type: str):
        """添加大纲项"""
        indent_str = '  ' * (indent // 4)
        item = QListWidgetItem(f"{indent_str}{icon} {name}")
        item.setData(Qt.UserRole, line)
        item.setData(Qt.UserRole + 1, item_type)
        
        if item_type == 'class':
            item.setForeground(QColor('#ffb86c'))
        elif item_type == 'function':
            item.setForeground(QColor('#50fa7b'))
        elif item_type == 'import':
            item.setForeground(QColor('#8be9fd'))
        
        self.outline_tree.addItem(item)
        self._outline_items.append({
            'name': name,
            'line': line,
            'type': item_type,
            'indent': indent
        })

    def _on_item_clicked(self, item):
        """大纲项点击"""
        line = item.data(Qt.UserRole)
        if line:
            self.outline_item_clicked.emit(line)

    def clear_outline(self):
        """清除大纲"""
        self._outline_items = []
        self.outline_tree.clear()


class StrategyCodeEditor(QWidget):
    """策略代码编辑器"""

    code_saved = pyqtSignal(str)
    code_executed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file = None
        self.is_modified = False
        self.init_ui()
        self._init_code_completion()
        self._init_error_checker()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QToolBar()
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3c3c3c;
                spacing: 4px;
                padding: 4px;
            }
            QToolButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px;
                color: #d4d4d4;
            }
            QToolButton:hover {
                background-color: #3c3c3c;
                border: 1px solid #5a5a5a;
            }
            QToolButton:pressed {
                background-color: #264f78;
            }
        """)

        new_action = QAction('新建', self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._new_file)
        toolbar.addAction(new_action)

        open_action = QAction('打开', self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_file)
        toolbar.addAction(open_action)

        save_action = QAction('保存', self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._save_file)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        run_action = QAction('运行', self)
        run_action.setShortcut(QKeySequence('F5'))
        run_action.triggered.connect(self._run_code)
        toolbar.addAction(run_action)

        format_action = QAction('格式化', self)
        format_action.setShortcut(QKeySequence('Ctrl+Shift+F'))
        format_action.triggered.connect(self._format_code)
        toolbar.addAction(format_action)

        check_action = QAction('检查', self)
        check_action.setShortcut(QKeySequence('Ctrl+Shift+M'))
        check_action.triggered.connect(self._check_code)
        toolbar.addAction(check_action)

        toolbar.addSeparator()

        template_action = QAction('模板', self)
        template_action.triggered.connect(self._insert_template)
        toolbar.addAction(template_action)

        toolbar.addSeparator()

        debug_action = QAction('调试', self)
        debug_action.setShortcut(QKeySequence('F9'))
        debug_action.triggered.connect(self._open_debugger)
        toolbar.addAction(debug_action)
        
        outline_action = QAction('大纲', self)
        outline_action.setShortcut(QKeySequence('Ctrl+Shift+O'))
        outline_action.triggered.connect(self._toggle_outline)
        toolbar.addAction(outline_action)

        layout.addWidget(toolbar)

        main_splitter = QSplitter(Qt.Horizontal)

        self.outline_widget = CodeOutlineWidget()
        self.outline_widget.outline_item_clicked.connect(self._go_to_outline_item)
        main_splitter.addWidget(self.outline_widget)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        vertical_splitter = QSplitter(Qt.Vertical)

        self.code_editor = CodeEditor()
        self.code_editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                border: none;
                color: #d4d4d4;
                font-family: Consolas;
                font-size: 11px;
                selection-background-color: #264f78;
            }
        """)
        self.code_editor.textChanged.connect(self._on_text_changed)
        vertical_splitter.addWidget(self.code_editor)

        self.error_widget = ErrorListWidget()
        self.error_widget.error_clicked.connect(self._go_to_error)
        self.error_widget.setMaximumHeight(150)
        vertical_splitter.addWidget(self.error_widget)

        vertical_splitter.setSizes([600, 150])
        right_layout.addWidget(vertical_splitter)

        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([200, 800])

        layout.addWidget(main_splitter)

        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #007acc;
                color: white;
                font-size: 11px;
            }
        """)
        self.status_bar.showMessage('就绪')
        layout.addWidget(self.status_bar)

        self._load_default_template()

    def _toggle_outline(self):
        """切换大纲显示"""
        if self.outline_widget.isVisible():
            self.outline_widget.hide()
        else:
            self.outline_widget.show()

    def _go_to_outline_item(self, line: int):
        """跳转到大纲项对应的代码行"""
        cursor = self.code_editor.textCursor()
        block = self.code_editor.document().findBlockByNumber(line - 1)
        if block.isValid():
            cursor.setPosition(block.position())
            self.code_editor.setTextCursor(cursor)
            self.code_editor.setFocus()
            self.code_editor.ensureCursorVisible()

    def _init_code_completion(self):
        """初始化代码补全"""
        self.code_editor.completion_callback = self._provide_completions
        self._jedi_script_cache = None
        self._jedi_code_hash = None

    def _init_error_checker(self):
        """初始化错误检查器"""
        self.code_editor.error_callback = self._check_code_errors
        self._error_check_thread = None
        self._error_check_lock = threading.Lock()

    def _provide_completions(self, text_before_cursor: str, line: int, column: int):
        """提供代码补全 - 使用缓存优化"""
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
        """检查代码错误 - 异步处理优化"""
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
        """异步执行flake8检查"""
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
        """在主线程中更新错误列表"""
        self.error_widget.update_errors(errors)
        self._update_status(errors)

    def _update_status(self, errors: List[Dict]):
        """更新状态栏"""
        error_count = sum(1 for e in errors if e.get('severity') == 'error')
        warning_count = sum(1 for e in errors if e.get('severity') == 'warning')

        if error_count > 0:
            self.status_bar.showMessage(f'❌ {error_count} 个错误, ⚠️ {warning_count} 个警告')
        elif warning_count > 0:
            self.status_bar.showMessage(f'⚠️ {warning_count} 个警告')
        else:
            self.status_bar.showMessage('✓ 无错误')

    def _on_text_changed(self):
        """文本改变时"""
        self.is_modified = True

        cursor = self.code_editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        self.status_bar.showMessage(f'行 {line}, 列 {column}')
        
        self._update_outline_debounced()

    def _update_outline_debounced(self):
        """防抖更新大纲"""
        if not hasattr(self, '_outline_timer'):
            self._outline_timer = QTimer()
            self._outline_timer.setSingleShot(True)
            self._outline_timer.timeout.connect(self._update_outline)
        self._outline_timer.start(500)

    def _update_outline(self):
        """更新代码大纲"""
        if hasattr(self, 'outline_widget') and self.outline_widget:
            code = self.code_editor.toPlainText()
            self.outline_widget.update_outline(code)

    def _new_file(self):
        """新建文件"""
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
        self.status_bar.showMessage('新建文件')

    def _open_file(self):
        """打开文件"""
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
                self.status_bar.showMessage(f'已打开: {os.path.basename(file_path)}')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'无法打开文件: {e}')

    def _save_file(self):
        """保存文件"""
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
            self.status_bar.showMessage(f'已保存: {os.path.basename(self.current_file)}')
            self.code_saved.emit(self.current_file)
        except Exception as e:
            QMessageBox.critical(self, '错误', f'无法保存文件: {e}')

    def _run_code(self):
        """运行代码"""
        code = self.code_editor.toPlainText()
        self.code_executed.emit(code)
        self.status_bar.showMessage('正在运行代码...')

    def _format_code(self):
        """格式化代码"""
        try:
            import black

            code = self.code_editor.toPlainText()
            formatted = black.format_str(code, mode=black.FileMode())
            self.code_editor.setPlainText(formatted)
            self.status_bar.showMessage('代码已格式化')
        except ImportError:
            QMessageBox.warning(
                self, '缺少依赖',
                '请安装black库来格式化代码\n\n安装命令: pip install black'
            )
        except Exception as e:
            QMessageBox.warning(self, '格式化失败', f'代码格式化失败: {e}')

    def _check_code(self):
        """检查代码"""
        code = self.code_editor.toPlainText()
        self._check_code_errors(code)
        self.status_bar.showMessage('代码检查完成')

    def _insert_template(self):
        """插入模板"""
        dialog = TemplateDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            template = dialog.get_template()
            if template:
                self.code_editor.setPlainText(template)
                self.status_bar.showMessage('已插入模板')

    def _go_to_error(self, line: int, column: int):
        """跳转到错误位置"""
        cursor = self.code_editor.textCursor()
        cursor.movePosition(QTextCursor.Start)
        for _ in range(line - 1):
            cursor.movePosition(QTextCursor.Down)
        for _ in range(column):
            cursor.movePosition(QTextCursor.Right)
        self.code_editor.setTextCursor(cursor)
        self.code_editor.setFocus()

    def _open_debugger(self):
        """打开调试器"""
        from gui.widgets.strategy_debugger import StrategyDebugger
        
        dialog = QDialog(self)
        dialog.setWindowTitle('策略调试器')
        dialog.resize(1200, 800)
        
        layout = QVBoxLayout(dialog)
        
        debugger = StrategyDebugger()
        debugger.load_code(self.code_editor.toPlainText(), self.current_file)
        layout.addWidget(debugger)
        
        dialog.exec_()

    def _load_default_template(self):
        """加载默认模板"""
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
        self.name = "MyStrategy"

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        生成交易信号

        Args:
            data: 股票数据，包含open, high, low, close, volume等列

        Returns:
            信号序列，1表示买入，-1表示卖出，0表示持有
        """
        signals = pd.Series(0, index=data.index)

        # 在这里实现你的策略逻辑
        # 示例：简单的移动平均策略
        short_ma = data['close'].rolling(window=5).mean()
        long_ma = data['close'].rolling(window=20).mean()

        # 生成信号
        signals[short_ma > long_ma] = SignalType.BUY
        signals[short_ma < long_ma] = SignalType.SELL

        return signals

    def validate_parameters(self) -> bool:
        """验证策略参数"""
        return True


if __name__ == '__main__':
    # 测试策略
    strategy = MyStrategy()
    print(f"策略名称: {strategy.name}")
'''
        self.code_editor.setPlainText(template)


class TemplateDialog(QDialog):
    """模板选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('选择策略模板')
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        self.template_combo = QComboBox()
        self.template_combo.addItems([
            '基础策略模板',
            '移动平均策略',
            'RSI策略',
            'MACD策略',
            '布林带策略',
            '多因子策略'
        ])
        layout.addWidget(QLabel('选择模板:'))
        layout.addWidget(self.template_combo)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(300)
        layout.addWidget(QLabel('预览:'))
        layout.addWidget(self.preview)

        self.template_combo.currentTextChanged.connect(self._update_preview)

        buttons = QHBoxLayout()
        ok_button = QPushButton('确定')
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton('取消')
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

        self._update_preview(self.template_combo.currentText())

    def _update_preview(self, template_name: str):
        """更新预览"""
        templates = {
            '基础策略模板': '''from core.strategy.base_strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def generate_signals(self, data):
        # 实现你的策略逻辑
        pass
''',
            '移动平均策略': '''from core.strategy.base_strategy import BaseStrategy
import pandas as pd

class MAStrategy(BaseStrategy):
    def generate_signals(self, data):
        signals = pd.Series(0, index=data.index)
        short_ma = data['close'].rolling(5).mean()
        long_ma = data['close'].rolling(20).mean()
        signals[short_ma > long_ma] = 1
        signals[short_ma < long_ma] = -1
        return signals
''',
            'RSI策略': '''from core.strategy.base_strategy import BaseStrategy
import pandas as pd
import talib

class RSIStrategy(BaseStrategy):
    def generate_signals(self, data):
        signals = pd.Series(0, index=data.index)
        rsi = talib.RSI(data['close'], timeperiod=14)
        signals[rsi < 30] = 1  # 超卖
        signals[rsi > 70] = -1  # 超买
        return signals
''',
            'MACD策略': '''from core.strategy.base_strategy import BaseStrategy
import pandas as pd
import talib

class MACDStrategy(BaseStrategy):
    def generate_signals(self, data):
        signals = pd.Series(0, index=data.index)
        macd, signal, hist = talib.MACD(data['close'])
        signals[hist > 0] = 1
        signals[hist < 0] = -1
        return signals
''',
            '布林带策略': '''from core.strategy.base_strategy import BaseStrategy
import pandas as pd
import talib

class BollingerStrategy(BaseStrategy):
    def generate_signals(self, data):
        signals = pd.Series(0, index=data.index)
        upper, middle, lower = talib.BBANDS(data['close'])
        signals[data['close'] < lower] = 1  # 下穿下轨
        signals[data['close'] > upper] = -1  # 上穿上轨
        return signals
''',
            '多因子策略': '''from core.strategy.base_strategy import BaseStrategy
import pandas as pd
import numpy as np

class MultiFactorStrategy(BaseStrategy):
    def generate_signals(self, data):
        signals = pd.Series(0, index=data.index)
        # 因子1: 动量
        momentum = data['close'].pct_change(20)
        # 因子2: 波动率
        volatility = data['close'].pct_change().rolling(20).std()
        # 因子3: 成交量
        volume_factor = data['volume'] / data['volume'].rolling(20).mean()
        # 综合因子
        composite = momentum - volatility + volume_factor * 0.1
        signals[composite > composite.quantile(0.7)] = 1
        signals[composite < composite.quantile(0.3)] = -1
        return signals
'''
        }

        self.preview.setPlainText(templates.get(template_name, ''))

    def get_template(self) -> str:
        """获取选中的模板"""
        templates = {
            '基础策略模板': '''from core.strategy.base_strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def generate_signals(self, data):
        # 实现你的策略逻辑
        pass
''',
            '移动平均策略': '''from core.strategy.base_strategy import BaseStrategy
import pandas as pd

class MAStrategy(BaseStrategy):
    def generate_signals(self, data):
        signals = pd.Series(0, index=data.index)
        short_ma = data['close'].rolling(5).mean()
        long_ma = data['close'].rolling(20).mean()
        signals[short_ma > long_ma] = 1
        signals[short_ma < long_ma] = -1
        return signals
''',
            'RSI策略': '''from core.strategy.base_strategy import BaseStrategy
import pandas as pd
import talib

class RSIStrategy(BaseStrategy):
    def generate_signals(self, data):
        signals = pd.Series(0, index=data.index)
        rsi = talib.RSI(data['close'], timeperiod=14)
        signals[rsi < 30] = 1  # 超卖
        signals[rsi > 70] = -1  # 超买
        return signals
''',
            'MACD策略': '''from core.strategy.base_strategy import BaseStrategy
import pandas as pd
import talib

class MACDStrategy(BaseStrategy):
    def generate_signals(self, data):
        signals = pd.Series(0, index=data.index)
        macd, signal, hist = talib.MACD(data['close'])
        signals[hist > 0] = 1
        signals[hist < 0] = -1
        return signals
''',
            '布林带策略': '''from core.strategy.base_strategy import BaseStrategy
import pandas as pd
import talib

class BollingerStrategy(BaseStrategy):
    def generate_signals(self, data):
        signals = pd.Series(0, index=data.index)
        upper, middle, lower = talib.BBANDS(data['close'])
        signals[data['close'] < lower] = 1  # 下穿下轨
        signals[data['close'] > upper] = -1  # 上穿上轨
        return signals
''',
            '多因子策略': '''from core.strategy.base_strategy import BaseStrategy
import pandas as pd
import numpy as np

class MultiFactorStrategy(BaseStrategy):
    def generate_signals(self, data):
        signals = pd.Series(0, index=data.index)
        # 因子1: 动量
        momentum = data['close'].pct_change(20)
        # 因子2: 波动率
        volatility = data['close'].pct_change().rolling(20).std()
        # 因子3: 成交量
        volume_factor = data['volume'] / data['volume'].rolling(20).mean()
        # 综合因子
        composite = momentum - volatility + volume_factor * 0.1
        signals[composite > composite.quantile(0.7)] = 1
        signals[composite < composite.quantile(0.3)] = -1
        return signals
'''
        }
        return templates.get(self.template_combo.currentText(), '')
