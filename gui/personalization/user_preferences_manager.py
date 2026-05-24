"""
用户个性化界面配置和偏好保存系统
建立用户个性化界面配置系统，支持布局、主题、快捷键等个性化设置
"""

from loguru import logger
import json
import os
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QSpinBox,
    QSlider, QColorDialog, QFontDialog, QKeySequenceEdit,
    QTabWidget, QGroupBox, QScrollArea, QFrame, QSplitter,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QApplication, QMessageBox, QFileDialog
)
from PyQt5.QtCore import (
    Qt, QSettings, pyqtSignal, QObject, QTimer, QSize,
    QRect, QPoint
)
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPalette, QKeySequence
import threading


class PreferenceCategory(Enum):
    """偏好设置类别"""
    APPEARANCE = "appearance"       # 外观设置
    LAYOUT = "layout"              # 布局设置
    BEHAVIOR = "behavior"          # 行为设置
    SHORTCUTS = "shortcuts"        # 快捷键设置
    PERFORMANCE = "performance"    # 性能设置
    ACCESSIBILITY = "accessibility"  # 无障碍设置


class ThemeType(Enum):
    """主题类型"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"
    CUSTOM = "custom"


class LayoutType(Enum):
    """布局类型"""
    COMPACT = "compact"
    NORMAL = "normal"
    EXPANDED = "expanded"
    CUSTOM = "custom"


@dataclass
class AppearancePreferences:
    """外观偏好设置"""
    theme: ThemeType = ThemeType.LIGHT
    custom_theme_path: str = ""
    font_family: str = "Microsoft YaHei UI"
    font_size: int = 10
    ui_scale: float = 1.0
    accent_color: str = "#2196F3"
    window_opacity: float = 1.0
    show_animations: bool = True
    animation_speed: float = 1.0
    icon_theme: str = "default"


@dataclass
class LayoutPreferences:
    """布局偏好设置"""
    layout_type: LayoutType = LayoutType.NORMAL
    sidebar_visible: bool = True
    sidebar_width: int = 250
    toolbar_visible: bool = True
    statusbar_visible: bool = True
    tab_position: str = "top"  # top, bottom, left, right
    splitter_sizes: Dict[str, List[int]] = field(default_factory=dict)
    window_geometry: Dict[str, Any] = field(default_factory=dict)
    dock_positions: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class BehaviorPreferences:
    """行为偏好设置"""
    auto_save_interval: int = 300  # 秒
    confirm_exit: bool = True
    remember_window_state: bool = True
    show_tooltips: bool = True
    tooltip_delay: int = 500  # 毫秒
    double_click_interval: int = 500
    auto_backup: bool = True
    backup_count: int = 5
    language: str = "zh_CN"
    date_format: str = "yyyy-MM-dd"
    time_format: str = "HH:mm:ss"


@dataclass
class ShortcutPreferences:
    """快捷键偏好设置"""
    shortcuts: Dict[str, str] = field(default_factory=dict)
    enable_global_shortcuts: bool = False
    shortcut_context: str = "application"  # application, widget


@dataclass
class PerformancePreferences:
    """性能偏好设置"""
    max_threads: int = 4
    cache_size_mb: int = 256
    enable_gpu_acceleration: bool = False
    lazy_loading: bool = True
    preload_data: bool = False
    memory_limit_mb: int = 1024
    gc_interval: int = 60  # 秒


@dataclass
class AccessibilityPreferences:
    """无障碍偏好设置"""
    high_contrast: bool = False
    large_fonts: bool = False
    screen_reader_support: bool = False
    keyboard_navigation: bool = True
    focus_indicators: bool = True
    sound_feedback: bool = False
    reduce_motion: bool = False


@dataclass
class UserPreferences:
    """用户偏好设置总类"""
    appearance: AppearancePreferences = field(default_factory=AppearancePreferences)
    layout: LayoutPreferences = field(default_factory=LayoutPreferences)
    behavior: BehaviorPreferences = field(default_factory=BehaviorPreferences)
    shortcuts: ShortcutPreferences = field(default_factory=ShortcutPreferences)
    performance: PerformancePreferences = field(default_factory=PerformancePreferences)
    accessibility: AccessibilityPreferences = field(default_factory=AccessibilityPreferences)

    # 元数据
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())
    user_id: str = ""


class PreferenceValidator:
    """偏好设置验证器"""

    @staticmethod
    def validate_appearance(prefs: AppearancePreferences) -> List[str]:
        """验证外观设置"""
        errors = []

        if prefs.font_size < 8 or prefs.font_size > 72:
            errors.append("字体大小必须在8-72之间")

        if prefs.ui_scale < 0.5 or prefs.ui_scale > 3.0:
            errors.append("UI缩放必须在0.5-3.0之间")

        if prefs.window_opacity < 0.1 or prefs.window_opacity > 1.0:
            errors.append("窗口透明度必须在0.1-1.0之间")

        if prefs.animation_speed < 0.1 or prefs.animation_speed > 5.0:
            errors.append("动画速度必须在0.1-5.0之间")

        # 验证颜色格式
        try:
            if not prefs.accent_color.startswith('#') or len(prefs.accent_color) != 7:
                errors.append("强调色格式无效")
        except Exception:
            errors.append("强调色格式无效")

        return errors

    @staticmethod
    def validate_layout(prefs: LayoutPreferences) -> List[str]:
        """验证布局设置"""
        errors = []

        if prefs.sidebar_width < 100 or prefs.sidebar_width > 800:
            errors.append("侧边栏宽度必须在100-800之间")

        valid_tab_positions = ["top", "bottom", "left", "right"]
        if prefs.tab_position not in valid_tab_positions:
            errors.append(f"标签位置必须是: {', '.join(valid_tab_positions)}")

        return errors

    @staticmethod
    def validate_behavior(prefs: BehaviorPreferences) -> List[str]:
        """验证行为设置"""
        errors = []

        if prefs.auto_save_interval < 30 or prefs.auto_save_interval > 3600:
            errors.append("自动保存间隔必须在30-3600秒之间")

        if prefs.tooltip_delay < 0 or prefs.tooltip_delay > 5000:
            errors.append("工具提示延迟必须在0-5000毫秒之间")

        if prefs.double_click_interval < 100 or prefs.double_click_interval > 2000:
            errors.append("双击间隔必须在100-2000毫秒之间")

        if prefs.backup_count < 1 or prefs.backup_count > 50:
            errors.append("备份数量必须在1-50之间")

        return errors

    @staticmethod
    def validate_performance(prefs: PerformancePreferences) -> List[str]:
        """验证性能设置"""
        errors = []

        if prefs.max_threads < 1 or prefs.max_threads > 32:
            errors.append("最大线程数必须在1-32之间")

        if prefs.cache_size_mb < 64 or prefs.cache_size_mb > 4096:
            errors.append("缓存大小必须在64-4096MB之间")

        if prefs.memory_limit_mb < 256 or prefs.memory_limit_mb > 16384:
            errors.append("内存限制必须在256-16384MB之间")

        if prefs.gc_interval < 10 or prefs.gc_interval > 600:
            errors.append("垃圾回收间隔必须在10-600秒之间")

        return errors

    @staticmethod
    def validate_preferences(prefs: UserPreferences) -> List[str]:
        """验证所有偏好设置"""
        errors = []

        errors.extend(PreferenceValidator.validate_appearance(prefs.appearance))
        errors.extend(PreferenceValidator.validate_layout(prefs.layout))
        errors.extend(PreferenceValidator.validate_behavior(prefs.behavior))
        errors.extend(PreferenceValidator.validate_performance(prefs.performance))

        return errors


class PreferenceStorage:
    """偏好设置存储管理器"""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or self._get_default_storage_path()
        self.backup_path = f"{self.storage_path}.backup"
        self._ensure_storage_directory()

    def _get_default_storage_path(self) -> str:
        """获取默认存储路径"""
        app_data_dir = Path.home() / ".FactorWeave-Quant" / "preferences"
        app_data_dir.mkdir(parents=True, exist_ok=True)
        return str(app_data_dir / "user_preferences.json")

    def _ensure_storage_directory(self):
        """确保存储目录存在"""
        storage_dir = Path(self.storage_path).parent
        storage_dir.mkdir(parents=True, exist_ok=True)

    def save_preferences(self, preferences: UserPreferences) -> bool:
        """保存偏好设置"""
        try:
            # 更新修改时间
            preferences.modified_at = datetime.now().isoformat()

            # 创建备份
            if os.path.exists(self.storage_path):
                import shutil
                shutil.copy2(self.storage_path, self.backup_path)

            # 保存到文件
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(preferences), f, indent=2, ensure_ascii=False)

            logger.info(f"偏好设置已保存到: {self.storage_path}")
            return True

        except Exception as e:
            logger.error(f"保存偏好设置失败: {e}")
            return False

    def load_preferences(self) -> Optional[UserPreferences]:
        """加载偏好设置"""
        try:
            if not os.path.exists(self.storage_path):
                logger.info("偏好设置文件不存在，使用默认设置")
                return UserPreferences()

            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 转换为数据类
            preferences = self._dict_to_preferences(data)

            logger.info(f"偏好设置已从 {self.storage_path} 加载")
            return preferences

        except Exception as e:
            logger.error(f"加载偏好设置失败: {e}")

            # 尝试从备份恢复
            if os.path.exists(self.backup_path):
                try:
                    with open(self.backup_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    preferences = self._dict_to_preferences(data)
                    logger.info("从备份文件恢复偏好设置")
                    return preferences
                except Exception as backup_e:
                    logger.error(f"从备份恢复失败: {backup_e}")

            # 返回默认设置
            return UserPreferences()

    def _dict_to_preferences(self, data: Dict[str, Any]) -> UserPreferences:
        """将字典转换为偏好设置对象"""
        try:
            # 处理嵌套的数据类
            appearance_data = data.get('appearance', {})
            layout_data = data.get('layout', {})
            behavior_data = data.get('behavior', {})
            shortcuts_data = data.get('shortcuts', {})
            performance_data = data.get('performance', {})
            accessibility_data = data.get('accessibility', {})

            # 转换枚举值
            if 'theme' in appearance_data:
                appearance_data['theme'] = ThemeType(appearance_data['theme'])

            if 'layout_type' in layout_data:
                layout_data['layout_type'] = LayoutType(layout_data['layout_type'])

            return UserPreferences(
                appearance=AppearancePreferences(**appearance_data),
                layout=LayoutPreferences(**layout_data),
                behavior=BehaviorPreferences(**behavior_data),
                shortcuts=ShortcutPreferences(**shortcuts_data),
                performance=PerformancePreferences(**performance_data),
                accessibility=AccessibilityPreferences(**accessibility_data),
                version=data.get('version', '1.0'),
                created_at=data.get('created_at', datetime.now().isoformat()),
                modified_at=data.get('modified_at', datetime.now().isoformat()),
                user_id=data.get('user_id', '')
            )

        except Exception as e:
            logger.error(f"转换偏好设置数据失败: {e}")
            return UserPreferences()

    def export_preferences(self, export_path: str, preferences: UserPreferences) -> bool:
        """导出偏好设置"""
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(preferences), f, indent=2, ensure_ascii=False)

            logger.info(f"偏好设置已导出到: {export_path}")
            return True

        except Exception as e:
            logger.error(f"导出偏好设置失败: {e}")
            return False

    def import_preferences(self, import_path: str) -> Optional[UserPreferences]:
        """导入偏好设置"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            preferences = self._dict_to_preferences(data)

            logger.info(f"偏好设置已从 {import_path} 导入")
            return preferences

        except Exception as e:
            logger.error(f"导入偏好设置失败: {e}")
            return None


