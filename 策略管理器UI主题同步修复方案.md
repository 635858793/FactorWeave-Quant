# 策略管理器UI主题同步修复方案

## 问题概述
策略管理器UI（EnhancedStrategyManagerDialog）的主题与系统全局主题管理器不同步，导致主题切换失败。问题涉及颜色、UI样式、按钮样式等多个方面。

## 核心问题分析

### 问题1: 主题管理器实例不一致
**位置**: `enhanced_strategy_manager_dialog.py:298730`

**问题描述**: 
策略管理器使用全局`theme_manager`变量，如果主窗口或其他组件创建了独立的ThemeManager实例，策略管理器将无法接收到主题变化信号。

**影响**: 
全局主题切换时，策略管理器对话框不会响应。

**修复方案**:
修改`__init__`接收`theme_manager`参数，通过依赖注入传递ThemeManager实例。

**代码修改**:
```python
# 修改前
def __init__(self, parent=None, strategy_service=None, trading_service=None):
    from utils.theme import theme_manager
    theme_manager.theme_changed.connect(self._on_theme_changed)

# 修改后
def __init__(self, parent=None, strategy_service=None, trading_service=None, theme_manager=None):
    from utils.theme import theme_manager as default_theme_manager
    self.theme_manager = theme_manager or default_theme_manager
    self.theme_manager.theme_changed.connect(self._on_theme_changed)
```

### 问题2: apply_theme方法不完整
**位置**: `utils/theme.py:464977-464983`

**问题描述**:
`apply_theme`方法只对没有样式表的子组件应用主题，已有样式的组件不会更新。

**影响**:
主题切换后，某些组件保留旧样式。

**修复方案**:
移除`if not child.styleSheet()`条件判断，强制对所有子组件应用主题。

**代码修改**:
```python
# 修改前
def apply_theme(self, widget):
    """应用主题到指定控件"""
    colors = self.get_theme_colors()
    stylesheet = self._build_stylesheet(processed_colors)
    widget.setStyleSheet(stylesheet)
    for child in widget.findChildren(QWidget):
        if not child.styleSheet():  # ⚠️ 关键问题
            child.setStyleSheet(stylesheet)

# 修改后
def apply_theme(self, widget):
    """应用主题到指定控件"""
    colors = self.get_theme_colors()
    stylesheet = self._build_stylesheet(processed_colors)
    widget.setStyleSheet(stylesheet)
    for child in widget.findChildren(QWidget):
        child.setStyleSheet(stylesheet)  # 强制应用主题
```

### 问题3: 递归主题更新性能问题
**位置**: `enhanced_strategy_manager_dialog.py:301950-301975`

**问题描述**:
`findChildren(QWidget)`会递归查找所有子组件，然后对每个子组件再次调用`findChildren(QWidget)`，导致大量重复处理。

**影响**:
主题切换时UI卡顿，CPU占用高。

**修复方案**:
重构`_deep_apply_theme_to_widget`方法，使用扁平化遍历，记录已处理组件。

**代码修改**:
```python
# 修改前
def _deep_apply_theme_to_widget(self, widget):
    """深度应用主题到所有子组件"""
    for child in widget.findChildren(QWidget):
        self.theme_manager.apply_theme(child)
        self._deep_apply_theme_to_widget(child)  # 递归调用

# 修改后
def _deep_apply_theme_to_widget(self, widget):
    """深度应用主题到所有子组件（优化版）"""
    processed_widgets = set()
    
    def apply_to_widget(w):
        if w in processed_widgets:
            return
        processed_widgets.add(w)
        self.theme_manager.apply_theme(w)
        for child in w.findChildren(QWidget):
            apply_to_widget(child)
    
    apply_to_widget(widget)
```

### 问题4: 表格颜色硬编码
**位置**: `enhanced_strategy_manager_dialog.py:297508-297521`

**问题描述**:
表格项的颜色通过`setBackground()`直接设置，会覆盖QSS样式表中的颜色设置。

**影响**:
主题切换后，表格状态列颜色不变。

**修复方案**:
移除`setBackground`调用，改用QSS样式表控制表格项颜色。

**代码修改**:
```python
# 修改前
item.setBackground(QColor('#4CAF50'))  # 运行中 - 绿色

# 修改后
# 在QSS样式表中定义状态颜色
QTableWidget::item[data-status="running"] {
    background-color: #4CAF50;
}
```

### 问题5: QSS/JSON主题混合冲突
**位置**: `utils/theme.py:464830-464842`

**问题描述**:
QSS主题通过`app.setStyleSheet()`全局应用，JSON主题通过`_refresh_all_widgets`逐个组件更新，切换时样式残留或优先级不明确。

**影响**:
从QSS切换到JSON时某些组件样式不正确，从JSON切换到QSS时组件的JSON样式可能残留。

**修复方案**:
明确定义样式优先级：QSS主题 > JSON主题 > 全局样式，切换时完全清除旧样式。

**代码修改**:
```python
def set_theme(self, theme_type):
    """设置主题（优化版）"""
    # 清除所有旧样式
    self.app.setStyleSheet('')
    for widget in self._tracked_widgets:
        widget.setStyleSheet('')
    
    # 应用新主题
    if theme_type == ThemeType.QSS:
        stylesheet = self._load_qss_theme(theme_type)
        self.app.setStyleSheet(stylesheet)
    elif theme_type == ThemeType.JSON:
        self._load_json_theme(theme_type)
        self._refresh_all_widgets()
```

### 问题6: 子对话框主题未同步
**位置**: `enhanced_strategy_manager_dialog.py:299154-299189`

**问题描述**:
子对话框在创建时应用一次主题，未监听主题变化信号。

**影响**:
子对话框主题不随主对话框变化。

**修复方案**:
为所有子对话框添加主题变化信号监听。

**代码修改**:
```python
# 子对话框基类
class BaseSubDialog(QDialog):
    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager or parent.theme_manager
        self.theme_manager.theme_changed.connect(self._on_theme_changed)
        self._setup_ui()
        self.theme_manager.apply_theme(self)
    
    def _on_theme_changed(self, theme_type):
        """主题变化回调"""
        self.theme_manager.apply_theme(self)
```

## 实施计划

### 阶段1: 核心问题修复（高优先级）
1. 修复主题管理器实例不一致问题
2. 改进ThemeManager.apply_theme方法
3. 优化递归主题更新逻辑
4. 修复表格颜色硬编码问题

### 阶段2: 主题系统优化（中优先级）
5. 解决QSS/JSON主题混合冲突
6. 子对话框主题同步
7. 改进信号连接管理
8. 修复主题缓存更新时机

### 阶段3: 性能和稳定性（低优先级）
9. 优化_refresh_all_widgets方法
10. 修复策略管理器对话框创建时机
11. 改进主题颜色获取方法
12. 统一主题类型枚举

### 阶段4: 完善和测试（验证阶段）
13. 移除全局样式表
14. 完善子对话框主题应用
15. 添加主题切换回调验证
16. 添加性能监控和日志
17. 编写单元测试

## 预期效果

修复完成后，策略管理器UI将能够：
1. 正确响应全局主题切换信号
2. 所有UI组件（包括子对话框）同步更新主题
3. 主题切换性能优化，无明显卡顿
4. 支持QSS和JSON主题无缝切换
5. 主题样式一致性得到保证
