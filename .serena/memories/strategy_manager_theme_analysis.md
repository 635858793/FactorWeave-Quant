# 策略管理器UI主题系统分析结果

## 一、主题存储机制

### 1. 数据库主题表 (SQLite)
- **表名**: `themes`
- **路径**: `db/factorweave_system.sqlite`
- **字段**:
  - `id`: 主键
  - `name`: 主题名称
  - `type`: 主题类型 (json/qss)
  - `content`: 主题内容
  - `base_type`: 基础类型 (light/dark/gradient)
  - `origin`: 来源 (system/file/imported)
  - `created_at/updated_at`: 时间戳

### 2. 主题来源
- **QSS主题文件**: 17个 (QSSTheme/1.qss - 17.qss)
- **JSON主题配置**: 3个 (config/theme.json: light, dark, gradient)
- **总计**: 20种主题

## 二、ThemeManager核心功能

### 关键文件
- `utils/theme.py`: ThemeManager类定义
- `config/theme.json`: JSON主题配置
- `QSSTheme/*.qss`: QSS主题文件

### 核心方法
```python
def __init__(self):  # 初始化时导入主题到数据库
    self._load_theme_json()  # 加载config/theme.json
    self._import_themes_to_db()  # 导入QSS主题到数据库

def set_theme(self, theme_name: str):  # 设置主题
    # 1. 获取数据库中的主题内容
    # 2. 根据base_type设置Theme枚举
    # 3. QSS主题: 直接应用setStyleSheet
    # 4. JSON主题: 发送信号 + 异步刷新窗口

def _refresh_all_widgets(self):  # 刷新所有窗口组件
    # 异步批量刷新，避免UI卡顿
```

## 三、主题应用调用链

```
用户选择主题
    ↓
ThemeManager.set_theme(theme_name)
    ↓
┌─ QSS主题 ──→ apply_qss_theme_content() → app.setStyleSheet()
└─ JSON主题 ─→ theme_changed.emit() → _refresh_all_widgets()
                      ↓
              遍历所有topLevelWidgets
                      ↓
              异步批量刷新组件样式
```

## 四、策略管理器UI问题

### 问题1: 子对话框未应用主题
- **位置**: enhanced_strategy_manager_dialog.py
- **影响**: ParameterDialog, BacktestResultDialog, OptimizeDialog等子对话框
- **原因**: 子对话框创建时未调用theme_manager.apply_theme()

### 问题2: 硬编码颜色
- **行43105-43117**: 性能卡片硬编码颜色
- **行41488-41492**: 状态栏硬编码颜色
- **影响**: 无法随主题切换而变化

### 问题3: 主题切换响应不完整
- 主对话框监听theme_changed信号
- 子对话框未监听，可能导致主题不一致

## 五、主题类型说明

### JSON主题 (config/theme.json)
- light: 明亮灰白主题
- dark: 深色主题
- gradient: 渐变主题

### QSS主题 (QSSTheme/*.qss)
- 1.qss - 16.qss: 深色系主题 (蓝色/深灰渐变)
- 17.qss: 浅色主题 (白色靓丽风格)

## 六、修复策略

### 短期修复 (策略管理器)
1. 确保所有子对话框创建时应用当前主题
2. 将硬编码颜色替换为theme_manager.get_color()
3. 子对话框监听theme_changed信号

### 长期优化
1. 统一所有UI组件的主题应用机制
2. 建立主题一致性检查工具
3. 文档化主题系统架构

---
**分析时间**: 2025-12-27
**分析范围**: 策略管理器UI + 主题管理系统
