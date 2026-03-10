"""
纯Loguru日志控件模块
直接集成Loguru日志系统，提供实时日志显示
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from datetime import datetime
from loguru import logger
import traceback
import json
import os

class LoguruLogWidget(QWidget):
    """纯Loguru日志控件类"""

    log_received = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        """初始化日志控件"""
        super().__init__(parent)
        self.all_logs = []
        self.is_paused = False
        self.auto_scroll = True
        self._processing = False
        
        self.init_ui()
        self.setup_loguru_sink()
        self.connect_signals()
        
        logger.info("纯Loguru日志控件初始化完成")

    def init_ui(self):
        """初始化UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # 工具栏
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)

        # 日志显示区域
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 9))
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        layout.addWidget(self.log_display)

    def create_toolbar(self):
        """创建工具栏"""
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 4, 4, 4)
        toolbar_layout.setSpacing(8)

        # 日志级别过滤
        toolbar_layout.addWidget(QLabel("级别:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["全部", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_combo.setCurrentText("INFO")
        toolbar_layout.addWidget(self.level_combo)

        # 搜索框
        toolbar_layout.addWidget(QLabel("搜索:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("输入关键词...")
        self.search_box.setMaximumWidth(200)
        toolbar_layout.addWidget(self.search_box)

        # 弹性空间
        toolbar_layout.addStretch()

        # 自动滚动开关
        self.auto_scroll_btn = QPushButton("自动滚动")
        self.auto_scroll_btn.setCheckable(True)
        self.auto_scroll_btn.setChecked(True)
        toolbar_layout.addWidget(self.auto_scroll_btn)

        # 暂停按钮
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setCheckable(True)
        toolbar_layout.addWidget(self.pause_btn)

        # 清空按钮
        self.clear_btn = QPushButton("清空")
        toolbar_layout.addWidget(self.clear_btn)

        # 导出按钮
        self.export_btn = QPushButton("导出")
        toolbar_layout.addWidget(self.export_btn)

        return toolbar

    def setup_loguru_sink(self):
        """设置Loguru自定义Sink"""
        _self = self
        
        def qt_sink(message):
            """Qt专用sink函数"""
            if _self._processing:
                return
            _self._processing = True
            try:
                if _self.is_paused:
                    return
                    
                record = message.record
                level = record["level"].name
                msg = record["message"]
                timestamp = record["time"].strftime("%H:%M:%S.%f")[:-3]
                
                _self.log_received.emit(level, msg, timestamp)
            except Exception as e:
                import sys
                sys.stderr.write(f"[LoguruLogWidget] 错误: {e}\n")
                sys.stderr.flush()
            finally:
                _self._processing = False

        self.sink_id = logger.add(
            qt_sink,
            level="DEBUG",
            format="{message}",
            enqueue=False,
            catch=False
        )

    def connect_signals(self):
        """连接信号槽"""
        self.log_received.connect(self.add_log_entry)
        self.level_combo.currentTextChanged.connect(self.filter_logs)
        self.search_box.textChanged.connect(self.filter_logs)
        self.auto_scroll_btn.toggled.connect(self.toggle_auto_scroll)
        self.pause_btn.toggled.connect(self.toggle_pause)
        self.clear_btn.clicked.connect(self.clear_logs)
        self.export_btn.clicked.connect(self.export_logs)

    @pyqtSlot(str, str, str)
    def add_log_entry(self, level, message, timestamp):
        """添加日志条目"""
        try:
            # 存储原始日志
            log_entry = {
                'timestamp': timestamp,
                'level': level,
                'message': message,
                'formatted_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.all_logs.append(log_entry)
            
            # 限制日志数量（保留最近1000条）
            if len(self.all_logs) > 1000:
                self.all_logs = self.all_logs[-1000:]
            
            # 刷新显示
            self.refresh_display()
            
        except Exception as e:
            # 使用print避免日志循环
            # 使用print避免日志循环，但这里应该使用其他方式记录错误
            pass  # 静默处理以避免日志循环

    def filter_logs(self):
        """过滤日志"""
        self.refresh_display()

    def refresh_display(self):
        """刷新日志显示"""
        try:
            level_filter = self.level_combo.currentText()
            search_text = self.search_box.text().lower()
            
            # 获取过滤后的日志
            filtered_logs = []
            for log_entry in self.all_logs:
                # 级别过滤
                if level_filter != "全部" and log_entry['level'] != level_filter:
                    continue
                
                # 文本搜索
                if search_text and search_text not in log_entry['message'].lower():
                    continue
                
                filtered_logs.append(log_entry)
            
            # 生成HTML内容
            html_content = self.generate_html_content(filtered_logs)
            
            # 保存滚动位置
            scrollbar = self.log_display.verticalScrollBar()
            old_value = scrollbar.value()
            old_max = scrollbar.maximum()
            at_bottom = (old_value == old_max) if old_max > 0 else True
            
            # 更新内容
            self.log_display.setHtml(html_content)
            
            # 恢复滚动位置
            if self.auto_scroll and at_bottom:
                self.scroll_to_bottom()
            
        except Exception as e:
            # 静默处理刷新错误以避免日志循环
            pass

    def generate_html_content(self, logs):
        """生成HTML格式的日志内容"""
        if not logs:
            return '<div style="color: #888; text-align: center; margin-top: 20px;">暂无日志</div>'
        
        html_lines = []
        for log_entry in logs:
            level = log_entry['level']
            message = log_entry['message']
            timestamp = log_entry['timestamp']
            
            # 根据级别设置颜色
            color = self.get_level_color(level)
            
            # 转义HTML特殊字符
            message = self.escape_html(message)
            
            # 生成HTML行
            html_line = f'''
            <div style="color: {color}; font-family: Consolas, monospace; margin: 1px 0;">
                <span style="color: #888;">[{timestamp}]</span> 
                <span style="font-weight: bold;">[{level}]</span> 
                {message}
            </div>
            '''
            html_lines.append(html_line)
        
        return ''.join(html_lines)

    def get_level_color(self, level):
        """获取日志级别对应的颜色"""
        color_map = {
            'DEBUG': '#888888',
            'INFO': '#ffffff',
            'WARNING': '#ffaa00',
            'ERROR': '#ff4444',
            'CRITICAL': '#ff0000'
        }
        return color_map.get(level, '#ffffff')

    def escape_html(self, text):
        """转义HTML特殊字符"""
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#39;'))

    def scroll_to_bottom(self):
        """滚动到底部"""
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def toggle_auto_scroll(self, enabled):
        """切换自动滚动"""
        self.auto_scroll = enabled
        if enabled:
            self.scroll_to_bottom()

    def toggle_pause(self, paused):
        """切换暂停状态"""
        self.is_paused = paused
        self.pause_btn.setText("恢复" if paused else "暂停")

    def clear_logs(self):
        """清空日志"""
        self.all_logs.clear()
        self.log_display.clear()
        logger.info("日志已清空")

    def export_logs(self):
        """导出日志"""
        try:
            if not self.all_logs:
                QMessageBox.information(self, "提示", "没有日志可导出")
                return
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出日志", f"logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Files (*.txt);;JSON Files (*.json)"
            )
            
            if file_path:
                if file_path.endswith('.json'):
                    self.export_as_json(file_path)
                else:
                    self.export_as_text(file_path)
                
                QMessageBox.information(self, "成功", f"日志已导出到:\n{file_path}")
                logger.info(f"日志已导出到: {file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {e}")
            logger.error(f"导出日志失败: {e}")

    def export_as_text(self, file_path):
        """导出为文本格式"""
        with open(file_path, 'w', encoding='utf-8') as f:
            for log_entry in self.all_logs:
                f.write(f"[{log_entry['formatted_time']}] [{log_entry['level']}] {log_entry['message']}\n")

    def export_as_json(self, file_path):
        """导出为JSON格式"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.all_logs, f, ensure_ascii=False, indent=2)

    def closeEvent(self, event):
        """关闭事件"""
        try:
            # 移除Loguru sink
            if hasattr(self, 'sink_id'):
                logger.remove(self.sink_id)
        except Exception as e:
            # 静默处理清理错误以避免日志循环
            pass
        
        super().closeEvent(event)

    def add_log(self, level: str, message: str):
        """向后兼容的添加日志方法"""
        # 直接使用logger记录，会通过sink回调到UI
        if level.upper() == "DEBUG":
            logger.debug(message)
        elif level.upper() == "INFO":
            logger.info(message)
        elif level.upper() == "WARNING":
            logger.warning(message)
        elif level.upper() == "ERROR":
            logger.error(message)
        elif level.upper() == "CRITICAL":
            logger.critical(message)
        else:
            logger.info(message)

# 为了向后兼容，保留原有类名
LogWidget = LoguruLogWidget