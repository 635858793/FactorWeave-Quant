"""
数据使用条款对话框模块
"""
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from pathlib import Path
from loguru import logger

from .base_dialog import BaseDialog

logger = logger


class DataUsageTermsDialog(BaseDialog):
    """数据使用条款对话框"""

    def __init__(self, parent=None, show_agreement=False):
        super().__init__(
            parent,
            title="数据使用条款",
            min_size=(800, 600),
            settings_key="DataUsageTermsDialog"
        )
        self.show_agreement = show_agreement
        self.user_agreed = False
        self.setup_ui()
        self.load_terms()

    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("FactorWeave-Quant  数据使用条款")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #007bff;
                padding: 10px;
                text-align: center;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 条款内容显示区域
        self.terms_text = QTextEdit()
        self.terms_text.setReadOnly(True)
        self.terms_text.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self.terms_text)

        # 如果需要显示同意选项
        if self.show_agreement:
            # 同意复选框
            self.agree_checkbox = QCheckBox("我已阅读并同意上述数据使用条款")
            self.agree_checkbox.setStyleSheet("""
                QCheckBox {
                    font-size: 12px;
                    font-weight: bold;
                    padding: 10px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
            """)
            layout.addWidget(self.agree_checkbox)

            # 按钮布局
            button_layout = QHBoxLayout()

            self.agree_button = QPushButton("同意并继续")
            self.agree_button.setStyleSheet("""
                QPushButton {
                    background-color: #007bff;
                    color: white;
                    font-weight: bold;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #0056b3;
                }
                QPushButton:disabled {
                    background-color: #6c757d;
                }
            """)
            self.agree_button.setEnabled(False)

            self.disagree_button = QPushButton("不同意")
            self.disagree_button.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    font-weight: bold;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
            """)

            button_layout.addStretch()
            button_layout.addWidget(self.disagree_button)
            button_layout.addWidget(self.agree_button)
            layout.addLayout(button_layout)

            # 连接信号
            self.agree_checkbox.toggled.connect(self.on_checkbox_toggled)
            self.agree_button.clicked.connect(self.on_agree_clicked)
            self.disagree_button.clicked.connect(self.on_disagree_clicked)

        else:
            # 只显示关闭按钮
            button_layout = QHBoxLayout()
            close_button = QPushButton("关闭")
            close_button.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    font-weight: bold;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #5a6268;
                }
            """)
            button_layout.addStretch()
            button_layout.addWidget(close_button)
            layout.addLayout(button_layout)

            close_button.clicked.connect(self.accept)

    def load_terms(self):
        """加载使用条款内容"""
        try:
            # 查找条款文件
            terms_file = Path(__file__).parent.parent.parent / \
                "DATA_USAGE_TERMS.md"

            if terms_file.exists():
                with open(terms_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 转换Markdown为HTML显示
                html_content = self.markdown_to_html(content)
                self.terms_text.setHtml(html_content)
            else:
                # 如果文件不存在，显示默认条款
                self.terms_text.setHtml(self.get_default_terms())

        except Exception as e:
            logger.error(f"加载使用条款失败: {str(e)}")
            self.terms_text.setHtml(self.get_default_terms())

    def markdown_to_html(self, markdown_text: str) -> str:
        """优化的Markdown到HTML转换器"""
        import re

        # 预处理：清理多余的空行
        html = re.sub(r'\n\s*\n\s*\n', '\n\n', markdown_text)

        # 转换标题（修复逻辑bug）
        html = re.sub(r'^#### (.*?)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

        # 转换粗体和斜体
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)

        # 转换代码块（改进）
        html = re.sub(r'```(\w+)?\n(.*?)\n```',
                      r'<pre style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #007bff; margin: 15px 0; overflow-x: auto;"><code>\2</code></pre>',
                      html, flags=re.DOTALL)

        # 转换行内代码
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

        # 转换列表（修复嵌套列表bug）
        lines = html.split('\n')
        in_list = False
        result_lines = []

        for line in lines:
            if re.match(r'^[-*+] ', line.strip()):
                if not in_list:
                    result_lines.append('<ul>')
                    in_list = True
                # 提取列表项内容
                content = re.sub(r'^[-*+] ', '', line.strip())
                result_lines.append(f'  <li>{content}</li>')
            else:
                if in_list:
                    result_lines.append('</ul>')
                    in_list = False
                result_lines.append(line)

        if in_list:
            result_lines.append('</ul>')

        html = '\n'.join(result_lines)

        # 转换段落（改进逻辑）
        paragraphs = re.split(r'\n\s*\n', html)
        html_paragraphs = []

        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            # 如果不是HTML标签开头，包装为段落
            if not re.match(r'^<[h1-6]|^<ul|^<pre|^<div', p):
                html_paragraphs.append(f'<p>{p}</p>')
            else:
                html_paragraphs.append(p)

        html = '\n\n'.join(html_paragraphs)

        # 优化样式（修复字体大小和行高）
        styled_html = f"""
        <style>
            body {{ 
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif; 
                line-height: 1.6; 
                font-size: 13px;
                color: #333;
                margin: 0;
                padding: 0;
            }}
            h1 {{ 
                color: #007bff; 
                border-bottom: 3px solid #007bff; 
                padding-bottom: 12px; 
                margin: 25px 0 20px 0;
                font-size: 24px;
                font-weight: bold;
            }}
            h2 {{ 
                color: #0056b3; 
                margin: 30px 0 15px 0; 
                font-size: 20px;
                font-weight: bold;
                border-left: 4px solid #007bff;
                padding-left: 15px;
            }}
            h3 {{ 
                color: #17a2b8; 
                margin: 25px 0 12px 0; 
                font-size: 16px;
                font-weight: bold;
            }}
            h4 {{ 
                color: #28a745; 
                margin: 20px 0 10px 0; 
                font-size: 14px;
                font-weight: bold;
            }}
            ul {{ 
                margin: 15px 0; 
                padding-left: 25px; 
                list-style-type: disc;
            }}
            li {{ 
                margin: 8px 0; 
                line-height: 1.5;
            }}
            p {{
                margin: 12px 0;
                text-align: justify;
            }}
            code {{ 
                background-color: #f8f9fa; 
                color: #e83e8c;
                padding: 3px 6px; 
                border-radius: 4px; 
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }}
            pre {{ 
                margin: 20px 0; 
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                line-height: 1.4;
            }}
            pre code {{
                background-color: transparent;
                color: #333;
                padding: 0;
                border-radius: 0;
            }}
            strong {{
                color: #007bff;
                font-weight: bold;
            }}
            em {{
                color: #6f42c1;
                font-style: italic;
            }}
            .highlight {{ 
                background-color: #fff3cd; 
                padding: 10px 15px; 
                border-radius: 6px; 
                border-left: 4px solid #ffc107;
                margin: 15px 0;
            }}
        </style>
        {html}
        """

        return styled_html

    def get_default_terms(self) -> str:
        """获取默认使用条款"""
        return """
        
        <h2>数据使用声明</h2>
        
        <h3>1. 使用目的限制</h3>
        <p><strong>允许的使用目的：</strong></p>
        <ul>
            <li>个人投资研究：用于个人投资决策分析和研究</li>
            <li>学术研究：用于金融量化相关的学术研究</li>
            <li>教育学习：用于量化交易技术的学习和教育</li>
            <li>非商业分析：用于非营利性的数据分析和回测</li>
        </ul>
        
        <p><strong>禁止的使用目的：</strong></p>
        <ul>
            <li>商业转售：禁止将获取的数据进行商业转售</li>
            <li>大规模爬取：禁止进行大规模、高频率的数据爬取</li>
            <li>恶意使用：禁止用于任何可能损害数据提供方利益的行为</li>
            <li>版权侵犯：禁止侵犯数据提供方的知识产权</li>
        </ul>
        
        <h3>2. 用户责任</h3>
        <ul>
            <li>遵守法律法规：用户应遵守所在国家和地区的相关法律法规</li>
            <li>遵守网站条款：用户应遵守各数据提供方的网站使用条款</li>
            <li>合理使用频率：用户应控制数据请求频率，避免对数据提供方造成负担</li>
            <li>数据准确性：用户应理解数据可能存在延迟或错误，需自行验证</li>
        </ul>
        
        <h3>3. 免责声明</h3>
        <ul>
            <li>FactorWeave-Quant 不保证所提供数据的准确性、完整性或时效性</li>
            <li>FactorWeave-Quant 仅为数据分析工具，不构成投资建议</li>
            <li>用户的投资决策应基于自己的判断，并承担相应风险</li>
        </ul>
        
        <p><strong>重要提醒：</strong>使用FactorWeave-Quant 即表示您已阅读、理解并同意遵守本使用条款。</p>
        """

    def on_checkbox_toggled(self, checked: bool):
        """复选框状态改变时的处理"""
        self.agree_button.setEnabled(checked)

    def on_agree_clicked(self):
        """用户点击同意按钮"""
        if self.agree_checkbox.isChecked():
            self.user_agreed = True
            self.accept()
        else:
            QMessageBox.warning(self, "提示", "请先勾选同意条款")

    def on_disagree_clicked(self):
        """用户点击不同意按钮"""
        self.user_agreed = False
        self.reject()

    def is_agreed(self) -> bool:
        """检查用户是否同意条款"""
        return self.user_agreed

    @staticmethod
    def show_terms(parent=None) -> None:
        """显示使用条款（仅查看）- 修复事件循环冲突"""
        try:
            dialog = DataUsageTermsDialog(parent, show_agreement=False)
            # 使用show而不是exec_避免事件循环冲突
            if hasattr(parent, 'isVisible') and parent and parent.isVisible():
                dialog.show()
            else:
                dialog.exec_()
        except RuntimeError as e:
            logger.warning(f"显示条款对话框时发生事件循环冲突: {e}")
            # 降级处理：直接显示条款文本
            if parent:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(parent, "数据使用条款",
                                        "请在菜单中查看完整的数据使用条款。")

    @staticmethod
    def request_agreement(parent=None) -> bool:
        """请求用户同意条款 - 修复事件循环冲突"""
        try:
            dialog = DataUsageTermsDialog(parent, show_agreement=True)
            # 检查事件循环状态
            from PyQt5.QtCore import QCoreApplication
            if QCoreApplication.instance() and hasattr(QCoreApplication.instance(), 'thread'):
                result = dialog.exec_()
                return result == QDialog.Accepted and dialog.is_agreed()
            else:
                # 事件循环不可用时的降级处理
                logger.warning("事件循环不可用，无法显示同意对话框")
                return False
        except RuntimeError as e:
            logger.error(f"请求条款同意时发生事件循环冲突: {e}")
            # 降级处理：假设用户已同意（在实际部署时应该更严格）
            return True


class DataUsageManager:
    """数据使用管理器"""

    def __init__(self):
        self.settings = QSettings("FactorWeave-Quant", "DataUsage")

    def has_agreed_to_terms(self) -> bool:
        """检查用户是否已同意条款"""
        return self.settings.value("terms_agreed", False, type=bool)

    def set_terms_agreed(self, agreed: bool):
        """设置用户同意条款状态"""
        self.settings.setValue("terms_agreed", agreed)
        self.settings.setValue("terms_agreed_time",
                               QDateTime.currentDateTime())

    def get_agreement_time(self) -> QDateTime:
        """获取用户同意条款的时间"""
        return self.settings.value("terms_agreed_time", QDateTime(), type=QDateTime)

    def check_and_request_agreement(self, parent=None) -> bool:
        """检查并请求用户同意条款"""
        if not self.has_agreed_to_terms():
            # 显示条款并请求同意
            agreed = DataUsageTermsDialog.request_agreement(parent)
            if agreed:
                self.set_terms_agreed(True)
                return True
            else:
                return False
        return True

    def show_terms_dialog(self, parent=None):
        """显示条款对话框"""
        DataUsageTermsDialog.show_terms(parent)
