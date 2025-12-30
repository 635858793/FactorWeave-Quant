# 全局ThemeManager添加apply_theme方法

## 问题
2025-12-27 22:04:31 报错：`'ThemeManager' object has no attribute 'apply_theme'`

## 根本原因
全局 `ThemeManager` 类（`utils/theme.py`）缺少 `apply_theme` 方法，之前删除的本地 `ThemeManager` 类有这个方法。

全局 `ThemeManager` 原有方法：
- `set_theme(theme_name)` - 切换主题
- `get_theme_colors()` - 获取颜色
- `get_color(name)` - 获取单个颜色
- `apply_chart_theme()` - 应用图表主题
- `is_dark_theme()` - 检查是否深色主题
- `apply_qss_theme_content()` - 应用QSS内容（仅用于QSS主题）

缺少方法：
- `apply_theme(widget)` - 应用主题到指定控件（用于JSON主题）

## 解决方案
在 `utils/theme.py` 的 `ThemeManager` 类中添加两个方法：

1. `apply_theme(widget)` - 应用主题到控件
2. `_build_stylesheet(colors)` - 构建QSS样式表

## 文件位置
`utils/theme.py` 第453-586行

## 验证
✅ 语法检查通过