class PreferenceDialog(QDialog):
    """偏好设置对话框"""

    # 信号定义
    preferences_changed = pyqtSignal(UserPreferences)

    def __init__(self, preferences: UserPreferences, parent=None):
        super().__init__(parent)

        self.preferences = preferences
        self.original_preferences = json.loads(json.dumps(asdict(preferences)))

        self.setup_ui()
        self.load_preferences_to_ui()

        self.setWindowTitle("偏好设置")
        self.setModal(True)
        self.resize(800, 600)

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 创建标签页
        self.tab_widget = QTabWidget()

        # 外观标签页
        self.appearance_tab = self.create_appearance_tab()
        self.tab_widget.addTab(self.appearance_tab, "外观")

        # 布局标签页
        self.layout_tab = self.create_layout_tab()
        self.tab_widget.addTab(self.layout_tab, "布局")

        # 行为标签页
        self.behavior_tab = self.create_behavior_tab()
        self.tab_widget.addTab(self.behavior_tab, "行为")

        # 快捷键标签页
        self.shortcuts_tab = self.create_shortcuts_tab()
        self.tab_widget.addTab(self.shortcuts_tab, "快捷键")

        # 性能标签页
        self.performance_tab = self.create_performance_tab()
        self.tab_widget.addTab(self.performance_tab, "性能")

        # 无障碍标签页
        self.accessibility_tab = self.create_accessibility_tab()
        self.tab_widget.addTab(self.accessibility_tab, "无障碍")

        layout.addWidget(self.tab_widget)

        # 按钮区域
        button_layout = QHBoxLayout()

        # 导入导出按钮
        self.import_button = QPushButton("导入设置")
        self.export_button = QPushButton("导出设置")
        self.reset_button = QPushButton("重置默认")

        button_layout.addWidget(self.import_button)
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()

        # 确定取消按钮
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        self.apply_button = QPushButton("应用")

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)

        layout.addLayout(button_layout)

        # 连接信号
        self.import_button.clicked.connect(self.import_preferences)
        self.export_button.clicked.connect(self.export_preferences)
        self.reset_button.clicked.connect(self.reset_to_defaults)
        self.ok_button.clicked.connect(self.accept_changes)
        self.cancel_button.clicked.connect(self.reject)
        self.apply_button.clicked.connect(self.apply_changes)

    def create_appearance_tab(self) -> QWidget:
        """创建外观标签页"""
        widget = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)

        # 主题设置
        theme_group = QGroupBox("主题设置")
        theme_layout = QGridLayout(theme_group)

        theme_layout.addWidget(QLabel("主题:"), 0, 0)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["浅色", "深色", "自动", "自定义"])
        theme_layout.addWidget(self.theme_combo, 0, 1)

        theme_layout.addWidget(QLabel("强调色:"), 1, 0)
        self.accent_color_button = QPushButton()
        self.accent_color_button.clicked.connect(self.choose_accent_color)
        theme_layout.addWidget(self.accent_color_button, 1, 1)

        layout.addWidget(theme_group)

        # 字体设置
        font_group = QGroupBox("字体设置")
        font_layout = QGridLayout(font_group)

        font_layout.addWidget(QLabel("字体:"), 0, 0)
        self.font_button = QPushButton()
        self.font_button.clicked.connect(self.choose_font)
        font_layout.addWidget(self.font_button, 0, 1)

        font_layout.addWidget(QLabel("UI缩放:"), 1, 0)
        self.ui_scale_slider = QSlider(Qt.Horizontal)
        self.ui_scale_slider.setRange(50, 300)
        self.ui_scale_label = QLabel("100%")
        self.ui_scale_slider.valueChanged.connect(
            lambda v: self.ui_scale_label.setText(f"{v}%")
        )
        font_layout.addWidget(self.ui_scale_slider, 1, 1)
        font_layout.addWidget(self.ui_scale_label, 1, 2)

        layout.addWidget(font_group)

        # 动画设置
        animation_group = QGroupBox("动画设置")
        animation_layout = QGridLayout(animation_group)

        self.show_animations_check = QCheckBox("启用动画效果")
        animation_layout.addWidget(self.show_animations_check, 0, 0)

        animation_layout.addWidget(QLabel("动画速度:"), 1, 0)
        self.animation_speed_slider = QSlider(Qt.Horizontal)
        self.animation_speed_slider.setRange(10, 500)
        self.animation_speed_label = QLabel("100%")
        self.animation_speed_slider.valueChanged.connect(
            lambda v: self.animation_speed_label.setText(f"{v}%")
        )
        animation_layout.addWidget(self.animation_speed_slider, 1, 1)
        animation_layout.addWidget(self.animation_speed_label, 1, 2)

        layout.addWidget(animation_group)

        layout.addStretch()
        widget.setWidget(content)
        return widget

    def create_layout_tab(self) -> QWidget:
        """创建布局标签页"""
        widget = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)

        # 布局类型
        layout_group = QGroupBox("布局类型")
        layout_layout = QVBoxLayout(layout_group)

        self.layout_compact_radio = QCheckBox("紧凑布局")
        self.layout_normal_radio = QCheckBox("正常布局")
        self.layout_expanded_radio = QCheckBox("展开布局")

        layout_layout.addWidget(self.layout_compact_radio)
        layout_layout.addWidget(self.layout_normal_radio)
        layout_layout.addWidget(self.layout_expanded_radio)

        layout.addWidget(layout_group)

        # 界面元素
        ui_group = QGroupBox("界面元素")
        ui_layout = QGridLayout(ui_group)

        self.sidebar_visible_check = QCheckBox("显示侧边栏")
        ui_layout.addWidget(self.sidebar_visible_check, 0, 0)

        ui_layout.addWidget(QLabel("侧边栏宽度:"), 1, 0)
        self.sidebar_width_spin = QSpinBox()
        self.sidebar_width_spin.setRange(100, 800)
        ui_layout.addWidget(self.sidebar_width_spin, 1, 1)

        self.toolbar_visible_check = QCheckBox("显示工具栏")
        ui_layout.addWidget(self.toolbar_visible_check, 2, 0)

        self.statusbar_visible_check = QCheckBox("显示状态栏")
        ui_layout.addWidget(self.statusbar_visible_check, 3, 0)

        ui_layout.addWidget(QLabel("标签位置:"), 4, 0)
        self.tab_position_combo = QComboBox()
        self.tab_position_combo.addItems(["顶部", "底部", "左侧", "右侧"])
        ui_layout.addWidget(self.tab_position_combo, 4, 1)

        layout.addWidget(ui_group)

        # 窗口设置
        window_group = QGroupBox("窗口设置")
        window_layout = QGridLayout(window_group)

        self.remember_window_state_check = QCheckBox("记住窗口状态")
        window_layout.addWidget(self.remember_window_state_check, 0, 0)

        window_layout.addWidget(QLabel("窗口透明度:"), 1, 0)
        self.window_opacity_slider = QSlider(Qt.Horizontal)
        self.window_opacity_slider.setRange(10, 100)
        self.window_opacity_label = QLabel("100%")
        self.window_opacity_slider.valueChanged.connect(
            lambda v: self.window_opacity_label.setText(f"{v}%")
        )
        window_layout.addWidget(self.window_opacity_slider, 1, 1)
        window_layout.addWidget(self.window_opacity_label, 1, 2)

        layout.addWidget(window_group)

        layout.addStretch()
        widget.setWidget(content)
        return widget

    def create_behavior_tab(self) -> QWidget:
        """创建行为标签页"""
        widget = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)

        # 自动保存
        save_group = QGroupBox("自动保存")
        save_layout = QGridLayout(save_group)

        save_layout.addWidget(QLabel("自动保存间隔(秒):"), 0, 0)
        self.auto_save_spin = QSpinBox()
        self.auto_save_spin.setRange(30, 3600)
        save_layout.addWidget(self.auto_save_spin, 0, 1)

        self.auto_backup_check = QCheckBox("启用自动备份")
        save_layout.addWidget(self.auto_backup_check, 1, 0)

        save_layout.addWidget(QLabel("备份数量:"), 2, 0)
        self.backup_count_spin = QSpinBox()
        self.backup_count_spin.setRange(1, 50)
        save_layout.addWidget(self.backup_count_spin, 2, 1)

        layout.addWidget(save_group)

        # 交互行为
        interaction_group = QGroupBox("交互行为")
        interaction_layout = QGridLayout(interaction_group)

        self.confirm_exit_check = QCheckBox("退出时确认")
        interaction_layout.addWidget(self.confirm_exit_check, 0, 0)

        self.show_tooltips_check = QCheckBox("显示工具提示")
        interaction_layout.addWidget(self.show_tooltips_check, 1, 0)

        interaction_layout.addWidget(QLabel("工具提示延迟(毫秒):"), 2, 0)
        self.tooltip_delay_spin = QSpinBox()
        self.tooltip_delay_spin.setRange(0, 5000)
        interaction_layout.addWidget(self.tooltip_delay_spin, 2, 1)

        interaction_layout.addWidget(QLabel("双击间隔(毫秒):"), 3, 0)
        self.double_click_spin = QSpinBox()
        self.double_click_spin.setRange(100, 2000)
        interaction_layout.addWidget(self.double_click_spin, 3, 1)

        layout.addWidget(interaction_group)

        # 语言和格式
        locale_group = QGroupBox("语言和格式")
        locale_layout = QGridLayout(locale_group)

        locale_layout.addWidget(QLabel("语言:"), 0, 0)
        self.language_combo = QComboBox()
        self.language_combo.addItems(["简体中文", "English", "繁體中文", "日本語"])
        locale_layout.addWidget(self.language_combo, 0, 1)

        locale_layout.addWidget(QLabel("日期格式:"), 1, 0)
        self.date_format_combo = QComboBox()
        self.date_format_combo.addItems(["yyyy-MM-dd", "dd/MM/yyyy", "MM/dd/yyyy"])
        locale_layout.addWidget(self.date_format_combo, 1, 1)

        locale_layout.addWidget(QLabel("时间格式:"), 2, 0)
        self.time_format_combo = QComboBox()
        self.time_format_combo.addItems(["HH:mm:ss", "hh:mm:ss AP", "HH:mm"])
        locale_layout.addWidget(self.time_format_combo, 2, 1)

        layout.addWidget(locale_group)

        layout.addStretch()
        widget.setWidget(content)
        return widget

    def create_shortcuts_tab(self) -> QWidget:
        """创建快捷键标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 快捷键设置
        self.shortcuts_tree = QTreeWidget()
        self.shortcuts_tree.setHeaderLabels(["功能", "快捷键"])
        self.shortcuts_tree.setColumnWidth(0, 300)

        # 添加快捷键项目
        self.populate_shortcuts_tree()

        layout.addWidget(self.shortcuts_tree)

        # 快捷键编辑
        edit_layout = QHBoxLayout()

        self.shortcut_edit = QKeySequenceEdit()
        edit_layout.addWidget(QLabel("新快捷键:"))
        edit_layout.addWidget(self.shortcut_edit)

        self.set_shortcut_button = QPushButton("设置")
        self.clear_shortcut_button = QPushButton("清除")
        self.reset_shortcuts_button = QPushButton("重置所有")

        edit_layout.addWidget(self.set_shortcut_button)
        edit_layout.addWidget(self.clear_shortcut_button)
        edit_layout.addWidget(self.reset_shortcuts_button)

        layout.addLayout(edit_layout)

        # 全局快捷键选项
        self.global_shortcuts_check = QCheckBox("启用全局快捷键")
        layout.addWidget(self.global_shortcuts_check)

        return widget

    def create_performance_tab(self) -> QWidget:
        """创建性能标签页"""
        widget = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)

        # 线程设置
        thread_group = QGroupBox("线程设置")
        thread_layout = QGridLayout(thread_group)

        thread_layout.addWidget(QLabel("最大线程数:"), 0, 0)
        self.max_threads_spin = QSpinBox()
        self.max_threads_spin.setRange(1, 32)
        thread_layout.addWidget(self.max_threads_spin, 0, 1)

        layout.addWidget(thread_group)

        # 内存设置
        memory_group = QGroupBox("内存设置")
        memory_layout = QGridLayout(memory_group)

        memory_layout.addWidget(QLabel("缓存大小(MB):"), 0, 0)
        self.cache_size_spin = QSpinBox()
        self.cache_size_spin.setRange(64, 4096)
        memory_layout.addWidget(self.cache_size_spin, 0, 1)

        memory_layout.addWidget(QLabel("内存限制(MB):"), 1, 0)
        self.memory_limit_spin = QSpinBox()
        self.memory_limit_spin.setRange(256, 16384)
        memory_layout.addWidget(self.memory_limit_spin, 1, 1)

        memory_layout.addWidget(QLabel("垃圾回收间隔(秒):"), 2, 0)
        self.gc_interval_spin = QSpinBox()
        self.gc_interval_spin.setRange(10, 600)
        memory_layout.addWidget(self.gc_interval_spin, 2, 1)

        layout.addWidget(memory_group)

        # 优化选项
        optimization_group = QGroupBox("优化选项")
        optimization_layout = QVBoxLayout(optimization_group)

        self.gpu_acceleration_check = QCheckBox("启用GPU加速")
        optimization_layout.addWidget(self.gpu_acceleration_check)

        self.lazy_loading_check = QCheckBox("启用延迟加载")
        optimization_layout.addWidget(self.lazy_loading_check)

        self.preload_data_check = QCheckBox("预加载数据")
        optimization_layout.addWidget(self.preload_data_check)

        layout.addWidget(optimization_group)

        layout.addStretch()
        widget.setWidget(content)
        return widget

    def create_accessibility_tab(self) -> QWidget:
        """创建无障碍标签页"""
        widget = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)

        # 视觉辅助
        visual_group = QGroupBox("视觉辅助")
        visual_layout = QVBoxLayout(visual_group)

        self.high_contrast_check = QCheckBox("高对比度模式")
        visual_layout.addWidget(self.high_contrast_check)

        self.large_fonts_check = QCheckBox("大字体模式")
        visual_layout.addWidget(self.large_fonts_check)

        self.reduce_motion_check = QCheckBox("减少动画效果")
        visual_layout.addWidget(self.reduce_motion_check)

        layout.addWidget(visual_group)

        # 交互辅助
        interaction_group = QGroupBox("交互辅助")
        interaction_layout = QVBoxLayout(interaction_group)

        self.keyboard_navigation_check = QCheckBox("键盘导航")
        interaction_layout.addWidget(self.keyboard_navigation_check)

        self.focus_indicators_check = QCheckBox("焦点指示器")
        interaction_layout.addWidget(self.focus_indicators_check)

        self.sound_feedback_check = QCheckBox("声音反馈")
        interaction_layout.addWidget(self.sound_feedback_check)

        layout.addWidget(interaction_group)

        # 屏幕阅读器
        screen_reader_group = QGroupBox("屏幕阅读器")
        screen_reader_layout = QVBoxLayout(screen_reader_group)

        self.screen_reader_check = QCheckBox("启用屏幕阅读器支持")
        screen_reader_layout.addWidget(self.screen_reader_check)

        layout.addWidget(screen_reader_group)

        layout.addStretch()
        widget.setWidget(content)
        return widget

    def populate_shortcuts_tree(self):
        """填充快捷键树"""
        # 文件操作
        file_item = QTreeWidgetItem(["文件操作", ""])
        self.shortcuts_tree.addTopLevelItem(file_item)

        shortcuts = [
            ("新建", "Ctrl+N"),
            ("打开", "Ctrl+O"),
            ("保存", "Ctrl+S"),
            ("另存为", "Ctrl+Shift+S"),
            ("退出", "Ctrl+Q")
        ]

        for name, shortcut in shortcuts:
            item = QTreeWidgetItem([name, shortcut])
            file_item.addChild(item)

        # 编辑操作
        edit_item = QTreeWidgetItem(["编辑操作", ""])
        self.shortcuts_tree.addTopLevelItem(edit_item)

        edit_shortcuts = [
            ("撤销", "Ctrl+Z"),
            ("重做", "Ctrl+Y"),
            ("复制", "Ctrl+C"),
            ("粘贴", "Ctrl+V"),
            ("全选", "Ctrl+A")
        ]

        for name, shortcut in edit_shortcuts:
            item = QTreeWidgetItem([name, shortcut])
            edit_item.addChild(item)

        # 展开所有项目
        self.shortcuts_tree.expandAll()

    def load_preferences_to_ui(self):
        """将偏好设置加载到UI"""
        try:
            # 外观设置
            theme_map = {
                ThemeType.LIGHT: 0,
                ThemeType.DARK: 1,
                ThemeType.AUTO: 2,
                ThemeType.CUSTOM: 3
            }
            self.theme_combo.setCurrentIndex(theme_map.get(self.preferences.appearance.theme, 0))

            self.update_accent_color_button(self.preferences.appearance.accent_color)
            self.update_font_button(self.preferences.appearance.font_family, self.preferences.appearance.font_size)

            self.ui_scale_slider.setValue(int(self.preferences.appearance.ui_scale * 100))
            self.show_animations_check.setChecked(self.preferences.appearance.show_animations)
            self.animation_speed_slider.setValue(int(self.preferences.appearance.animation_speed * 100))

            # 布局设置
            layout_type = self.preferences.layout.layout_type
            self.layout_compact_radio.setChecked(layout_type == LayoutType.COMPACT)
            self.layout_normal_radio.setChecked(layout_type == LayoutType.NORMAL)
            self.layout_expanded_radio.setChecked(layout_type == LayoutType.EXPANDED)

            self.sidebar_visible_check.setChecked(self.preferences.layout.sidebar_visible)
            self.sidebar_width_spin.setValue(self.preferences.layout.sidebar_width)
            self.toolbar_visible_check.setChecked(self.preferences.layout.toolbar_visible)
            self.statusbar_visible_check.setChecked(self.preferences.layout.statusbar_visible)

            tab_position_map = {"top": 0, "bottom": 1, "left": 2, "right": 3}
            self.tab_position_combo.setCurrentIndex(tab_position_map.get(self.preferences.layout.tab_position, 0))

            self.window_opacity_slider.setValue(int(self.preferences.appearance.window_opacity * 100))

            # 行为设置
            self.auto_save_spin.setValue(self.preferences.behavior.auto_save_interval)
            self.confirm_exit_check.setChecked(self.preferences.behavior.confirm_exit)
            self.remember_window_state_check.setChecked(self.preferences.behavior.remember_window_state)
            self.show_tooltips_check.setChecked(self.preferences.behavior.show_tooltips)
            self.tooltip_delay_spin.setValue(self.preferences.behavior.tooltip_delay)
            self.double_click_spin.setValue(self.preferences.behavior.double_click_interval)
            self.auto_backup_check.setChecked(self.preferences.behavior.auto_backup)
            self.backup_count_spin.setValue(self.preferences.behavior.backup_count)

            # 性能设置
            self.max_threads_spin.setValue(self.preferences.performance.max_threads)
            self.cache_size_spin.setValue(self.preferences.performance.cache_size_mb)
            self.memory_limit_spin.setValue(self.preferences.performance.memory_limit_mb)
            self.gc_interval_spin.setValue(self.preferences.performance.gc_interval)
            self.gpu_acceleration_check.setChecked(self.preferences.performance.enable_gpu_acceleration)
            self.lazy_loading_check.setChecked(self.preferences.performance.lazy_loading)
            self.preload_data_check.setChecked(self.preferences.performance.preload_data)

            # 无障碍设置
            self.high_contrast_check.setChecked(self.preferences.accessibility.high_contrast)
            self.large_fonts_check.setChecked(self.preferences.accessibility.large_fonts)
            self.screen_reader_check.setChecked(self.preferences.accessibility.screen_reader_support)
            self.keyboard_navigation_check.setChecked(self.preferences.accessibility.keyboard_navigation)
            self.focus_indicators_check.setChecked(self.preferences.accessibility.focus_indicators)
            self.sound_feedback_check.setChecked(self.preferences.accessibility.sound_feedback)
            self.reduce_motion_check.setChecked(self.preferences.accessibility.reduce_motion)

            # 快捷键设置
            self.global_shortcuts_check.setChecked(self.preferences.shortcuts.enable_global_shortcuts)

        except Exception as e:
            logger.error(f"加载偏好设置到UI失败: {e}")

    def save_ui_to_preferences(self):
        """将UI设置保存到偏好设置"""
        try:
            # 外观设置
            theme_map = [ThemeType.LIGHT, ThemeType.DARK, ThemeType.AUTO, ThemeType.CUSTOM]
            self.preferences.appearance.theme = theme_map[self.theme_combo.currentIndex()]

            self.preferences.appearance.ui_scale = self.ui_scale_slider.value() / 100.0
            self.preferences.appearance.show_animations = self.show_animations_check.isChecked()
            self.preferences.appearance.animation_speed = self.animation_speed_slider.value() / 100.0
            self.preferences.appearance.window_opacity = self.window_opacity_slider.value() / 100.0

            # 布局设置
            if self.layout_compact_radio.isChecked():
                self.preferences.layout.layout_type = LayoutType.COMPACT
            elif self.layout_normal_radio.isChecked():
                self.preferences.layout.layout_type = LayoutType.NORMAL
            elif self.layout_expanded_radio.isChecked():
                self.preferences.layout.layout_type = LayoutType.EXPANDED

            self.preferences.layout.sidebar_visible = self.sidebar_visible_check.isChecked()
            self.preferences.layout.sidebar_width = self.sidebar_width_spin.value()
            self.preferences.layout.toolbar_visible = self.toolbar_visible_check.isChecked()
            self.preferences.layout.statusbar_visible = self.statusbar_visible_check.isChecked()

            tab_positions = ["top", "bottom", "left", "right"]
            self.preferences.layout.tab_position = tab_positions[self.tab_position_combo.currentIndex()]

            # 行为设置
            self.preferences.behavior.auto_save_interval = self.auto_save_spin.value()
            self.preferences.behavior.confirm_exit = self.confirm_exit_check.isChecked()
            self.preferences.behavior.remember_window_state = self.remember_window_state_check.isChecked()
            self.preferences.behavior.show_tooltips = self.show_tooltips_check.isChecked()
            self.preferences.behavior.tooltip_delay = self.tooltip_delay_spin.value()
            self.preferences.behavior.double_click_interval = self.double_click_spin.value()
            self.preferences.behavior.auto_backup = self.auto_backup_check.isChecked()
            self.preferences.behavior.backup_count = self.backup_count_spin.value()

            # 性能设置
            self.preferences.performance.max_threads = self.max_threads_spin.value()
            self.preferences.performance.cache_size_mb = self.cache_size_spin.value()
            self.preferences.performance.memory_limit_mb = self.memory_limit_spin.value()
            self.preferences.performance.gc_interval = self.gc_interval_spin.value()
            self.preferences.performance.enable_gpu_acceleration = self.gpu_acceleration_check.isChecked()
            self.preferences.performance.lazy_loading = self.lazy_loading_check.isChecked()
            self.preferences.performance.preload_data = self.preload_data_check.isChecked()

            # 无障碍设置
            self.preferences.accessibility.high_contrast = self.high_contrast_check.isChecked()
            self.preferences.accessibility.large_fonts = self.large_fonts_check.isChecked()
            self.preferences.accessibility.screen_reader_support = self.screen_reader_check.isChecked()
            self.preferences.accessibility.keyboard_navigation = self.keyboard_navigation_check.isChecked()
            self.preferences.accessibility.focus_indicators = self.focus_indicators_check.isChecked()
            self.preferences.accessibility.sound_feedback = self.sound_feedback_check.isChecked()
            self.preferences.accessibility.reduce_motion = self.reduce_motion_check.isChecked()

            # 快捷键设置
            self.preferences.shortcuts.enable_global_shortcuts = self.global_shortcuts_check.isChecked()

        except Exception as e:
            logger.error(f"保存UI到偏好设置失败: {e}")

    def choose_accent_color(self):
        """选择强调色"""
        try:
            current_color = QColor(self.preferences.appearance.accent_color)
            color = QColorDialog.getColor(current_color, self, "选择强调色")

            if color.isValid():
                self.preferences.appearance.accent_color = color.name()
                self.update_accent_color_button(color.name())

        except Exception as e:
            logger.error(f"选择强调色失败: {e}")

    def update_accent_color_button(self, color: str):
        """更新强调色按钮"""
        try:
            self.accent_color_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border: 2px solid #ccc;
                    border-radius: 4px;
                    min-height: 30px;
                }}
            """)
            self.accent_color_button.setText(color)

        except Exception as e:
            logger.error(f"更新强调色按钮失败: {e}")

    def choose_font(self):
        """选择字体"""
        try:
            current_font = QFont(
                self.preferences.appearance.font_family,
                self.preferences.appearance.font_size
            )

            font, ok = QFontDialog.getFont(current_font, self, "选择字体")

            if ok:
                self.preferences.appearance.font_family = font.family()
                self.preferences.appearance.font_size = font.pointSize()
                self.update_font_button(font.family(), font.pointSize())

        except Exception as e:
            logger.error(f"选择字体失败: {e}")

    def update_font_button(self, family: str, size: int):
        """更新字体按钮"""
        try:
            self.font_button.setText(f"{family}, {size}pt")
            self.font_button.setFont(QFont(family, min(size, 12)))  # 限制按钮字体大小

        except Exception as e:
            logger.error(f"更新字体按钮失败: {e}")

    def import_preferences(self):
        """导入偏好设置"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "导入偏好设置", "", "JSON Files (*.json)"
            )

            if file_path:
                storage = PreferenceStorage()
                imported_prefs = storage.import_preferences(file_path)

                if imported_prefs:
                    self.preferences = imported_prefs
                    self.load_preferences_to_ui()
                    QMessageBox.information(self, "成功", "偏好设置导入成功")
                else:
                    QMessageBox.warning(self, "错误", "导入偏好设置失败")

        except Exception as e:
            logger.error(f"导入偏好设置失败: {e}")
            QMessageBox.critical(self, "错误", f"导入失败: {e}")

    def export_preferences(self):
        """导出偏好设置"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出偏好设置", "preferences.json", "JSON Files (*.json)"
            )

            if file_path:
                self.save_ui_to_preferences()
                storage = PreferenceStorage()

                if storage.export_preferences(file_path, self.preferences):
                    QMessageBox.information(self, "成功", "偏好设置导出成功")
                else:
                    QMessageBox.warning(self, "错误", "导出偏好设置失败")

        except Exception as e:
            logger.error(f"导出偏好设置失败: {e}")
            QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def reset_to_defaults(self):
        """重置为默认设置"""
        try:
            reply = QMessageBox.question(
                self, "确认重置", "确定要重置所有设置为默认值吗？",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.preferences = UserPreferences()
                self.load_preferences_to_ui()

        except Exception as e:
            logger.error(f"重置默认设置失败: {e}")

    def apply_changes(self):
        """应用更改"""
        try:
            self.save_ui_to_preferences()

            # 验证设置
            errors = PreferenceValidator.validate_preferences(self.preferences)
            if errors:
                QMessageBox.warning(self, "验证失败", "\n".join(errors))
                return

            self.preferences_changed.emit(self.preferences)

        except Exception as e:
            logger.error(f"应用更改失败: {e}")
            QMessageBox.critical(self, "错误", f"应用失败: {e}")

    def accept_changes(self):
        """接受更改并关闭"""
        try:
            self.apply_changes()
            self.accept()

        except Exception as e:
            logger.error(f"接受更改失败: {e}")


class UserPreferencesManager(QObject):
    """用户偏好设置管理器主类"""

    # 信号定义
    preferences_loaded = pyqtSignal(UserPreferences)
    preferences_saved = pyqtSignal(UserPreferences)
    preferences_changed = pyqtSignal(UserPreferences, UserPreferences)  # new, old

    def __init__(self, storage_path: Optional[str] = None):
        super().__init__()

        self.storage = PreferenceStorage(storage_path)
        self.current_preferences: Optional[UserPreferences] = None
        self.auto_save_timer = QTimer()
        self.auto_save_enabled = True

        # 设置自动保存
        self.auto_save_timer.timeout.connect(self._auto_save)

        logger.info("用户偏好设置管理器已初始化")

    def load_preferences(self) -> UserPreferences:
        """加载偏好设置"""
        try:
            old_preferences = self.current_preferences
            self.current_preferences = self.storage.load_preferences()

            if self.current_preferences:
                # 启动自动保存
                if self.auto_save_enabled:
                    interval = self.current_preferences.behavior.auto_save_interval * 1000
                    self.auto_save_timer.start(interval)

                self.preferences_loaded.emit(self.current_preferences)

                if old_preferences:
                    self.preferences_changed.emit(self.current_preferences, old_preferences)

                logger.info("偏好设置加载完成")

            return self.current_preferences

        except Exception as e:
            logger.error(f"加载偏好设置失败: {e}")
            return UserPreferences()

    def save_preferences(self, preferences: Optional[UserPreferences] = None) -> bool:
        """保存偏好设置"""
        try:
            prefs_to_save = preferences or self.current_preferences

            if not prefs_to_save:
                logger.warning("没有偏好设置可保存")
                return False

            # 验证设置
            errors = PreferenceValidator.validate_preferences(prefs_to_save)
            if errors:
                logger.error(f"偏好设置验证失败: {errors}")
                return False

            # 保存
            success = self.storage.save_preferences(prefs_to_save)

            if success:
                old_preferences = self.current_preferences
                self.current_preferences = prefs_to_save

                self.preferences_saved.emit(self.current_preferences)

                if old_preferences:
                    self.preferences_changed.emit(self.current_preferences, old_preferences)

                logger.info("偏好设置保存完成")

            return success

        except Exception as e:
            logger.error(f"保存偏好设置失败: {e}")
            return False

    def update_preferences(self, **kwargs) -> bool:
        """更新偏好设置"""
        try:
            if not self.current_preferences:
                self.current_preferences = UserPreferences()

            # 更新指定的设置
            for key, value in kwargs.items():
                if hasattr(self.current_preferences, key):
                    setattr(self.current_preferences, key, value)

            return self.save_preferences()

        except Exception as e:
            logger.error(f"更新偏好设置失败: {e}")
            return False

    def get_preferences(self) -> UserPreferences:
        """获取当前偏好设置"""
        if not self.current_preferences:
            self.load_preferences()

        return self.current_preferences

    def show_preferences_dialog(self, parent: Optional[QWidget] = None) -> bool:
        """显示偏好设置对话框"""
        try:
            if not self.current_preferences:
                self.load_preferences()

            dialog = PreferenceDialog(self.current_preferences, parent)
            dialog.preferences_changed.connect(self.save_preferences)

            return dialog.exec_() == QDialog.Accepted

        except Exception as e:
            logger.error(f"显示偏好设置对话框失败: {e}")
            return False

    def export_preferences(self, file_path: str) -> bool:
        """导出偏好设置"""
        try:
            if not self.current_preferences:
                self.load_preferences()

            return self.storage.export_preferences(file_path, self.current_preferences)

        except Exception as e:
            logger.error(f"导出偏好设置失败: {e}")
            return False

    def import_preferences(self, file_path: str) -> bool:
        """导入偏好设置"""
        try:
            imported_prefs = self.storage.import_preferences(file_path)

            if imported_prefs:
                return self.save_preferences(imported_prefs)

            return False

        except Exception as e:
            logger.error(f"导入偏好设置失败: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """重置为默认设置"""
        try:
            default_prefs = UserPreferences()
            return self.save_preferences(default_prefs)

        except Exception as e:
            logger.error(f"重置默认设置失败: {e}")
            return False

    def _auto_save(self):
        """自动保存"""
        try:
            if self.current_preferences and self.auto_save_enabled:
                self.save_preferences()

        except Exception as e:
            logger.error(f"自动保存失败: {e}")

    def set_auto_save_enabled(self, enabled: bool):
        """设置自动保存启用状态"""
        self.auto_save_enabled = enabled

        if enabled and self.current_preferences:
            interval = self.current_preferences.behavior.auto_save_interval * 1000
            self.auto_save_timer.start(interval)
        else:
            self.auto_save_timer.stop()

    def get_preference_statistics(self) -> Dict[str, Any]:
        """获取偏好设置统计信息"""
        try:
            if not self.current_preferences:
                return {'error': '偏好设置未加载'}

            return {
                'version': self.current_preferences.version,
                'created_at': self.current_preferences.created_at,
                'modified_at': self.current_preferences.modified_at,
                'user_id': self.current_preferences.user_id,
                'theme': self.current_preferences.appearance.theme.value,
                'layout_type': self.current_preferences.layout.layout_type.value,
                'auto_save_interval': self.current_preferences.behavior.auto_save_interval,
                'max_threads': self.current_preferences.performance.max_threads,
                'cache_size_mb': self.current_preferences.performance.cache_size_mb,
                'shortcuts_count': len(self.current_preferences.shortcuts.shortcuts),
                'auto_save_enabled': self.auto_save_enabled
            }

        except Exception as e:
            logger.error(f"获取偏好设置统计失败: {e}")
            return {'error': str(e)}


# 全局实例
user_preferences_manager = None


def get_user_preferences_manager(storage_path: Optional[str] = None) -> UserPreferencesManager:
    """获取用户偏好设置管理器实例"""
    global user_preferences_manager

    if user_preferences_manager is None:
        user_preferences_manager = UserPreferencesManager(storage_path)

    return user_preferences_manager


def get_current_preferences() -> UserPreferences:
    """获取当前偏好设置的便捷函数"""
    manager = get_user_preferences_manager()
    return manager.get_preferences()


def show_preferences_dialog(parent: Optional[QWidget] = None) -> bool:
    """显示偏好设置对话框的便捷函数"""
    manager = get_user_preferences_manager()
    return manager.show_preferences_dialog(parent)
